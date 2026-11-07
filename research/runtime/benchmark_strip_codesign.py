"""Compare connected-segment DP and CP-SAT with one shared physical contract."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import platform
from statistics import median
from time import perf_counter

import ortools

from research.runtime.strip_codesign import (
    CAPACITIES, GEOMETRIES, dynamic_search, evaluate, representatives,
)
from research.runtime.strip_cpsat import solve
from research.runtime.strip_trace import replay


CASES = {
    "3mm256": (256, (256,) * 4),
    "3mm512": (512, (512,) * 4),
    "rectangular_3mm": (193, (224, 320, 144, 192)),
    "rectangular_5mm": (317, (128, 192, 224, 128, 256, 192)),
    "rectangular_6mm": (512, (192, 256, 256, 128, 320, 192, 224)),
    "rectangular_7mm": (509, (64, 160, 96, 192, 256, 160, 128, 224)),
}
BUDGETS = (131072, 135168, 262144)
ENERGY_J = 4e-15
TIME_S = 1e-9 / 1536


def audited(result, rows, widths):
    cost, hardware, plan = result
    actual, peak, words = replay(rows, widths, hardware, plan)
    if cost != actual or evaluate(rows, widths, hardware, plan) != (actual, peak):
        raise AssertionError("compiled plan failed the independent wave trace")
    return dict(
        architecture=asdict(hardware), mapping=[asdict(g) for g in plan],
        peak_bytes=peak, energy=cost[0], ticks=cost[1], edp=cost[0] * cost[1],
        edp_j_s=cost[0] * cost[1] * ENERGY_J * TIME_S,
        words={"/".join(map(str, key)): value for key, value in sorted(words.items())},
    )


def bench(rows, widths, capacity, repeats, seconds):
    trials = []
    scores = {}
    for trial in range(repeats):
        results = {}
        for method in (("dp", "cpsat") if trial % 2 == 0 else ("cpsat", "dp")):
            representatives.cache_clear()
            started = perf_counter()
            if method == "dp":
                result = dynamic_search(rows, widths, capacity)
                stats = dict(status="OPTIMAL")
            else:
                result, stats = solve(rows, widths, capacity, seconds, seed=trial)
            scores[method] = audited(result, rows, widths)
            results[method] = dict(seconds=perf_counter() - started, edp=scores[method]["edp"], **stats)
        if results["cpsat"]["status"] == "OPTIMAL" and results["dp"]["edp"] != results["cpsat"]["edp"]:
            raise AssertionError("the two exact searches returned different optima")
        if results["dp"]["edp"] > results["cpsat"]["edp"]:
            raise AssertionError("dynamic search missed a feasible CP-SAT candidate")
        trials.append(results)
    dp_s, cp_s = (median(t[m]["seconds"] for t in trials) for m in ("dp", "cpsat"))

    no_fusion = dynamic_search(rows, widths, capacity, fuse=False)
    chosen = no_fusion[1]
    controls = {
        "fixed_nvdla": dynamic_search(rows, widths, capacity, geometries=((32, 192),)),
        "no_fusion": no_fusion,
        "stagewise_arch_then_fusion": dynamic_search(rows, widths, capacity,
                                                     geometries=((chosen.px, chosen.py),)),
    }
    return dict(
        trials=trials, dp_median_s=dp_s, cpsat_median_s=cp_s, speedup=cp_s / dp_s,
        winners=scores,
        controls={name: audited(result, rows, widths) for name, result in controls.items()},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--solver-seconds", type=float, default=30)
    args = parser.parse_args()
    if args.repeats < 1 or args.solver_seconds <= 0 or args.output.exists():
        parser.error("need positive limits and a new output file")
    cases = {}
    for name, (rows, widths) in CASES.items():
        outcomes = []
        for capacity in BUDGETS:
            outcome = bench(rows, widths, capacity, args.repeats, args.solver_seconds)
            outcomes.append(dict(budget_bytes=capacity, **outcome))
            print(json.dumps(dict(
                case=name, budget=capacity, speedup=outcome["speedup"],
                edp=outcome["winners"]["dp"]["edp"],
                cpsat=sorted({t["cpsat"]["status"] for t in outcome["trials"]}),
            )), flush=True)
        cases[name] = dict(rows=rows, widths=widths, outcomes=outcomes)
    report = dict(
        cpu=platform.processor(), python=platform.python_version(), ortools=ortools.__version__,
        workers=1, repeats=args.repeats, cpsat_timeout_seconds=args.solver_seconds,
        hardware_geometries=GEOMETRIES, capacities_bytes=CAPACITIES,
        memory_and_mac_time="serialized wave services", energy_unit_j=ENERGY_J,
        time_unit_s=TIME_S, cases=cases,
    )
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
