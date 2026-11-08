"""Exact LSTP architecture selection over a fixed synthetic serving sample."""

import argparse
from dataclasses import asdict
from math import ceil
import json
import multiprocessing as mp
import os
from pathlib import Path
from random import Random
from statistics import mean, median
from time import monotonic

from research.physical_cost.concurrent_serving import Workload
from research.physical_cost.serving_exhaustive import inputs, limit_memory, panel, write_atomic


def sample(seed=17309):
    rng = Random(seed)
    for band, (low, high) in enumerate(((64, 160), (161, 384), (385, 1024))):
        for delayed in (False, True):
            concurrent = 3 if band == 2 else 2
            for index, requests in enumerate((1, concurrent, concurrent, 1)):
                contexts = tuple(rng.randint(low, high) for _ in range(requests))
                arrivals = [rng.randrange(40_000_000, 100_000_001) if delayed else rng.randrange(0, 5_000_001), 0]
                arrivals.extend(sorted(rng.randrange(100_000, 1_001_000) for _ in range(requests - 1)))
                work = Workload(rng.choice((32, 96, 192, 384)), contexts, rng.choice((1, 2)),
                                tuple(arrivals))
                yield f"band{band}-{'delayed' if delayed else 'overlap'}-{index}", index < 2, work


def score(row, index, field="episode"):
    return row[field][index]


def measure(rows, index):
    edps = [score(row, index) for row in rows]
    oracle = [row["oracle"] for row in rows]
    regrets = sorted(value / target - 1 for value, target in zip(edps, oracle, strict=True))
    return {"mean_edp": mean(edps), "regret_to_oracle_mean_edp": mean(edps) / mean(oracle) - 1,
            "mean_scenario_regret": mean(regrets), "median_scenario_regret": median(regrets),
            "p90_scenario_regret": regrets[ceil(0.9 * len(regrets)) - 1],
            "scenario_edp": edps}


def minimum(indices, key):
    scored = [(key(index), index) for index in indices]
    best = min(scored)[0]
    return sorted(index for value, index in scored if value == best)


def select(rows, count):
    train = [row for row in rows if row["training"]]
    test = [row for row in rows if not row["training"]]
    feasible = [i for i in range(count) if all(row["episode"][i] is not None for row in train)]
    selections = {field: minimum(feasible, lambda i: sum(score(row, i, field) for row in train))
                  for field in ("episode", "decode", "prefill")}
    for row in train:
        selections[row["name"]] = minimum(feasible, lambda i: score(row, i))
    # Remap every tied architecture over the training episodes before the
    # final index tie-break. The test samples are scored only afterward.
    result = {}
    for name, ties in selections.items():
        index = min(ties, key=lambda i: (sum(score(row, i) for row in train), i))
        result[name] = {"index": index, "training_ties": ties, "train": measure(train, index),
                        "test": measure(test, index) if all(row["episode"][index] is not None for row in test) else None}
    return result


def stage_gate(rows, selections):
    training = [row for row in rows if row["training"]]
    phase = min(("decode", "prefill"),
                key=lambda name: (sum(score(row, selections[name]["index"]) for row in training), name))
    held_out = [row for row in rows if not row["training"]]
    robust = selections["episode"]["index"]
    baseline = selections[phase]["index"]
    threshold = {"numerator": 1, "denominator": 10}
    comparison = {"phase_chosen_on_training": phase, "threshold": threshold,
                  "passed": None, "held_out_regret_to_shared": None}
    if selections[phase]["test"] and selections["episode"]["test"]:
        ours = sum(score(row, robust) for row in held_out)
        theirs = sum(score(row, baseline) for row in held_out)
        comparison["held_out_regret_to_shared"] = theirs / ours - 1
        comparison["passed"] = 10 * theirs >= 11 * ours
    return comparison


def compact(panel_result, name, training):
    rows = panel_result["architectures"]
    result = {"name": name, "training": training, "workload": panel_result["workload"],
              "oracle": panel_result["best_edp"], "oracle_architectures": panel_result["optimal_architectures"],
              "evaluated": panel_result["evaluated"]}
    for phase in ("episode", "decode", "prefill"):
        values = [row if phase == "episode" else row["stages"][phase] for row in rows]
        result[phase] = [row["best"]["edp"] if row["evaluated"] else None for row in values]
        result[f"{phase}_evaluated"] = sum(row["evaluated"] for row in values)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sram", type=Path)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--memory-gib", type=int, required=True)
    parser.add_argument("--seconds", type=float, required=True)
    args = parser.parse_args()
    if min(args.workers, args.memory_gib, args.seconds) <= 0 or args.workers > (os.cpu_count() or 1):
        parser.error("Use positive limits and at most one worker per logical CPU")
    deadline = monotonic() + args.seconds
    limit_memory(args.memory_gib * 2**30, args.workers)
    hardware, macros, manifest = inputs(args.sram, args.ledger)
    if manifest["device"] != "itrs-lstp":
        parser.error("The distribution uses the LSTP SRAM table")
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    with mp.get_context("spawn").Pool(args.workers) as pool:
        for name, training, work in sample():
            checkpoint = {**manifest, "workload": json.loads(json.dumps(asdict(work))), "stages": True}
            report = panel(pool, name, work, hardware, macros, args.output, checkpoint, deadline, stages=True)
            rows.append(compact(report, name, training))
    selections = select(rows, len(hardware))
    result = {**manifest, "seed": 17309, "architecture": [asdict(hw) for hw in hardware],
              "scenarios": rows, "selections": selections, "stage_gate": stage_gate(rows, selections)}
    write_atomic(args.output / "distribution.json.gz", result)


if __name__ == "__main__":
    main()
