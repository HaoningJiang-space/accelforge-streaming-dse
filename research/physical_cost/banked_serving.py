"""Addressed two-request schedules for the CACTI SRAM hierarchy."""

from collections import deque
from dataclasses import dataclass, replace
from itertools import product
from math import ceil

from research.runtime.strip_codesign import ceildiv


LINE = 64
LOCAL_WORD = 8
MAC_AJ = 84_000


@dataclass(frozen=True)
class Workload:
    rows: int = 64
    inner: int = 256
    columns: int = 256
    context: int = 1024
    head: int = 64
    steps: int = 8
    decode_tile: int = 256
    reserve_values: bool = False


@dataclass(frozen=True, order=True)
class Mapping:
    rows: int
    columns: int
    buffers: int
    resident: bool
    layout: str
    prefer: str
    pin_weights: bool = False


def mappings():
    layouts = ((False, "striped"), (True, "striped"), (True, "separate"), (True, "shared"))
    for rows, cols, depth, (resident, layout), pinned, prefer in product(
        (8, 16, 32), (16, 32, 64, 128), (1, 2), layouts, (False, True), ("P", "D"),
    ):
        yield Mapping(rows, cols, depth, resident, layout, prefer, pinned)


@dataclass(frozen=True)
class Region:
    order: tuple
    starts: tuple
    words: int

    def counts(self, start, words):
        lanes = len(self.order)
        stop = start + words
        return tuple((bank, (stop + lanes - 1 - lane) // lanes - (start + lanes - 1 - lane) // lanes)
                     for lane, bank in enumerate(self.order))


@dataclass(frozen=True)
class Access:
    slot: str
    first: int
    words: int
    direction: str
    bank: int | None = None


@dataclass(frozen=True)
class Command:
    request: str
    kind: str
    after: tuple
    accesses: tuple
    local_words: int = 0
    local_peak: int = 0
    macs: int = 0
    cycles: int = 0


@dataclass(frozen=True)
class Life:
    slot: str
    first: int
    last: int


@dataclass
class Program:
    hardware: object
    workload: Workload
    mapping: Mapping
    regions: dict
    commands: list
    lives: list


def tile_words(rows, k, n):
    return ceildiv(rows * k, LINE), ceildiv(k * n, LINE), ceildiv(rows * n, LINE)


def layout_requirements(hardware, work, mapping, standalone=None):
    banks = hardware.global_banks
    context_words = ceildiv(work.context * work.head, LINE)
    p_orders = {"striped": tuple(range(banks)), "separate": tuple(range(1, banks)), "shared": (0,)}
    p_order = p_orders[mapping.layout]
    d_order = tuple(range(banks))
    kv_order = d_order if mapping.layout == "striped" else (0,)
    decode_n = min(work.context, work.decode_tile)
    px, pw, po = tile_words(min(mapping.rows, work.rows), work.inner, min(mapping.columns, work.columns))
    p_words = px + po + (0 if mapping.pin_weights else pw)
    q_words, dw_words, do_words = tile_words(1, work.head, decode_n)
    d_words = q_words + do_words + (0 if mapping.resident else dw_words)
    local_p = work.inner * ceildiv(min(mapping.columns, work.columns), hardware.x)
    local_d = work.head * ceildiv(decode_n, hardware.x)
    private_bytes = (
        (ceildiv(local_p, LOCAL_WORD) * LOCAL_WORD if standalone != "D" else 0)
        + (ceildiv(local_d, LOCAL_WORD) * LOCAL_WORD if standalone != "P" else 0)
    )

    regions = {}
    cursors = [0] * banks

    def allocate(slot, words, order):
        region = Region(order, tuple(cursors[bank] for bank in order), words)
        for bank, count in region.counts(0, words):
            cursors[bank] += count
        regions[slot] = region

    if standalone != "P":
        if mapping.resident:
            allocate("KV", context_words, kv_order)
            if work.reserve_values:
                allocate("V", context_words, kv_order)
        allocate("D", d_words, d_order)
    if standalone != "D":
        if mapping.pin_weights:
            allocate("PW", pw, p_order)
        for i in range(mapping.buffers):
            allocate(f"P{i}", p_words, p_order)
    return regions, max(cursors) * LINE, private_bytes


def place(hardware, work, mapping, standalone=None):
    regions, bank_bytes, private_bytes = layout_requirements(hardware, work, mapping, standalone)
    if bank_bytes > hardware.global_capacity or private_bytes > hardware.private_capacity:
        return None
    return regions


def build(hardware, work, mapping, *, standalone=None):
    """Compile the declared blocked GEMM/GEMV mapping with fixed SRAM slots."""
    regions = place(hardware, work, mapping, standalone)
    if regions is None:
        return None
    if work.head * work.decode_tile % LINE or (standalone is None and work.steps < 2):
        raise ValueError("The serving grammar requires aligned KV cuts and at least two decode steps")
    commands, lives = [], []
    context_words = ceildiv(work.context * work.head, LINE)

    def add(request, kind, after=(), accesses=(), **work_items):
        index = len(commands)
        commands.append(Command(request, kind, tuple(dict.fromkeys(after)), tuple(accesses), **work_items))
        return index

    def dma(request, slot, first, words, direction, after):
        first_command = None
        for bank, count in regions[slot].counts(first, words):
            if count:
                index = add(request, "dma", after, (Access(slot, first, words, direction, bank),))
                after = (index,)
                if first_command is None:
                    first_command = index
        return first_command, after[0]

    def private_words(k, n):
        active = min(n, hardware.x)
        peak = ceildiv(k * ceildiv(n, hardware.x), LOCAL_WORD)
        words = sum(ceildiv(k * len(range(lane, n, hardware.x)), LOCAL_WORD) for lane in range(active))
        return words, peak

    def kernel(request, slot, shape, data, output, previous, kv=None, pinned=False):
        r, k, n = shape
        _, ww, ow = tile_words(r, k, n)
        words, peak = private_words(k, n)
        reads = (Access(slot, 0, data, "r"),)
        if kv is not None:
            reads += (Access("KV", kv, ww, "r"),)
        load = add(request, "load", previous, reads,
                   local_words=0 if pinned else words, local_peak=0 if pinned else peak)
        mac = add(request, "mac", (load,), local_words=words, local_peak=peak,
                  macs=r * k * n, cycles=r * ceildiv(k, hardware.y) * ceildiv(n, hardware.x))
        write = add(request, "write", (mac,), (Access(slot, output, ow, "w"),))
        _, last = dma(request, slot, output, ow, "r", (write,))
        return load, mac, last

    first_decode_end = second_decode_start = kv_start = last_kv_load = None
    if standalone != "P":
        prior = ()
        if mapping.resident:
            kv_start, kv_end = dma("D", "KV", 0, context_words, "w", ())
            prior = (kv_end,)
            if work.reserve_values:
                v_start, v_end = dma("D", "V", 0, context_words, "w", prior)
                prior = (v_end,)
        for step in range(work.steps):
            for col in range(0, work.context, work.decode_tile):
                n = min(work.decode_tile, work.context - col)
                xw, ww, _ = tile_words(1, work.head, n)
                staged = xw if mapping.resident else xw + ww
                first, loaded = dma("D", "D", 0, staged, "w", prior)
                if step == 1 and col == 0:
                    second_decode_start = first
                kv = col * work.head // LINE if mapping.resident else None
                load, _, last = kernel("D", "D", (1, work.head, n), staged, staged, (loaded,), kv)
                last_kv_load = load
                lives.append(Life("D", first, last))
                prior = (last,)
            if step == 0:
                first_decode_end = prior[0]
        if mapping.resident:
            lives.append(Life("KV", kv_start, last_kv_load))
            if work.reserve_values:
                # The later value contraction is outside this score window.
                # Keep the complete value tensor through the last decode step.
                lives.append(Life("V", v_start, prior[0]))

    p_first = p_previous_mac = None
    p_previous_dma = first_decode_end
    reuse = {}
    if standalone != "D":
        rows = range(0, work.rows, mapping.rows)
        cols = range(0, work.columns, mapping.columns)
        tiles = ((row, col) for col, row in product(cols, rows)) if mapping.pin_weights else product(rows, cols)
        p_weight_ready = None
        for i, (row, col) in enumerate(tiles):
            slot = f"P{i % mapping.buffers}"
            r = min(mapping.rows, work.rows - row)
            n = min(mapping.columns, work.columns - col)
            xw, ww, _ = tile_words(r, work.inner, n)
            if mapping.pin_weights and row == 0:
                dependency = tuple(x for x in (p_previous_dma, p_weight_ready) if x is not None)
                w_first, p_previous_dma = dma("P", "PW", 0, ww, "w", dependency)
                if p_first is None:
                    p_first = w_first
                predecessors = tuple(x for x in (p_previous_dma, p_previous_mac) if x is not None)
                words, peak = private_words(work.inner, n)
                p_weight_ready = add("P", "load", predecessors, (Access("PW", 0, ww, "r"),),
                                     local_words=words, local_peak=peak)
                lives.append(Life("PW", w_first, p_weight_ready))
            staged = xw if mapping.pin_weights else xw + ww
            dependencies = tuple(x for x in (p_previous_dma, reuse.get(slot)) if x is not None)
            first, p_previous_dma = dma("P", slot, 0, staged, "w", dependencies)
            if p_first is None:
                p_first = first
            predecessors = tuple(x for x in (p_previous_dma, p_previous_mac, p_weight_ready) if x is not None)
            _, p_previous_mac, last = kernel(
                "P", slot, (r, work.inner, n), staged, staged, predecessors, pinned=mapping.pin_weights,
            )
            reuse[slot] = last
            lives.append(Life(slot, first, last))

    if standalone is None and second_decode_start is not None:
        command = commands[second_decode_start]
        # Admit one prefill stage after the first decode step and before the second.
        first_prefill_fill = p_first
        commands[second_decode_start] = replace(command, after=command.after + (first_prefill_fill,))
    return Program(hardware, work, mapping, regions, commands, lives)


@dataclass
class Costs:
    resources: list
    durations: list
    dynamic: int
    leak: int
    graph: list
    indegrees: list
    lower: int
    lower_ns: int


def price(program, macros):
    hw = program.hardware
    g, l = macros[hw.global_bank_bytes], macros[hw.weight_bytes_per_stripe]
    g_cycle = ceil(max(g["access_ns"], g["cycle_ns"]))
    l_cycle = ceil(max(l["access_ns"], l["cycle_ns"]))
    global_aj = {d: round(g[f"{name}_nj"] * 1e9) for d, name in (("r", "read"), ("w", "write"))}
    local_aj = {d: round(l[f"{name}_nj"] * 1e9) for d, name in (("r", "read"), ("w", "write"))}
    leak = round(hw.standby_mw(macros) * 1e6)
    ports, duration, dynamic = [], [], 0
    work = [0] * (2 * hw.global_banks + 4)
    dram, local_r, local_w, mac = range(2 * hw.global_banks, len(work))
    graph = [[] for _ in program.commands]
    indegrees = []
    for i, command in enumerate(program.commands):
        used = {}
        for access in command.accesses:
            for bank, count in program.regions[access.slot].counts(access.first, access.words):
                if count and (access.bank is None or access.bank == bank):
                    port = 2 * bank + (access.direction == "w")
                    elapsed = count * g_cycle
                    if command.kind == "dma":
                        elapsed = count * max(hw.ddr_word_ns, g_cycle)
                        used[dram] = used.get(dram, 0) + elapsed
                        # Writing to the SRAM endpoint reads the off-chip device.
                        dynamic += count * (hw.ddr_read_aj if access.direction == "w" else hw.ddr_write_aj)
                    used[port] = used.get(port, 0) + elapsed
                    dynamic += count * global_aj[access.direction]
        if command.kind == "load" and command.local_words:
            used[local_w] = max(used.values()) + command.local_peak * l_cycle
            dynamic += command.local_words * local_aj["w"]
        if command.kind == "mac":
            used[local_r] = command.local_peak * l_cycle
            used[mac] = used[local_r] + command.cycles
            dynamic += command.local_words * local_aj["r"] + command.macs * MAC_AJ
        ports.append(tuple(used.items()))
        duration.append(max(used.values()))
        for port, ticks in used.items():
            work[port] += ticks
        indegrees.append(len(command.after))
        for before in command.after:
            graph[before].append(i)
    unmet = indegrees.copy()
    available = deque(i for i, count in enumerate(unmet) if count == 0)
    end = [0] * len(duration)
    seen = 0
    while available:
        i = available.popleft()
        end[i] += duration[i]
        seen += 1
        for j in graph[i]:
            end[j] = max(end[j], end[i])
            unmet[j] -= 1
            if not unmet[j]:
                available.append(j)
    if seen != len(end):
        raise AssertionError("Cyclic command dependencies")
    latency = max(max(work), max(end))
    return Costs(ports, duration, dynamic, leak, graph, indegrees,
                 (dynamic + leak * latency) * latency, latency)


def dispatch(program, costs):
    """Schedule the earliest ready command and break ties by the declared policy."""
    unmet = costs.indegrees.copy()
    ready = [i for i, count in enumerate(unmet) if not count]
    earliest = [0] * len(unmet)
    starts = [0] * len(unmet)
    end = [0] * (2 * program.hardware.global_banks + 4)
    bank_wait = 0
    prefer = program.mapping.prefer
    while ready:
        def key(i):
            return (max(earliest[i], *(end[port] for port, _ in costs.resources[i])),
                    program.commands[i].request != prefer, i)

        index = min(ready, key=key)
        ready.remove(index)
        start = key(index)[0]
        floor = max(earliest[index], *(end[p] if p >= len(end) - 4 else 0
                                        for p, _ in costs.resources[index]))
        bank_wait += max(0, start - floor)
        starts[index] = start
        finish = start + costs.durations[index]
        for port, ticks in costs.resources[index]:
            end[port] = start + ticks
        for follower in costs.graph[index]:
            earliest[follower] = max(earliest[follower], finish)
            unmet[follower] -= 1
            if not unmet[follower]:
                ready.append(follower)
    elapsed = max(end)
    edp = (costs.dynamic + costs.leak * elapsed) * elapsed
    if edp < costs.lower:
        raise AssertionError("Resource lower bound exceeds replay")
    return edp, elapsed, starts, bank_wait
