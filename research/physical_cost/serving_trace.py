"""Execute a serving DAG on addressed SRAM and an explicit DDR controller."""

from collections import Counter
from dataclasses import dataclass
from heapq import heapify, heappop, heappush
from math import ceil

from research.physical_cost.banked_serving import Region
from research.physical_cost.serving_ddr import CK, DDR


@dataclass(frozen=True, slots=True)
class Access:
    slot: str
    first: int
    words: int
    value: tuple
    offset: int = 0


@dataclass(frozen=True, slots=True)
class Task:
    owner: int
    label: str
    deps: tuple
    direction: str
    accesses: tuple
    release: int
    dram_line: int | None = None
    cycles: int = 0
    alu: int = 0
    local_read: int = 0
    local_write: int = 0


class Program:
    def __init__(self, hardware, priority):
        self.hardware = hardware
        self.priority = priority
        self.regions = {}
        self.tasks = []
        self.used = [0] * hardware.global_banks

    def reserve(self, name, words, order):
        region = Region(order, tuple(self.used[b] for b in order), words)
        for bank, count in region.counts(0, words):
            self.used[bank] += count
        self.regions[name] = region

    def add(self, owner, label, deps=(), direction="", accesses=(), release=0, **fields):
        index = len(self.tasks)
        self.tasks.append(Task(owner, label, tuple(dict.fromkeys(deps)), direction, accesses,
                               release, **fields))
        return index


def run(program, macros, record=False):
    hw = program.hardware
    ddr = DDR(record)
    macro, local = macros[hw.global_bank_bytes], macros[hw.weight_bytes_per_stripe]
    period = 1000 * ceil(max(macro["cycle_ns"], macro["access_ns"]))
    ports = {"r": [0] * hw.global_banks, "w": [0] * hw.global_banks}
    counts = Counter()
    # Dispatch by dependency completion with deterministic priority for simultaneous arrivals.
    tasks = program.tasks
    children = [[] for _ in tasks]
    remaining = [len(task.deps) for task in tasks]
    ready = [task.release for task in tasks]
    finish = [0] * len(tasks)
    intervals = []
    for i, task in enumerate(tasks):
        for parent in task.deps:
            children[parent].append(i)
    queue = [(t.release, (t.owner != program.priority), i) for i, t in enumerate(tasks) if not t.deps]
    heapify(queue)
    core = 0
    while queue:
        release, _, index = heappop(queue)
        task = tasks[index]
        stop = release
        if task.cycles:
            start = max(core, release)
            core = stop = start + 1000 * task.cycles
            counts["alu"] += task.alu
            counts["local_read"] += task.local_read
            counts["local_write"] += task.local_write
            if record:
                intervals.append((start, stop, index, "core", -1, -1, None, None))
        for access in task.accesses:
            region = program.regions[access.slot]
            port = ports[task.direction]
            counts[task.direction] += access.words
            if not record and task.dram_line is None:
                for bank, words in region.counts(access.first, access.words):
                    if words:
                        port[bank] = max(port[bank], release) + period * words
                        stop = max(stop, port[bank])
                continue
            lanes = len(region.order)
            for i in range(access.words):
                line = access.first + i
                lane = line % lanes
                bank, row = region.order[lane], region.starts[lane] + line // lanes
                start = max(port[bank], release)
                dram = None if task.dram_line is None else task.dram_line + i
                if dram is not None and task.direction == "w":
                    # One response line can be held at the interface. Release
                    # the request only when its destination bank can accept it.
                    _, start = ddr.burst(dram, False, start)
                    counts["ddr_read"] += 1
                elif dram is not None:
                    start = max(start, ddr.dq * CK)
                port[bank] = start + period
                stop = max(stop, port[bank])
                if dram is not None and task.direction == "r":
                    _, end = ddr.burst(dram, True, port[bank])
                    stop = max(stop, end)
                    counts["ddr_write"] += 1
                if record:
                    intervals.append((start, port[bank], index, task.direction, bank, row,
                                      (access.value, access.offset + i), dram))
        finish[index] = stop
        for child in children[index]:
            ready[child] = max(ready[child], stop)
            remaining[child] -= 1
            if not remaining[child]:
                heappush(queue, (ready[child], tasks[child].owner != program.priority, child))
    assert all(finish)
    elapsed = max(finish)
    # Transfer prices retain the prior IDD full-row amortization. The
    # command ledger separately reports the actual row/refresh activity.
    energy = (counts["r"] * round(macro["read_nj"] * 1e9)
              + counts["w"] * round(macro["write_nj"] * 1e9)
              + counts["local_read"] * round(local["read_nj"] * 1e9)
              + counts["local_write"] * round(local["write_nj"] * 1e9)
              + counts["ddr_read"] * hw.ddr_read_aj + counts["ddr_write"] * hw.ddr_write_aj
              + counts["alu"] * 84_000)
    standby = round(hw.standby_mw(macros) * elapsed * 1000)
    return {"edp": (energy + standby) * elapsed, "elapsed_ps": elapsed, "dynamic_aj": energy,
            "standby_aj": standby, "actions": dict(counts), "commands": ddr.counts,
            "trace": (intervals, finish, ddr.trace) if record else None}
