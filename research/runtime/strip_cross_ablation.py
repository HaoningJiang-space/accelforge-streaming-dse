"""Cross hardware freedom with fusion policy at fixed SRAM ceilings."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from research.joint_budget.protocol import Hardware
from research.runtime.strip_codesign import (
    CAPACITIES, GEOMETRIES, dynamic_search, evaluate, segment_frontier,
)
from research.runtime.strip_trace import replay


def full_chain(rows, widths, budget):
    best = None
    for x, y in GEOMETRIES:
        hardware = Hardware(x, y, max(c for c in CAPACITIES if c <= budget))
        for cost, segment in segment_frontier(rows, widths, hardware, 0, len(widths)-1):
            if best is None or cost[0] * cost[1] < best[0][0] * best[0][1]:
                best = cost, hardware, (segment,)
    if best is None:
        raise ValueError("no fully fused plan")
    return best


def run(raw):
    report = json.loads(raw)
    training = report["cases"]["3mm256"]["outcomes"][-1]["winners"]["dp"]["architecture"]
    fixed = ((training["px"], training["py"]),)
    summary = []
    for case, workload in report["cases"].items():
        rows, widths = workload["rows"], tuple(workload["widths"])
        for outcome in workload["outcomes"]:
            budget = outcome["budget_bytes"]
            checks = {
                f"{arch}_{fusion}": dynamic_search(rows, widths, budget, geometries, fuse)
                for arch, geometries in (("fixed", fixed), ("joint", GEOMETRIES))
                for fusion, fuse in (("singleton", False), ("adaptive", True))
            }
            checks["joint_full_chain"] = full_chain(rows, widths, budget)
            results = {}
            for label, (cost, hardware, plan) in checks.items():
                score, peak, words = replay(rows, widths, hardware, plan)
                if score != cost or evaluate(rows, widths, hardware, plan) != (cost, peak):
                    raise AssertionError("ablation schedule failed common evaluator")
                results[label] = dict(architecture=asdict(hardware), edp=cost[0] * cost[1],
                                      peak_bytes=peak, dram_bytes=sum(
                                          n for (_, level, _, _), n in words.items() if level == "DRAM"),
                                      mapping=[asdict(group) for group in plan])
            if results["joint_adaptive"]["edp"] != outcome["winners"]["dp"]["edp"]:
                raise AssertionError("primary benchmark and crossed ablations differ")
            summary.append(dict(case=case, budget_bytes=budget, controls=results))
    return dict(input_sha256=hashlib.sha256(raw).hexdigest(), fixed_geometry=fixed[0], selections=summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.reference.read_bytes())
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
