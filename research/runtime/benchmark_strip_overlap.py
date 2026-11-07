"""Benchmark exact overlap search against native FFM joins and GAMMA operators."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from research.runtime.strip_ffm import join
from research.runtime.strip_gamma import PINNED_SOURCE, search as gamma_search, upstream
from research.runtime.strip_overlap import audit
from research.runtime.strip_overlap_cost import evaluate_overlap
from research.runtime.strip_overlap_search import anchors, exact_search
from research.tracking_audit import common


CASES = {
    "3mm256": (256, (256,) * 4),
    "3mm512": (512, (512,) * 4),
    "rectangular_3mm": (193, (224, 320, 144, 192)),
    "rectangular_5mm": (317, (128, 192, 224, 128, 256, 192)),
    "rectangular_6mm": (512, (192, 256, 256, 128, 320, 192, 224)),
    "rectangular_7mm": (509, (64, 160, 96, 192, 256, 160, 128, 224)),
    # Uneven widths and their reversal test different pressure on the two ports.
    "wide_n": (257, (48, 384, 96, 512, 128)),
    "wide_k": (257, (128, 512, 96, 384, 48)),
}
BUDGETS = (131072, 135168, 262144)
DEADLINES = (0.05, 0.15, 0.50)
METHODS = ("demand", "ffm", "gamma")


def edp(design):
    cost, _, _ = design
    return cost[0] * cost[1]


def trajectory(method, rows, widths, budget, kernel, seed, deadline, designs):
    t0 = perf_counter()
    history = []

    def record(result):
        objective = edp(result)
        if not history or objective < history[-1]["edp"]:
            seconds = perf_counter() - t0
            token = (result[0], result[1], result[2])
            index = designs.setdefault(token, len(designs))
            history.append(dict(seconds=seconds, edp=objective, design=index))

    seeds = tuple(anchors(rows, widths, budget))
    initial = min(seeds, key=edp)
    record(initial)
    if method == "gamma":
        result, stats = gamma_search(kernel, rows, widths, budget, seeds, t0+deadline, seed, record)
    else:
        result, searched = exact_search(rows, widths, budget, on_incumbent=record, initial=initial,
                                        prefix_join=join if method == "ffm" else None)
        stats = dict(geometries_visited=searched, proved=True)
    record(result)
    return dict(history=history, total_seconds=perf_counter()-t0, **stats), result


def witness(rows, widths, result):
    cost, h, plan = result
    calendar = audit(rows, widths, h, plan)
    if cost[1] != calendar["end_ticks"] or cost != evaluate_overlap(rows, widths, h, plan)[0]:
        raise AssertionError("batched/scalar overlap score disagrees with scheduled events")
    return dict(architecture=asdict(h), mapping=[asdict(segment) for segment in plan],
                energy_units=cost[0], ticks=cost[1], edp=edp(result), calendar=calendar)


def snapshot(trials, method, seconds):
    return [next((step["edp"] for step in reversed(trial[method]["history"])
                  if step["seconds"] <= seconds), None) for trial in trials]


def run(kernel, digest, repeats):
    cases = {}
    for name, (rows, widths) in CASES.items():
        outcomes = []
        for budget in BUDGETS:
            designs = {}
            trials = []
            for seed in range(repeats):
                order = METHODS[seed % 3:] + METHODS[:seed % 3]
                trial, best = {}, {}
                for method in order:
                    trial[method], best[method] = trajectory(method, rows, widths, budget, kernel, seed,
                                                            DEADLINES[-1], designs)
                if edp(best["demand"]) != edp(best["ffm"]) or edp(best["demand"]) > edp(best["gamma"]):
                    raise AssertionError("exact and specialized baseline scores are inconsistent")
                trials.append(trial)
            catalog = [witness(rows, widths, design) for design in designs]
            speed = {m: median(t[m]["total_seconds"] for t in trials) for m in METHODS}
            snapshots = []
            for seconds in DEADLINES:
                values = {method: snapshot(trials, method, seconds) for method in METHODS}
                snapshots.append(dict(seconds=seconds, edp_by_seed=values))
            outcome = dict(budget_bytes=budget, trials=trials, witnesses=catalog,
                           median_total_seconds=speed, deadline_snapshots=snapshots)
            outcomes.append(outcome)
            print(json.dumps(dict(case=name, budget_bytes=budget, best=edp(best["demand"]),
                                  gamma=edp(best["gamma"]), median_seconds=speed)), flush=True)
        cases[name] = dict(rows=rows, widths=widths, outcomes=outcomes)
    return dict(
        repeats=repeats, workers=1, gamma_revision=PINNED_SOURCE, gamma_sha256=digest,
        port_calendar="ordered strip bands; shared DMA; SRAM staging when capacity permits",
        deadlines=DEADLINES, cases=cases,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gamma", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1 or args.output.exists():
        parser.error("use a positive trial count and a new output file")
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    kernel, digest = upstream(args.gamma)
    report = run(kernel, digest, args.repeats)
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
