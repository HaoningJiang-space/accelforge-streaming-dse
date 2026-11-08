"""Measure architecture shortlist regret and certify exactness in nested SRAM grids."""

import argparse
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
import gzip
from heapq import heapify, heappop, heappush
from itertools import product
import json
from math import ceil
from pathlib import Path
from random import Random
from time import perf_counter

from research.physical_cost.banked_oracle import audit
from research.physical_cost.banked_search import (
    CASES, CRITICAL_PROBES, action_prices, bind_profile, bound_profile, shortlist,
)
from research.physical_cost.banked_serving import Mapping, build, dispatch, layout_requirements, mappings, price
from research.physical_cost.mixed_gate import Architecture, GB_BANKS, GB_BYTES, LOCAL_BYTES, REFERENCE, SHAPES


WORKLOADS = {
    **CASES,
    "kv_long": replace(CASES["kv512"], steps=32),
    "kv_asymmetric": replace(CASES["kv512"], rows=93, inner=192, columns=320, context=576, head=80),
}
DEFAULT_CASES = ("context512", "holdout576", "kv512", "kv_long", "kv_asymmetric")
COLD_METHODS = ("adaptive", "joint", "within10", "critical_top2")
COLD_DEADLINES = (1, 3, 5, 10, 20)


@dataclass(frozen=True, order=True)
class DeepArchitecture(Architecture):
    global_depth: int = 1
    private_depth: int = 1

    @property
    def global_capacity(self):
        return self.global_bank_bytes * self.global_depth

    @property
    def private_capacity(self):
        return self.weight_bytes_per_stripe * self.private_depth

    def sram_totals(self, macros, metric):
        return (macros[self.global_bank_bytes][metric] * (self.global_banks * self.global_depth)
                + macros[self.weight_bytes_per_stripe][metric] * (self.x * self.private_depth))


def grid(macros, limit):
    global_options = [(size, depth) for size, count in ((16384, 8), (65536, 3))
                      for depth in range(1, count + 1)]
    local_options = [(size, depth) for size, count in ((1024, 8), (4096, 3))
                     for depth in range(1, count + 1)]
    hardware = (DeepArchitecture(x, 2048 // x, banks, g, l, gd, ld)
                for x, banks, (g, gd), (l, ld) in product(
                    (4, 8, 16, 32, 64, 128, 256), range(2, 25), global_options, local_options))
    return tuple(sorted(hw for hw in hardware if hw.sram_totals(macros, "area_mm2") <= limit))


def service(hw, macros):
    cycles = tuple(ceil(max(m["access_ns"], m["cycle_ns"]))
                   for m in (macros[hw.global_bank_bytes], macros[hw.weight_bytes_per_stripe]))
    return hw.x, hw.y, hw.global_banks, *cycles


@dataclass
class HardwareRows:
    timing: tuple
    costs: tuple
    feasible_mask: int
    plans: list

    @property
    def lower(self):
        return self.plans[0][0]


def catalog(hardware, work, macros, plans):
    """Compile the layout and bound profile once per mapping and timing class."""
    groups = defaultdict(list)
    for hw in hardware:
        groups[service(hw, macros)].append(hw)
    rows, profile_count = {}, 0
    for timing, group in groups.items():
        requirements = []
        gb_max = max(hw.global_capacity for hw in group)
        local_max = max(hw.private_capacity for hw in group)
        for index, mapping in enumerate(plans):
            regions, gb, local = layout_requirements(group[0], work, mapping)
            if gb <= gb_max and local <= local_max:
                duration, traffic = bound_profile(group[0], work, mapping, regions, *timing[-2:])
                requirements.append((index, gb, local, duration, traffic))
        profile_count += len(requirements)
        for hw in group:
            prices = action_prices(macros[hw.global_bank_bytes], macros[hw.weight_bytes_per_stripe])
            leak = round(hw.sram_totals(macros, "leak_mw") * 1e6)
            items, mask = [], 0
            for index, gb, local, duration, traffic in requirements:
                if gb <= hw.global_capacity and local <= hw.private_capacity:
                    bound, dynamic = bind_profile(duration, traffic, prices, leak)
                    items.append((bound, index, dynamic))
                    mask |= 1 << index
            if items:
                rows[hw] = HardwareRows(timing, (leak, *prices), mask, sorted(items))
    return rows, profile_count


def breakpoints(hardware, rows):
    """Remove a design only when a surviving design supports all its plans."""
    groups = defaultdict(list)
    for hw in hardware:
        groups[rows[hw].timing].append(hw)
    result = []
    for group in groups.values():
        kept = []
        for hw in sorted(group, key=lambda h: (rows[h].costs, -rows[h].feasible_mask.bit_count(), h)):
            current = rows[hw]
            if any(current.feasible_mask & rows[other].feasible_mask == current.feasible_mask
                   and all(a <= b for a, b in zip(rows[other].costs, current.costs, strict=True))
                   for other in kept):
                continue
            kept.append(hw)
        result.extend(kept)
    return tuple(result)


class Evaluator:
    def __init__(self, work, macros, plans, rows):
        self.work, self.macros, self.plans, self.rows = work, macros, plans, rows
        self.compiled, self.times, self.verified = {}, {}, {}

    def command(self, hw, index):
        # Same addresses and service periods imply the same command times.
        # The cached hardware prices are irrelevant to those times.
        key = self.rows[hw].timing, index
        if key not in self.compiled:
            program = build(hw, self.work, self.plans[index])
            self.compiled[key] = program, price(program, self.macros)
        return key, self.compiled[key]

    def score(self, hw, dynamic, duration):
        return (dynamic + self.rows[hw].costs[0] * duration) * duration

    def critical_score(self, hw):
        return min(max(bound, self.score(hw, dynamic, self.command(hw, index)[1][1].lower_ns))
                   for bound, index, dynamic in self.rows[hw].plans[:CRITICAL_PROBES])

    def scheduled_edp(self, hw, index, prefer, dynamic):
        key, (program, costs) = self.command(hw, index)
        trial = key, prefer
        if trial not in self.times:
            mapped = replace(program, mapping=replace(program.mapping, prefer=prefer))
            self.times[trial] = dispatch(mapped, costs)[1]
        return self.score(hw, dynamic, self.times[trial])

    def exact(self, hardware, upper=float("inf"), best=None, report=None):
        visits = 0
        checks = 0
        for hw in sorted(hardware, key=lambda h: (self.rows[h].lower, h)):
            if self.rows[hw].lower >= upper:
                break
            visits += 1
            for bound, index, dynamic in self.rows[hw].plans:
                if bound >= upper:
                    break
                _, (_, costs) = self.command(hw, index)
                if self.score(hw, dynamic, costs.lower_ns) >= upper:
                    continue
                for prefer in ("P", "D"):
                    checks += 1
                    score = self.scheduled_edp(hw, index, prefer, dynamic)
                    if score < bound:
                        raise AssertionError("Addressed evaluation is below its optimistic bound")
                    if score < upper:
                        upper, best = score, (hw, index, prefer)
                        if report is not None:
                            report(upper, best)
        if best is None:
            raise ValueError("The subset contains no feasible hardware")
        self.verify(upper, *best)
        return upper, best, visits, checks

    def joint(self, hardware, upper, best, report):
        """Interleave architectures and refine individual mapping bounds lazily."""
        queue = [(self.rows[hw].lower, hw, 0, False) for hw in hardware]
        heapify(queue)
        visits, checks = set(), 0
        while queue and queue[0][0] < upper:
            bound, hw, position, refined = heappop(queue)
            visits.add(hw)
            options = self.rows[hw].plans
            _, index, dynamic = options[position]
            if not refined:
                if position + 1 < len(options):
                    heappush(queue, (options[position + 1][0], hw, position + 1, False))
                _, (_, costs) = self.command(hw, index)
                refined_bound = max(bound, self.score(hw, dynamic, costs.lower_ns))
                if refined_bound > bound:
                    if refined_bound < upper:
                        heappush(queue, (refined_bound, hw, position, True))
                    continue
            for prefer in ("P", "D"):
                checks += 1
                score = self.scheduled_edp(hw, index, prefer, dynamic)
                if score < bound:
                    raise AssertionError("Refined command bound exceeds the addressed schedule")
                if score < upper:
                    upper, best = score, (hw, index, prefer)
                    report(upper, best)
        return upper, best, len(visits), checks

    def verify(self, score, hw, index, prefer):
        key = hw, index, prefer
        if key not in self.verified:
            program = build(hw, self.work, replace(self.plans[index], prefer=prefer))
            expected, elapsed, starts, _ = dispatch(program, price(program, self.macros))
            replay = audit(program, self.macros, starts)
            if replay["edp"] != expected or replay["ns"] != elapsed:
                raise AssertionError("Independent addressed replay disagrees")
            self.verified[key] = expected
        if self.verified[key] != score:
            raise AssertionError("Retargeted service or prices disagree with exact replay")


def measure(hardware, rows, evaluator, ranks):
    reduced = breakpoints(hardware, rows)
    optimum, winner, visits, checks = evaluator.exact(reduced)
    winner_hw, winner_index, winner_prefer = winner
    result = {
        "feasible": len(hardware),
        "timing_classes": len({rows[hw].timing for hw in hardware}),
        "breakpoints": len(reduced),
        "exact_edp": optimum,
        "exact_hardware": asdict(winner_hw),
        "exact_mapping": asdict(replace(evaluator.plans[winner_index], prefer=winner_prefer)),
        "architectures_remapped_for_proof": visits,
        "schedule_checks_for_proof": checks,
        "shortlists": {},
    }
    for universe, candidates in (("all", hardware), ("breakpoints", reduced)):
        cheap = {hw: rows[hw].lower for hw in candidates}
        critical = {hw: ranks[hw] for hw in candidates}
        methods = {
            "top1": shortlist(cheap, count=1),
            "top2": shortlist(cheap, count=2),
            "within10": shortlist(cheap, percent=10),
            "critical_top2": shortlist(critical, count=2),
        }
        for method, chosen in methods.items():
            upper, _, remapped, evals = evaluator.exact(chosen)
            outside = min((cheap[hw] for hw in cheap.keys() - set(chosen)), default=upper)
            lower = min(upper, outside)
            if not lower <= optimum <= upper:
                raise AssertionError("Invalid shortlist certificate or dominance")
            result["shortlists"][f"{universe}/{method}"] = {
                "size": len(chosen),
                "remapped": remapped,
                "schedule_checks": evals,
                "edp": upper,
                "miss": upper > optimum,
                "regret": upper / optimum - 1,
                "certificate_lower": lower,
                "certificate_gap": upper / lower - 1,
                "excluded_lower": outside,
                "certified": upper <= outside,
            }
    return result


def nested_samples(hardware, anchor, sizes, seeds):
    for seed in seeds:
        other = sorted(set(hardware) - set(anchor))
        Random(seed).shuffle(other)
        for size in sizes:
            if len(anchor) < size < len(hardware):
                yield seed, (*anchor, *other[:size - len(anchor)])
    yield None, anchor
    yield None, hardware


def run(macros, cap, cases, sizes, seeds, output):
    reference = Architecture(*REFERENCE).sram_totals(macros, "area_mm2")
    hardware = grid(macros, cap)
    anchor = tuple(sorted(hw for hw in (
        DeepArchitecture(*shape, banks, g, l)
        for shape, banks, g, l in product(SHAPES, GB_BANKS, GB_BYTES, LOCAL_BYTES))
        if hw.sram_totals(macros, "area_mm2") <= min(1.5 * reference, cap)))
    report = {"sram_area_mm2": cap, "hardware_points": len(hardware), "seeds": seeds, "cases": {}}
    for name in cases:
        start = perf_counter()
        work = WORKLOADS[name]
        plans = tuple(m for m in mappings() if m.prefer == "P" and (m.resident or not work.reserve_values))
        rows, profiles = catalog(hardware, work, macros, plans)
        generation_s = perf_counter() - start
        evaluator = Evaluator(work, macros, plans, rows)
        ranks = {hw: evaluator.critical_score(hw) for hw in rows}
        rank_s = perf_counter() - start - generation_s
        results = []
        for seed, subset in nested_samples(hardware, anchor, sizes, seeds):
            eligible = tuple(hw for hw in subset if hw in rows)
            record = measure(eligible, rows, evaluator, ranks)
            results.append({"seed": seed, "size": len(subset), **record})
        report["cases"][name] = {
            "workload": asdict(work), "cells": results, "generated_bound_profiles": profiles,
            "feasible_mapping_hardware_pairs": 2 * sum(len(row.plans) for row in rows.values()),
            "catalog_seconds": generation_s, "critical_ranking_seconds": rank_s,
            "amortized_seconds": perf_counter() - start,
            "unique_command_compilations": len(evaluator.compiled),
            "unique_schedules": len(evaluator.times), "independent_replays": len(evaluator.verified),
        }
        full = results[-1]
        print(name, len(hardware), full["feasible"], full["breakpoints"], full["exact_edp"],
              [(m, round(item["regret"], 4)) for m, item in full["shortlists"].items()], flush=True)
        output.write_bytes(gzip.compress(json.dumps(report, indent=2).encode(), mtime=0))


def cold_search(macros, cap, work, method):
    start = perf_counter()
    hardware = grid(macros, cap)
    plans = tuple(m for m in mappings() if m.prefer == "P" and (m.resident or not work.reserve_values))
    rows, profiles = catalog(hardware, work, macros, plans)
    reduced = breakpoints(tuple(rows), rows)
    generation_s = perf_counter() - start
    evaluator = Evaluator(work, macros, plans, rows)
    history = []

    def record(score, choice):
        evaluator.verify(score, *choice)
        history.append((perf_counter() - start, score))

    # Give each method the same independently verified feasible seed.
    anchor = DeepArchitecture(64, 32, 2, 65536, 1024)
    anchor_plan = Mapping(16, 32, 1, work.reserve_values, "striped", "P")
    index = plans.index(anchor_plan)
    seed = None
    if anchor in rows:
        seed = next((dynamic for _, candidate, dynamic in rows[anchor].plans if index == candidate), None)
    if seed is None:
        anchor = min(reduced)
        _, index, seed = rows[anchor].plans[0]
    choice = (anchor, index, "D")
    upper = evaluator.scheduled_edp(*choice, seed)
    record(upper, choice)

    selection_start = perf_counter()
    if method == "within10":
        chosen = shortlist({hw: rows[hw].lower for hw in reduced}, percent=10)
    elif method == "critical_top2":
        chosen = shortlist({hw: evaluator.critical_score(hw) for hw in reduced}, count=2)
    else:
        chosen = reduced
    selection_s = perf_counter() - selection_start
    solver = evaluator.joint if method == "joint" else evaluator.exact
    optimum, _, visits, checks = solver(chosen, upper, choice, record)
    omitted_bound = min((rows[hw].lower for hw in set(reduced) - set(chosen)), default=optimum)
    return {
        "seconds": perf_counter() - start, "generation_seconds": generation_s,
        "selection_seconds": selection_s, "bound_profiles": profiles, "size": len(chosen),
        "architectures_visited": visits, "schedule_checks": checks, "edp": optimum,
        "certified": optimum <= omitted_bound, "lower": min(optimum, omitted_bound),
        "compilations": len(evaluator.compiled), "independent_replays": len(evaluator.verified),
        "incumbents": history,
        "checkpoints": {str(t): min((score for stamp, score in history if stamp <= t), default=None)
                        for t in COLD_DEADLINES},
    }


def run_cold(macros, cap, cases, repeats, output):
    report = {"sram_area_mm2": cap, "repeats": repeats, "cases": {}}
    for name in cases:
        records = {method: [] for method in COLD_METHODS}
        for repeat in range(repeats):
            turn = repeat % len(COLD_METHODS)
            for method in COLD_METHODS[turn:] + COLD_METHODS[:turn]:
                row = cold_search(macros, cap, WORKLOADS[name], method)
                records[method].append(row)
                print(name, repeat, method, row["edp"], round(row["seconds"], 3), flush=True)
            if records["joint"][-1]["edp"] != records["adaptive"][-1]["edp"]:
                raise AssertionError("Exact architecture-first and joint search disagree")
        report["cases"][name] = {"workload": asdict(WORKLOADS[name]), "runs": records}
        output.write_bytes(gzip.compress(json.dumps(report, indent=2).encode(), mtime=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--area", type=float, default=4.5)
    parser.add_argument("--cases", nargs="+", choices=WORKLOADS, default=DEFAULT_CASES)
    parser.add_argument("--sizes", nargs="+", type=int, default=(64, 256, 1024))
    parser.add_argument("--seeds", nargs="+", type=int, default=(17, 29, 61, 83, 101))
    parser.add_argument("--cold-repeats", type=int, default=0)
    args = parser.parse_args()
    if args.area < 1.346496 or not all(n > 0 for n in args.sizes) or args.cold_repeats < 0:
        parser.error("Provide at least the reference SRAM budget, positive sizes, and nonnegative repeats")
    macros = {int(size): value for size, value in json.loads(args.table.read_text())["macros"].items()}
    if args.cold_repeats:
        run_cold(macros, args.area, args.cases, args.cold_repeats, args.output)
    else:
        run(macros, args.area, args.cases, args.sizes, args.seeds, args.output)


if __name__ == "__main__":
    main()
