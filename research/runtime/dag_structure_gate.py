"""Compare exact DAG searches under identical costing and cache settings."""

import argparse
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from research.runtime.dag_cases import CASES
from research.runtime.dag_overlap_search import exact_search
from research.runtime.dag_staging_gate import BUDGETS, audited, mm3


DEADLINES = (0.01, 0.02, 0.05, 0.1, 0.25)


def measure(graph, budget, prune):
    trace = []
    stats = {}
    start = perf_counter()

    def found(result):
        energy, ticks = result[0]
        trace.append((perf_counter()-start, energy*ticks))

    result, _ = exact_search(graph, budget, prune_orders=prune, on_incumbent=found, stats=stats)
    elapsed = perf_counter()-start
    witness = audited(graph, result)
    return dict(wall_s=elapsed, edp=witness["edp"], trace=trace, **stats)


def compare(graph, budget, repeats):
    trials = {name: [] for name in ("dominance", "enumerated")}
    for trial in range(repeats):
        for prune in ((True, False) if trial % 2 == 0 else (False, True)):
            name = "dominance" if prune else "enumerated"
            trials[name].append(measure(graph, budget, prune))
    best, = {row["edp"] for rows in trials.values() for row in rows}
    result = {}
    for name, rows in trials.items():
        points = []
        for deadline in DEADLINES:
            values = [min((cost for elapsed, cost in row["trace"] if elapsed <= deadline), default=None)
                      for row in rows]
            feasible = [cost for cost in values if cost is not None]
            points.append(dict(deadline_s=deadline, feasible_trials=len(feasible),
                               optimum_trials=feasible.count(best),
                               median_regret=median(cost/best-1 for cost in feasible) if feasible else None))
        result[name] = dict(wall_median_s=median(row["wall_s"] for row in rows), quality=points,
                            first_optimum_median_s=median(next(t for t, cost in row["trace"] if cost == best)
                                                         for row in rows), trials=rows)
    return dict(budget_bytes=budget, **result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1 or args.output.exists():
        parser.error("require positive repetitions and a fresh report path")
    rows = []
    for name, factory in {"3mm": mm3, **CASES}.items():
        graph = factory()
        for budget in BUDGETS:
            result = compare(graph, budget, args.repeats)
            rows.append(dict(case=name, **result))
            print(name, budget, *(result[mode]["wall_median_s"] for mode in ("dominance", "enumerated")), flush=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(dict(repeats=args.repeats, cases=rows), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
