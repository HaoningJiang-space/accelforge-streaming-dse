"""Replay serving traces by physical word, separately from the dispatcher."""

from collections import Counter, defaultdict
from itertools import pairwise
from math import ceil

from research.physical_cost.banked_oracle import addresses
from research.physical_cost.serving_ddr_oracle import check


def verify(program, work, result, device, macros):
    intervals, finish, commands = result["trace"]
    hw = program.hardware
    macro, local = macros[hw.global_bank_bytes], macros[hw.weight_bytes_per_stripe]
    period = 1000 * ceil(max(macro["cycle_ns"], macro["access_ns"]))
    bursts = check(commands, device)
    queues = defaultdict(list)
    for line, op, start, stop in bursts:
        queues[line, op].append((start, stop))
    occupied, bounds = {}, {}
    for name, region in program.regions.items():
        locs = set(addresses(region, 0, region.words))
        assert len(locs) == region.words
        assert all(0 <= bank < hw.global_banks and 0 <= row < hw.global_capacity // 64
                   and (bank, row) not in occupied for bank, row in locs)
        occupied.update(dict.fromkeys(locs, name))
        bounds[name] = locs

    ready = [max(task.release, *(finish[p] for p in task.deps)) if task.deps else task.release
             for task in program.tasks]
    ends = [0] * len(program.tasks)
    ports, cells = defaultdict(list), defaultdict(list)
    observed = Counter()
    memory, main_memory = [], []
    scans = defaultdict(Counter)
    step_by_task = {}
    expected_accesses = Counter()
    for i, task in enumerate(program.tasks):
        for a in task.accesses:
            region = program.regions[a.slot]
            for j, (bank, row) in enumerate(addresses(region, a.first, a.words)):
                dram = None if task.dram_line is None else task.dram_line + j
                expected_accesses[i, task.direction, bank, row, (a.value, a.offset + j), dram] += 1
        if task.label in ("QK:read", "AV and merge:read"):
            tag = task.accesses[0].value
            step_by_task[i] = tag[2]
    for begin, end, i, direction, bank, row, value, dram in intervals:
        assert begin >= ready[i] and begin < end <= finish[i]
        port = (direction, bank)
        ports[port].append((begin, end, i))
        ends[i] = max(ends[i], end)
        if direction == "core":
            task = program.tasks[i]
            assert end - begin == task.cycles * 1000
            observed.update({"alu": task.alu, "local_read": task.local_read, "local_write": task.local_write})
            continue
        assert end - begin == period
        coord = bank, row
        assert coord in occupied
        assert any(coord in bounds[a.slot] for a in program.tasks[i].accesses)
        expected_accesses[i, direction, bank, row, value, dram] -= 1
        observed[direction] += 1
        cells[coord].append((begin, end))
        memory.append((end if direction == "w" else begin, direction == "r", coord, value, end, i))
        tag, offset = value
        if i in step_by_task and tag[0] in ("k", "v"):
            scans[program.tasks[i].owner, step_by_task[i], tag[0]][offset] += 1
        if dram is not None:
            op = "RD" if direction == "w" else "WR"
            burst = queues[dram, op].pop(0)
            if direction == "w":
                assert burst[1] == begin
            else:
                assert end <= burst[0]
                ends[i] = max(ends[i], burst[1])
            main_memory.append((burst[1], op == "RD", dram, value))
            observed["ddr_read" if op == "RD" else "ddr_write"] += 1
    assert ends == finish and all(not q for q in queues.values())
    assert all(n == 0 for n in expected_accesses.values())
    assert max(ends) == result["elapsed_ps"]
    assert all(result["actions"].get(k, 0) == v for k, v in observed.items())
    prices = {"r": round(macro["read_nj"] * 1e9), "w": round(macro["write_nj"] * 1e9),
              "local_read": round(local["read_nj"] * 1e9), "local_write": round(local["write_nj"] * 1e9),
              "ddr_read": hw.ddr_read_aj, "ddr_write": hw.ddr_write_aj, "alu": 84_000}
    energy = sum(prices[k] * n for k, n in observed.items())
    standby = round(hw.standby_mw(macros) * max(ends) * 1000)
    assert (energy, standby, (energy + standby) * max(ends)) == (
        result["dynamic_aj"], result["standby_aj"], result["edp"],
    )
    for request, context in enumerate(work.contexts, 1):
        for step in range(work.steps):
            expected = Counter(range(context + step + 1))
            assert scans[request, step, "k"] == expected
            assert scans[request, step, "v"] == expected

    waits = 0
    for port, slots in ports.items():
        slots.sort()
        for (_, done, prev), (start, _, nxt) in pairwise(slots):
            assert done <= start, (port, prev, nxt)
            if (port[0] != "core" and program.tasks[nxt].dram_line is None
                    and ready[nxt] < done and program.tasks[prev].owner != program.tasks[nxt].owner):
                waits += 1
    for spans in cells.values():
        assert all(a[1] <= b[0] for a, b in pairwise(sorted(spans)))
    version = {}
    last = {}
    for time, read, loc, value, stop, i in sorted(memory):
        if read:
            stored, born = version[loc]
            assert stored == value, (program.tasks[i].label, loc, value, stored)
            last[loc, born] = stop
        else:
            version[loc] = value, time
    persisted = {}
    for _, read, line, value in sorted(main_memory):
        (kind, *owner), token = value
        if read and kind in ("k", "v"):
            req, = owner
            assert line == (req << 16) + (0 if kind == "k" else 1 << 14) + token
            if token >= work.contexts[req - 1]:
                assert persisted[line] == value
        elif not read:
            persisted[line] = value
    for req, context in enumerate(work.contexts, 1):
        for kind in ("k", "v"):
            base = (req << 16) + (0 if kind == "k" else 1 << 14)
            assert all(persisted[base + t] == ((kind, req), t) for t in range(context, context + work.steps))

    events = []
    for (loc, born), stop in last.items():
        name = occupied[loc]
        group = "p" if name.startswith(("px", "py")) else "kv" if name.startswith(("k", "v")) else "other"
        # Ignore cold tile staging in the persistent-cache overlap statistic.
        if group == "kv" and program.regions[name].words < work.contexts[int(name[-1]) - 1] + work.steps:
            group = "other"
        events.extend(((born, 1, group, loc), (stop, -1, group, loc)))
    active, live, peak = Counter(), set(), 0
    overlap = previous = 0
    for time, delta, group, loc in sorted(events):
        if active["p"] and active["kv"]:
            overlap += time - previous
        previous = time
        if delta == 1:
            assert loc not in live
            live.add(loc)
        else:
            live.remove(loc)
        active[group] += delta
        peak = max(peak, len(live))
    first = next((entry[2] for entry in bursts if entry[1] == "RD"), None)
    bank_busy = {direction: [sum(end - start for start, end, _ in ports[direction, bank])
                             for bank in range(hw.global_banks)] for direction in ("r", "w")}
    completions = [max(end for task, end in zip(program.tasks, finish, strict=True) if task.owner == owner)
                   for owner in range(3)]
    return {"ddr_bursts": len(bursts), "first_data_ps": first, "peak_live_bytes": peak * 64,
            "reserved_bank_bytes": [n * 64 for n in program.used],
            "bank_busy_ps": bank_busy, "completion_by_request_ps": completions,
            "prefill_kv_overlap_ps": overlap, "cross_request_port_waits": waits}
