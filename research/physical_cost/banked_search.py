"""Compare shared-SRAM searches with the same cold wall-clock budgets."""

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, replace
import gzip
from itertools import product
import json
from math import ceil
from pathlib import Path
from time import perf_counter

from research.physical_cost.banked_oracle import audit
from research.physical_cost.banked_serving import (
    DRAM_AJ, DRAM_NS, MAC_AJ, Mapping, Workload, build, dispatch, mappings, place, price, tile_words,
)
from research.physical_cost.mixed_gate import Architecture, GB_BANKS, GB_BYTES, LOCAL_BYTES, REFERENCE, SHAPES
from research.runtime.strip_codesign import ceildiv
from research.runtime.strip_native_timing import shape_classes


CASES = {
    "context768": Workload(context=768),
    "context1024": Workload(),
    "context1536": Workload(rows=80, context=1536, steps=12),
}
DEADLINES = (0.1, 0.5, 2.0, 8.0)


def estimate(hw, work, mapping, macros):
    """Bound by bank service, decoder serialization, and prefill admission."""
    regions = place(hw, work, mapping)
    if regions is None:
        return None
    g, l = macros[hw.global_bank_bytes], macros[hw.weight_bytes_per_stripe]
    gc = ceil(max(g["access_ns"], g["cycle_ns"]))
    lc = ceil(max(l["access_ns"], l["cycle_ns"]))
    dma_ns = max(DRAM_NS, gc)
    leak = round(hw.sram_totals(macros, "leak_mw") * 1e6)
    resources = Counter()
    traffic = Counter()
    dynamic = 0

    def moves(request, slot, start, count, direction, repeats, dma=False):
        duration = 0
        period = dma_ns if dma else gc
        for bank, words in regions[slot].counts(start, count):
            resources[request, bank, direction] += words * period * repeats
            duration = max(duration, words * period)
        traffic[direction] += count * repeats
        if dma:
            resources[request, "dram", "both"] += count * dma_ns * repeats
            traffic["dram"] += count * repeats
            return count * dma_ns
        return duration

    def kernel(request, slot, r, k, n, repeats, kv_offset=None):
        xw, ww, ow = tile_words(r, k, n)
        staged = xw if kv_offset is not None else xw + ww
        peak = ceildiv(k * ceildiv(n, hw.x), 8)
        full_stripes = n % hw.x
        short_words = ceildiv(k * (n // hw.x), 8)
        long_words = ceildiv(k * (n // hw.x + 1), 8)
        local = full_stripes * long_words + (hw.x - full_stripes) * short_words
        incoming = moves(request, slot, 0, staged, "w", repeats, True)
        load = moves(request, slot, 0, staged, "r", repeats)
        if kv_offset is not None:
            # The sum of accesses to each bank is tracked exactly. The shorter
            # of the combined service bounds is sufficient for the chain bound.
            load = max(load, moves(request, "KV", kv_offset, ww, "r", repeats))
        load += peak * lc
        mac = peak * lc + r * ceildiv(k, hw.y) * ceildiv(n, hw.x)
        resources[request, "LW", "w"] += load * repeats
        resources[request, "LR", "r"] += peak * lc * repeats
        resources[request, "MAC", "both"] += mac * repeats
        output = moves(request, slot, staged, ow, "w", repeats)
        drain = moves(request, slot, staged, ow, "r", repeats, True)
        traffic["local"] += local * repeats
        traffic["macs"] += r * k * n * repeats
        return incoming + load + mac + output + drain

    first_decode = 0
    if mapping.resident:
        first_decode += moves("D", "KV", 0, ceildiv(work.context * work.head, 64), "w", 1, True)
    one_step = 0
    for col in range(0, work.context, work.decode_tile):
        n = min(work.decode_tile, work.context - col)
        one_step += kernel("D", "D", 1, work.head, n, work.steps,
                           col * work.head // 64 if mapping.resident else None)
    full_decode = first_decode + work.steps * one_step
    first_decode += one_step
    for (r, repeat_r), (n, repeat_n) in product(
        shape_classes(work.rows, mapping.rows), shape_classes(work.columns, mapping.columns),
    ):
        kernel("P", "P0", r, work.inner, n, repeat_r * repeat_n)

    pooled = Counter()
    p_service = 0
    for (request, port, direction), ticks in resources.items():
        pooled[port, direction] += ticks
        if request == "P":
            p_service = max(p_service, ticks)
    duration = max(full_decode, first_decode + p_service, max(pooled.values()))
    dynamic = (
        traffic["dram"] * DRAM_AJ + traffic["macs"] * MAC_AJ
        + sum(traffic[d] * round(g[f"{action}_nj"] * 1e9)
              for d, action in (("r", "read"), ("w", "write")))
        + traffic["local"] * sum(round(l[f"{action}_nj"] * 1e9) for action in ("read", "write"))
    )
    return (dynamic + leak * duration) * duration, dynamic


def phase_score(hw, work, macros):
    """Complete standalone mappings on this hardware before choosing any architecture."""
    phases = []
    for phase in ("P", "D"):
        if phase == "P":
            plans = (
                Mapping(r, n, d, False, layout, "P")
                for r, n, d, layout in product((8, 16, 32), (16, 32, 64, 128), (1, 2),
                                               ("striped", "separate", "shared"))
            )
        else:
            plans = (Mapping(8, 16, 1, cached, layout, "D")
                     for cached, layout in ((False, "striped"), (True, "striped"), (True, "separate")))
        options = []
        for mapping in plans:
            program = build(hw, work, mapping, standalone=phase)
            if program is not None:
                costs = price(program, macros)
                _, elapsed, _, _ = dispatch(program, costs)
                options.append((costs.dynamic + costs.leak * elapsed, elapsed))
        phases.append(options)
    return min((e1 + e2) * (t1 + t2) for (e1, t1), (e2, t2) in product(*phases))


def all_ties(scores):
    optimum = min(scores.values())
    return tuple(sorted(hw for hw, score in scores.items() if score == optimum))


def run_search(hardware, work, macros, method, deadlines=DEADLINES):
    start = perf_counter()
    incumbent = float("inf")
    history = []
    by_hw = defaultdict(list)
    considered = compiled = replayed = 0
    verification_s = 0.0
    best = None

    def replay(item):
        nonlocal compiled, replayed, incumbent, best, verification_s
        bound, hw, mapping, exact_dynamic = item
        program = build(hw, work, mapping)
        compiled += 1
        costs = price(program, macros)
        if costs.dynamic != exact_dynamic:
            raise AssertionError("Candidate bound miscounts dynamic energy")
        if max(bound, costs.lower) >= incumbent:
            return
        score, elapsed, times, waits = dispatch(program, costs)
        if score < bound:
            raise AssertionError("Co-resident bound exceeds actual EDP")
        replayed += 1
        if score < incumbent:
            t0 = perf_counter()
            verification = audit(program, macros, times)
            verification_s += perf_counter() - t0
            if verification["edp"] != score or verification["ns"] != elapsed:
                raise AssertionError("Independent addressed replay differs from the evaluator")
            incumbent = score
            best = (program, verification, waits)
            history.append((perf_counter() - start, score))

    # The same cold anchor is generated and charged in all runs.
    anchor = Mapping(16, 32, 1, False, "striped", "D")
    for hw in hardware:
        result = estimate(hw, work, anchor, macros)
        if result is not None:
            replay((result[0], hw, anchor, result[1]))
            break

    before_generation = perf_counter()
    for hw in hardware:
        estimates = {}
        for mapping in mappings():
            considered += 1
            key = replace(mapping, prefer="P")
            if key not in estimates:
                estimates[key] = estimate(hw, work, key, macros)
            result = estimates[key]
            if result is not None:
                by_hw[hw].append((result[0], hw, mapping, result[1]))
    generation = perf_counter() - before_generation
    by_hw = {hw: sorted(items) for hw, items in by_hw.items()}
    lower = {hw: items[0][0] for hw, items in by_hw.items()}
    selection_start = perf_counter()
    if method == "standalone":
        selected = all_ties({hw: phase_score(hw, work, macros) for hw in by_hw})
    elif method == "optimistic":
        selected = all_ties(lower)
    elif method == "near":
        minimum = min(lower.values())
        selected = tuple(sorted((hw for hw, cost in lower.items() if cost * 100 <= minimum * 102),
                                key=lambda hw: (lower[hw], hw)))
    else:
        selected = tuple(sorted(by_hw, key=lambda hw: (lower[hw], hw)))
    selection = perf_counter() - selection_start

    if method == "joint":
        for item in sorted(item for hw in selected for item in by_hw[hw]):
            if item[0] >= incumbent:
                break
            replay(item)
    else:
        for hw in selected:
            for item in by_hw[hw]:
                if item[0] >= incumbent:
                    break
                replay(item)
    elapsed = perf_counter() - start
    if best is None:
        raise ValueError("No legal schedule for the area and workload")
    program, verification, waits = best
    return {
        "seconds": elapsed,
        "generation_s": generation,
        "architecture_selection_s": selection,
        "verification_s": verification_s,
        "candidates_generated": sum(map(len, by_hw.values())),
        "candidates_considered": considered,
        "compiled": compiled,
        "scheduled": replayed,
        "architectures_selected": [asdict(hw) for hw in selected],
        "edp_aj_ns": incumbent,
        "winner": {"hardware": asdict(program.hardware), "mapping": asdict(program.mapping)},
        "replay": {**verification, "scheduler_bank_wait_ns": waits},
        "checkpoints": {str(t): min((edp for when, edp in history if when <= t), default=None)
                        for t in deadlines},
        "incumbents": history,
    }


def run(table, output, names, repeats):
    macros = {int(size): row for size, row in table["macros"].items()}
    limit = Architecture(*REFERENCE).sram_totals(macros, "area_mm2") * 1.5
    hardware = tuple(sorted(
        hw for hw in (Architecture(*shape, banks, gb, local)
                      for shape, banks, gb, local in product(SHAPES, GB_BANKS, GB_BYTES, LOCAL_BYTES))
        if hw.sram_totals(macros, "area_mm2") <= limit
    ))
    methods = ("joint", "standalone", "optimistic", "near", "sweep")
    report = {"area_mm2": limit, "hardware_points": len(hardware), "cases": {}}
    for name in names:
        work = CASES[name]
        runs = {method: [] for method in methods}
        for repeat in range(repeats):
            for method in methods[repeat % len(methods):] + methods[:repeat % len(methods)]:
                record = run_search(hardware, work, macros, method)
                runs[method].append(record)
                print(name, repeat, method, record["seconds"], record["edp_aj_ns"],
                      record["winner"], flush=True)
            if runs["joint"][-1]["edp_aj_ns"] != runs["sweep"][-1]["edp_aj_ns"]:
                raise AssertionError("The complete architecture sweep disagrees with joint search")
        report["cases"][name] = {"workload": asdict(work), "runs": runs}
        output.write_bytes(gzip.compress(json.dumps(report, indent=2).encode(), mtime=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    run(json.loads(args.table.read_text()), args.output, args.cases, args.repeats)


if __name__ == "__main__":
    main()
