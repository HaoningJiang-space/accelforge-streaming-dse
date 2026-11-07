"""Measure validated joint-design quality along both wall-clock trajectories."""

import argparse
import json
from pathlib import Path
from statistics import median
from time import perf_counter

import ortools

from research.runtime.benchmark_strip_codesign import BUDGETS, CASES, audited
from research.runtime.strip_codesign import CAPACITIES, GEOMETRIES, dynamic_search, representatives
from research.runtime.strip_cpsat import common_incumbent, solve


DEADLINES = (0.005, 0.020, 0.100)


def trajectory(method, rows, widths, capacity, seed):
    representatives.cache_clear()
    started = perf_counter()
    history = []

    def record(result):
        (e, t), _, _ = result
        if not history or e * t < history[-1]["edp"]:
            witness = audited(result, rows, widths)
            history.append(dict(seconds=perf_counter() - started, edp=witness["edp"],
                                architecture=witness["architecture"], mapping=witness["mapping"]))

    # Same policy and charge for finding and validating the first feasible plan.
    common = common_incumbent(rows, widths, [c for c in CAPACITIES if c <= capacity], GEOMETRIES)
    record(common)
    if method == "dp":
        result = dynamic_search(rows, widths, capacity, on_incumbent=record)
        stats = dict(status="OPTIMAL")
    else:
        result, stats = solve(rows, widths, capacity, 30, seed=seed, on_incumbent=record,
                              initial_design=common)
    record(result)
    return dict(proved_or_stopped_s=perf_counter() - started, history=history, **stats)


def quality(trial, deadline):
    return next((entry["edp"] for entry in reversed(trial["history"])
                 if entry["seconds"] <= deadline), None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repeats", type=int, default=9)
    args = parser.parse_args()
    if args.output.exists() or args.repeats < 1:
        parser.error("need a new output path and positive repeats")
    report = dict(workers=1, repeats=args.repeats, ortools=ortools.__version__,
                  deadlines_s=DEADLINES, cases={})
    for name, (rows, widths) in CASES.items():
        outcomes = []
        for capacity in BUDGETS:
            runs = []
            for seed in range(args.repeats):
                order = ("dp", "cpsat") if seed % 2 == 0 else ("cpsat", "dp")
                run = {method: trajectory(method, rows, widths, capacity, seed) for method in order}
                if (run["cpsat"]["status"] != "OPTIMAL"
                        or run["dp"]["history"][-1]["edp"] != run["cpsat"]["history"][-1]["edp"]):
                    raise AssertionError("benchmark needs the same terminal exact EDP")
                runs.append(run)
            snapshots = []
            for deadline in DEADLINES:
                paired = [(quality(run["dp"], deadline), quality(run["cpsat"], deadline)) for run in runs]
                changes = [1 - a / b for a, b in paired if a is not None and b is not None]
                snapshots.append(dict(
                    seconds=deadline, dp_wins=sum(x > 0 for x in changes),
                    cpsat_wins=sum(x < 0 for x in changes), equal=changes.count(0),
                    dp_missed=sum(a is None for a, _ in paired),
                    cpsat_missed=sum(b is None for _, b in paired),
                    median_edp_reduction=median(changes) if changes else None,
                ))
            outcomes.append(dict(budget_bytes=capacity, snapshots=snapshots, trials=runs))
            print(json.dumps(dict(case=name, capacity=capacity, snapshots=snapshots)), flush=True)
        report["cases"][name] = dict(rows=rows, widths=widths, outcomes=outcomes)
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
