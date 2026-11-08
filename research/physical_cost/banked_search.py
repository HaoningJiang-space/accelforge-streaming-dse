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
    MAC_AJ, Mapping, Workload, build, dispatch, layout_requirements,
    mappings, place, price, tile_words,
)
from research.physical_cost.mixed_gate import Architecture, GB_BANKS, GB_BYTES, LOCAL_BYTES, REFERENCE, SHAPES
from research.runtime.strip_codesign import ceildiv
from research.runtime.strip_native_timing import shape_classes


CASES = {
    "context512": Workload(context=512),
    "context768": Workload(context=768),
    "context1024": Workload(),
    "context1536": Workload(rows=80, context=1536, steps=12),
    "asymmetric": Workload(rows=93, inner=192, columns=320, context=1152, head=80, steps=12),
    "decode_heavy": Workload(rows=32, context=640, steps=16),
    "prefill_heavy": Workload(rows=128, context=640, steps=4),
    "holdout448": Workload(context=448),
    "holdout576": Workload(context=576),
    "holdout704": Workload(context=704),
    "kv256": Workload(context=256, reserve_values=True),
    "kv384": Workload(context=384, reserve_values=True),
    "kv512": Workload(context=512, reserve_values=True),
}
DEADLINES = (0.1, 0.5, 2.0, 8.0)
METHODS = ("binding", "joint", "standalone", "optimistic", "near", "sweep", "grouped_sweep",
           "wide", "top_two", "critical_joint", "critical_first", "critical_two")
CRITICAL_PROBES = 4


def estimate(hw, work, mapping, macros, regions=None):
    """Bound by bank service, decoder serialization, and prefill admission."""
    if regions is None:
        regions = place(hw, work, mapping)
    if regions is None:
        return None
    g, l = macros[hw.global_bank_bytes], macros[hw.weight_bytes_per_stripe]
    gc = ceil(max(g["access_ns"], g["cycle_ns"]))
    lc = ceil(max(l["access_ns"], l["cycle_ns"]))
    duration, traffic = bound_profile(hw, work, mapping, regions, gc, lc)
    return bind_profile(duration, traffic, action_prices(hw, g, l), round(hw.standby_mw(macros) * 1e6))


def action_prices(hw, global_macro, local_macro):
    return (hw.ddr_read_aj, hw.ddr_write_aj, MAC_AJ, *(round(m[f"{action}_nj"] * 1e9)
            for m in (global_macro, local_macro) for action in ("read", "write")))


def bind_profile(duration, traffic, prices, leak):
    dynamic = sum(count * price for count, price in zip(traffic, prices, strict=True))
    return (dynamic + leak * duration) * duration, dynamic


def bound_profile(hw, work, mapping, regions, gc, lc):
    dma_ns = max(hw.ddr_word_ns, gc)
    resources = Counter()
    traffic = Counter()

    def moves(request, slot, start, count, direction, repeats, dma=False):
        duration = 0
        period = dma_ns if dma else gc
        for bank, words in regions[slot].counts(start, count):
            resources[request, bank, direction] += words * period * repeats
            duration = max(duration, words * period)
        traffic[direction] += count * repeats
        if dma:
            resources[request, "dram", "both"] += count * dma_ns * repeats
            traffic["dram_r" if direction == "w" else "dram_w"] += count * repeats
            return count * dma_ns
        return duration

    def local_words(k, n):
        full_stripes = n % hw.x
        short_words = ceildiv(k * (n // hw.x), 8)
        long_words = ceildiv(k * (n // hw.x + 1), 8)
        local = full_stripes * long_words + (hw.x - full_stripes) * short_words
        return local, ceildiv(k * ceildiv(n, hw.x), 8)

    def kernel(request, slot, r, k, n, repeats, kv_offset=None, pinned=False):
        xw, ww, ow = tile_words(r, k, n)
        staged = xw if kv_offset is not None or pinned else xw + ww
        local, peak = local_words(k, n)
        incoming = moves(request, slot, 0, staged, "w", repeats, True)
        load = moves(request, slot, 0, staged, "r", repeats)
        if kv_offset is not None:
            # The sum of accesses to each bank is tracked exactly. The shorter
            # of the combined service bounds is sufficient for the chain bound.
            load = max(load, moves(request, "KV", kv_offset, ww, "r", repeats))
        if not pinned:
            load += peak * lc
            resources[request, "LW", "w"] += load * repeats
            traffic["local_w"] += local * repeats
        mac = peak * lc + r * ceildiv(k, hw.y) * ceildiv(n, hw.x)
        resources[request, "LR", "r"] += peak * lc * repeats
        resources[request, "MAC", "both"] += mac * repeats
        output = moves(request, slot, staged, ow, "w", repeats)
        drain = moves(request, slot, staged, ow, "r", repeats, True)
        traffic["local_r"] += local * repeats
        traffic["macs"] += r * k * n * repeats
        return incoming + load + mac + output + drain

    first_decode = 0
    if mapping.resident:
        first_decode += moves("D", "KV", 0, ceildiv(work.context * work.head, 64), "w", 1, True)
        if work.reserve_values:
            first_decode += moves("D", "V", 0, ceildiv(work.context * work.head, 64), "w", 1, True)
    one_step = 0
    for col in range(0, work.context, work.decode_tile):
        n = min(work.decode_tile, work.context - col)
        one_step += kernel("D", "D", 1, work.head, n, work.steps,
                           col * work.head // 64 if mapping.resident else None)
    full_decode = first_decode + work.steps * one_step
    first_decode += one_step
    for n, repeat_n in shape_classes(work.columns, mapping.columns):
        if mapping.pin_weights:
            ww = ceildiv(work.inner * n, 64)
            local, peak = local_words(work.inner, n)
            moves("P", "PW", 0, ww, "w", repeat_n, True)
            load = moves("P", "PW", 0, ww, "r", repeat_n)
            resources["P", "LW", "w"] += (load + peak * lc) * repeat_n
            traffic["local_w"] += local * repeat_n
        for r, repeat_r in shape_classes(work.rows, mapping.rows):
            kernel("P", "P0", r, work.inner, n, repeat_r * repeat_n, pinned=mapping.pin_weights)

    pooled = Counter()
    p_service = 0
    for (request, port, direction), ticks in resources.items():
        pooled[port, direction] += ticks
        if request == "P":
            p_service = max(p_service, ticks)
    duration = max(full_decode, first_decode + p_service, max(pooled.values()))
    return duration, tuple(traffic[key] for key in ("dram_r", "dram_w", "macs", "r", "w", "local_r", "local_w"))


def phase_score(hw, work, macros):
    """Complete standalone mappings on this hardware before choosing any architecture."""
    phases = []
    for phase in ("P", "D"):
        if phase == "P":
            plans = (
                Mapping(r, n, d, False, layout, "P", pin)
                for r, n, d, layout, pin in product((8, 16, 32), (16, 32, 64, 128), (1, 2),
                                                    ("striped", "separate", "shared"), (False, True))
            )
        else:
            plans = (Mapping(8, 16, 1, cached, layout, "D")
                     for cached, layout in ((False, "striped"), (True, "striped"), (True, "separate"))
                     if cached or not work.reserve_values)
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


def shortlist(scores, *, percent=None, count=None):
    ordered = sorted(scores, key=lambda hw: (scores[hw], hw))
    if percent is not None:
        cutoff = scores[ordered[0]] * (100 + percent)
        return tuple(hw for hw in ordered if scores[hw] * 100 <= cutoff)
    cutoff = scores[ordered[min(count, len(ordered)) - 1]]
    return tuple(hw for hw in ordered if scores[hw] <= cutoff)


def bind_candidates(hardware, work, plans, macros):
    """Reuse addressed layouts, excluding only cost-dominated equal-service mappings."""
    groups = defaultdict(list)
    prices = {}
    for hw in hardware:
        g, l = macros[hw.global_bank_bytes], macros[hw.weight_bytes_per_stripe]
        service = tuple(ceil(max(m["access_ns"], m["cycle_ns"])) for m in (g, l))
        groups[hw.x, hw.y, hw.global_banks, *service, max(hw.ddr_word_ns, service[0])].append(hw)
        prices[hw] = (*action_prices(hw, g, l), round(hw.standby_mw(macros) * 1e6))
    by_hw = defaultdict(list)
    feasible = 0
    for members in groups.values():
        dominates = {hw: {
            other for other in members if other != hw
            and (prices[other] != prices[hw] or other < hw)
            and all(a <= b for a, b in zip(prices[other], prices[hw], strict=True))
        } for hw in members}
        for mapping in plans:
            regions, gb_needed, private_needed = layout_requirements(members[0], work, mapping)
            admitted = {hw for hw in members if hw.global_capacity >= gb_needed
                        and hw.private_capacity >= private_needed}
            feasible += 2 * len(admitted)
            for hw in sorted(admitted):
                if admitted & dominates[hw]:
                    continue
                bound, dynamic = estimate(hw, work, mapping, macros, regions)
                for prefer in ("P", "D"):
                    by_hw[hw].append((bound, hw, replace(mapping, prefer=prefer), dynamic))
    return by_hw, feasible


def refine_candidates(by_hw, work, macros):
    """Compile a fixed number of distinct layouts at each architecture.

    The score over this shortlist ranks architectures only. Each per-mapping
    bound can safely replace its cheaper bound, including for exact search.
    """
    rankings, compiled = {}, {}
    for hw, items in by_hw.items():
        probes = [item for item in items if item[2].prefer == "P"][:CRITICAL_PROBES]
        values = {}
        for bound, _, mapping, dynamic in probes:
            program = build(hw, work, mapping)
            costs = price(program, macros)
            if dynamic != costs.dynamic:
                raise AssertionError("Critical-path probe changed the dynamic action count")
            values[mapping] = max(bound, costs.lower)
            compiled[hw, mapping] = program, costs
        rankings[hw] = min(values.values())
        by_hw[hw] = sorted((values.get(replace(mapping, prefer="P"), bound), hw, mapping, dynamic)
                           for bound, _, mapping, dynamic in items)
    return rankings, compiled


def run_search(hardware, work, macros, method, deadlines=DEADLINES):
    start = perf_counter()
    incumbent = float("inf")
    history = []
    by_hw = defaultdict(list)
    considered = compiled = replayed = 0
    verification_s = 0.0
    best = None
    probes = {}

    def replay(item):
        nonlocal compiled, replayed, incumbent, best, verification_s
        bound, hw, mapping, exact_dynamic = item
        previous = probes.get((hw, replace(mapping, prefer="P"))) if probes else None
        if previous is None:
            program = build(hw, work, mapping)
            costs = price(program, macros)
            compiled += 1
        else:
            program, costs = previous
            program = replace(program, mapping=mapping)
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
    anchor = Mapping(16, 32, 1, work.reserve_values, "striped", "D")
    for hw in hardware:
        result = estimate(hw, work, anchor, macros)
        if result is not None:
            replay((result[0], hw, anchor, result[1]))
            break

    before_generation = perf_counter()
    plans = tuple(mapping for mapping in mappings()
                  if mapping.prefer == "P" and (mapping.resident or not work.reserve_values))
    considered = 2 * len(plans) * len(hardware)
    if method in ("binding", "grouped_sweep"):
        by_hw, feasible = bind_candidates(hardware, work, plans, macros)
    else:
        for hw in hardware:
            for mapping in plans:
                result = estimate(hw, work, mapping, macros)
                if result is not None:
                    for prefer in ("P", "D"):
                        by_hw[hw].append((result[0], hw, replace(mapping, prefer=prefer), result[1]))
        feasible = sum(map(len, by_hw.values()))
    generation = perf_counter() - before_generation
    by_hw = {hw: sorted(items) for hw, items in by_hw.items()}
    lower = {hw: items[0][0] for hw, items in by_hw.items()}
    selection_start = perf_counter()
    if method in ("critical_joint", "critical_first", "critical_two"):
        rankings, probes = refine_candidates(by_hw, work, macros)
        compiled += len(probes)
    if method == "standalone":
        selected = all_ties({hw: phase_score(hw, work, macros) for hw in by_hw})
    elif method == "optimistic":
        selected = all_ties(lower)
    elif method in ("near", "wide"):
        selected = shortlist(lower, percent=2 if method == "near" else 10)
    elif method == "top_two":
        selected = shortlist(lower, count=2)
    elif method == "critical_first":
        selected = all_ties(rankings)
    elif method == "critical_two":
        selected = shortlist(rankings, count=2)
    else:
        selected = tuple(sorted(by_hw, key=lambda hw: (lower[hw], hw)))
    selection = perf_counter() - selection_start

    if method in ("joint", "binding", "critical_joint"):
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
        "candidates_dominated": feasible - sum(map(len, by_hw.values())),
        "compiled": compiled,
        "critical_probes": len(probes),
        "scheduled": replayed,
        "architectures_selected": [asdict(hw) for hw in selected],
        "edp_aj_ns": incumbent,
        "winner": {"hardware": asdict(program.hardware), "mapping": asdict(program.mapping)},
        "replay": {**verification, "scheduler_bank_wait_ns": waits},
        "checkpoints": {str(t): min((edp for when, edp in history if when <= t), default=None)
                        for t in deadlines},
        "incumbents": history,
    }


def layout_ablation(macros, hardware):
    hw = Architecture(64, 32, 2, 65536, 1024)
    if hw not in hardware:
        return {}
    layouts = {}
    work = CASES["context768"]
    for layout in ("striped", "separate", "shared"):
        mapping = Mapping(8, 32, 2, True, layout, "D", True)
        program = build(hw, work, mapping)
        if program is None:
            raise AssertionError("The fixed-address ablation must fit for all three layouts")
        costs = price(program, macros)
        value, _, starts, waits = dispatch(program, costs)
        independent = audit(program, macros, starts)
        if independent["edp"] != value:
            raise AssertionError("The layout ablation fails independent replay")
        layouts[layout] = {**independent, "scheduler_bank_wait_ns": waits,
                           "cheap_bound_aj_ns": estimate(hw, work, mapping, macros)[0],
                           "command_bound_aj_ns": costs.lower}
    return {"hardware": asdict(hw), "workload": asdict(work), "layouts": layouts}


def run(table, output, names, repeats, area_factor=1.5, methods=METHODS):
    macros = {int(size): row for size, row in table["macros"].items()}
    limit = Architecture(*REFERENCE).sram_totals(macros, "area_mm2") * area_factor
    hardware = tuple(sorted(
        hw for hw in (Architecture(*shape, banks, gb, local)
                      for shape, banks, gb, local in product(SHAPES, GB_BANKS, GB_BYTES, LOCAL_BYTES))
        if hw.sram_totals(macros, "area_mm2") <= limit
    ))
    report = {"area_mm2": limit, "hardware_points": len(hardware), "cases": {},
              "same_hardware_layout_ablation": layout_ablation(macros, hardware)}
    for name in names:
        work = CASES[name]
        runs = {method: [] for method in methods}
        for repeat in range(repeats):
            for method in methods[repeat % len(methods):] + methods[:repeat % len(methods)]:
                record = run_search(hardware, work, macros, method)
                runs[method].append(record)
                print(name, repeat, method, record["seconds"], record["edp_aj_ns"],
                      record["winner"], flush=True)
            if len({runs[method][-1]["edp_aj_ns"]
                    for method in ("binding", "joint", "sweep", "grouped_sweep", "critical_joint")
                    if method in runs}) > 1:
                raise AssertionError("The complete architecture sweep disagrees with joint search")
        report["cases"][name] = {"workload": asdict(work), "runs": runs}
        output.write_bytes(gzip.compress(json.dumps(report, indent=2).encode(), mtime=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--area-factor", type=float, default=1.5)
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    if args.area_factor <= 0:
        parser.error("--area-factor must be positive")
    if len(args.methods) != len(set(args.methods)):
        parser.error("--methods must be unique")
    run(json.loads(args.table.read_text()), args.output, args.cases, args.repeats, args.area_factor, args.methods)


if __name__ == "__main__":
    main()
