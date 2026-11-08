"""Independent word-address and lifetime replay for a scheduled serving plan."""

from collections import Counter, defaultdict
from itertools import product
from math import ceil


def addresses(region, offset, length):
    for word in range(offset, offset + length):
        lane = word % len(region.order)
        yield region.order[lane], region.starts[lane] + word // len(region.order)


def audit(program, macros, starts, *, standalone=None):
    """Check each physical word and reconstruct service and energy from scratch."""
    hw, work, plan = program.hardware, program.workload, program.mapping
    if len(starts) != len(program.commands) or min(starts) < 0:
        raise AssertionError("Missing or invalid command starts")
    bank_cap = hw.global_bank_bytes // 64
    g, l = macros[hw.global_bank_bytes], macros[hw.weight_bytes_per_stripe]
    global_period = max(ceil(g["access_ns"]), ceil(g["cycle_ns"]))
    local_period = max(ceil(l["access_ns"]), ceil(l["cycle_ns"]))
    per_word = {
        "r": round(g["read_nj"] * 10**9),
        "w": round(g["write_nj"] * 10**9),
    }
    intervals = defaultdict(list)
    movements, trace, completion = Counter(), [], []
    dynamic = 0

    def book(port, start, finish):
        intervals[port].append((start, finish))

    for i, command in enumerate(program.commands):
        start = starts[i]
        per_port = Counter()
        for access in command.accesses:
            region = program.regions[access.slot]
            if not 0 <= access.first < access.first + access.words <= region.words:
                raise AssertionError("Access outside its logical buffer")
            for bank, row in addresses(region, access.first, access.words):
                if access.bank is not None and bank != access.bank:
                    continue
                if not 0 <= row < bank_cap:
                    raise AssertionError("Access outside physical SRAM")
                port = (bank, access.direction)
                step = max(global_period, 2) if command.kind == "dma" else global_period
                tick = start + per_port[port]
                per_port[port] += step
                trace.append((tick, access.direction == "w", bank, row, access.slot, i, step))
                movements[command.request, access.direction] += 1
                dynamic += per_word[access.direction]
                if command.kind == "dma":
                    if access.bank is None:
                        raise AssertionError("DMA must name one physical bank")
                    per_port["DDR"] += step
                    dynamic += 3_599_360_000
                    movements[command.request, "dram"] += 1
        if command.kind == "load":
            # The read is followed by the transfer into private weight SRAM.
            per_port["LW"] = max(per_port.values()) + command.local_peak * local_period
            dynamic += round(l["write_nj"] * 10**9) * command.local_words
            movements[command.request, "local_write"] += command.local_words
        if command.kind == "mac":
            per_port["LR"] = command.local_peak * local_period
            per_port["MAC"] = command.cycles + per_port["LR"]
            dynamic += round(l["read_nj"] * 10**9) * command.local_words + 84_000 * command.macs
            movements[command.request, "local_read"] += command.local_words
            movements[command.request, "macs"] += command.macs
        for port, ticks in per_port.items():
            book(port, start, start + ticks)
        completion.append(start + max(per_port.values()))

    for i, command in enumerate(program.commands):
        if any(completion[parent] > starts[i] for parent in command.after):
            raise AssertionError("A command starts before its producer completes")
    for port, slots in intervals.items():
        if any(first[1] > second[0] for first, second in zip(sorted(slots), sorted(slots)[1:])):
            raise AssertionError(f"Port conflict on {port}")

    lifetimes, endpoints = defaultdict(list), []
    for life in program.lives:
        begin, end = starts[life.first], completion[life.last]
        region = program.regions[life.slot]
        if end <= begin:
            raise AssertionError("Invalid buffer lifetime")
        location = frozenset(addresses(region, 0, region.words))
        if len(location) != region.words or any(not 0 <= row < bank_cap for _, row in location):
            raise AssertionError("Buffer aliases itself or exceeds a physical bank")
        version = len(lifetimes[life.slot])
        lifetimes[life.slot].append((begin, end, version))
        endpoints.extend(((begin, 1, life.slot, location), (end, 0, life.slot, location)))

    active, live_addresses = {}, set()
    peak = co_resident = 0
    peak_banks = [0] * hw.global_banks
    previous = 0
    for tick, reserve, slot, location in sorted(endpoints, key=lambda item: item[:3]):
        if "KV" in active and any(name.startswith("P") for name in active):
            co_resident += tick - previous
        previous = tick
        if reserve:
            if slot in active or live_addresses & location:
                raise AssertionError("Overlapping live SRAM allocations")
            active[slot] = location
            live_addresses.update(location)
            usage = Counter(bank for bank, _ in live_addresses)
            if max(usage.values()) > bank_cap:
                raise AssertionError("Live data exceeds a bank capacity")
            peak = max(peak, len(live_addresses))
            for bank in usage:
                peak_banks[bank] = max(peak_banks[bank], usage[bank])
        else:
            if active.pop(slot) != location:
                raise AssertionError("Incorrect release")
            live_addresses.difference_update(location)

    known, address_busy = {}, {}
    for tick, write, bank, row, slot, index, step in sorted(trace):
        matching = [version for first, last, version in lifetimes[slot]
                    if first <= tick and completion[index] <= last]
        if len(matching) != 1:
            raise AssertionError("Access outside a live allocation")
        version = (slot, matching[0])
        address = (bank, row)
        opposite_end = address_busy.get((address, not write), 0)
        if opposite_end > tick:
            raise AssertionError("Simultaneous read and write of the same physical word")
        address_busy[address, write] = tick + step
        if write:
            known[address] = (version, tick + step)
        elif address not in known or known[address][0] != version or known[address][1] > tick:
            raise AssertionError("Read before write or stale slot contents")

    def words(bytes_):
        return (bytes_ + 63) // 64

    expected = Counter()
    phases = []
    if standalone != "D":
        phases.extend(("P", min(plan.rows, work.rows - row), work.inner,
                       min(plan.columns, work.columns - col), False)
                      for row, col in product(range(0, work.rows, plan.rows),
                                              range(0, work.columns, plan.columns)))
    if standalone != "P":
        phases.extend(("D", 1, work.head, min(work.decode_tile, work.context - col), plan.resident)
                      for _, col in product(range(work.steps), range(0, work.context, work.decode_tile)))
        if plan.resident:
            expected["D", "dram"] += words(work.context * work.head)
            expected["D", "w"] += words(work.context * work.head)
    private_words = Counter()
    for request, rows, inner, columns, cached in phases:
        input_words, weights, output = words(rows * inner), words(inner * columns), words(rows * columns)
        x = hw.x
        stripe_words = [(inner * count + 7) // 8 for count in Counter(c % x for c in range(columns)).values()]
        local = sum(stripe_words)
        private_words[request] = max(private_words[request], max(stripe_words))
        expected[request, "macs"] += rows * inner * columns
        expected[request, "dram"] += input_words + output + (0 if cached else weights)
        expected[request, "w"] += input_words + output + (0 if cached else weights)
        expected[request, "r"] += input_words + weights + output
        expected[request, "local_read"] += local
        expected[request, "local_write"] += local
    if movements != expected:
        raise AssertionError("Word and MAC totals differ from independent tile arithmetic")
    if sum(private_words.values()) * 8 > hw.weight_bytes_per_stripe:
        raise AssertionError("The two private SRAM slots exceed a stripe capacity")

    if standalone is None and plan.resident:
        prefill_start = min(begin for slot, lives in lifetimes.items() if slot.startswith("P")
                            for begin, _, _ in lives)
        reads_kv = [tick for tick, write, _, _, slot, _, _ in trace if slot == "KV" and not write]
        if not (co_resident and min(reads_kv) < prefill_start <= max(reads_kv)):
            raise AssertionError("The running decoder must read KV before and during the prefill lifetime")

    # Exact intersection of the occupied read and write intervals on each bank.
    rw_overlap = 0
    for bank in range(hw.global_banks):
        reads, writes = sorted(intervals[bank, "r"]), sorted(intervals[bank, "w"])
        i = j = 0
        while i < len(reads) and j < len(writes):
            a, b = reads[i], writes[j]
            rw_overlap += max(0, min(a[1], b[1]) - max(a[0], b[0]))
            if a[1] <= b[1]:
                i += 1
            else:
                j += 1
    ticks = max(completion)
    leak_mw = sum(macros[size]["leak_mw"] * n for size, n in (
        (hw.global_bank_bytes, hw.global_banks), (hw.weight_bytes_per_stripe, hw.x),
    ))
    return {
        "ns": ticks,
        "dynamic_aj": dynamic,
        "edp": (dynamic + round(leak_mw * 10**6) * ticks) * ticks,
        "peak_bytes": peak * 64,
        "peak_bank_bytes": [count * 64 for count in peak_banks],
        "reserved_private_bytes_per_stripe": sum(private_words.values()) * 8,
        "kv_prefill_co_resident_ns": co_resident,
        "same_bank_read_write_overlap_ns": rw_overlap,
        "words": {f"{request}/{kind}": count for (request, kind), count in sorted(movements.items())},
    }
