"""Separate hardware selection, fusion and port-timing effects."""

import argparse
import hashlib
import json
from pathlib import Path

from research.joint_budget.protocol import Hardware
from research.runtime.benchmark_strip_overlap import edp, witness
from research.runtime.strip_codesign import CAPACITIES, GEOMETRIES, Segment
from research.runtime.strip_overlap_cost import evaluate_overlap, stage_frontier, tile_grid
from research.runtime.strip_overlap_search import (
    connected_frontier, exact_search, ideal_stage, lower_geometry,
)


def full_chain(rows, widths, budget):
    capacity = max(c for c in CAPACITIES if c <= budget)
    best = None
    for bound, x, y in sorted((lower_geometry(rows, widths, x, y), x, y) for x, y in GEOMETRIES):
        if best is not None and bound >= edp(best):
            break
        h = Hardware(x, y, capacity)
        for cost, segment in connected_frontier(rows, widths, h, 0, len(widths)-1):
            design = cost, h, (segment,)
            if best is None or edp(design) < edp(best):
                best = design
    stage_frontier.cache_clear()
    tile_grid.cache_clear()
    ideal_stage.cache_clear()
    if best is None:
        raise ValueError("no legal fully fused design")
    return best


def run(raw, serial_raw):
    current, serial = (json.loads(data) for data in (raw, serial_raw))
    training = current["cases"]["3mm256"]["outcomes"][-1]
    chosen = training["trials"][0]["demand"]["history"][-1]["design"]
    geometry = training["witnesses"][chosen]["architecture"]
    fixed = ((geometry["px"], geometry["py"]),)
    selections = []
    for name, workload in current["cases"].items():
        rows, widths = workload["rows"], tuple(workload["widths"])
        for i, outcome in enumerate(workload["outcomes"]):
            cap = outcome["budget_bytes"]
            reference = outcome["trials"][0]["demand"]["history"][-1]
            fixed_plan, _ = exact_search(rows, widths, cap, geometries=fixed)
            singleton, _ = exact_search(rows, widths, cap, fuse=False)
            shape = singleton[1].px, singleton[1].py
            two_stage, _ = exact_search(rows, widths, cap, geometries=(shape,))
            checks = dict(fixed_training=fixed_plan, two_stage=two_stage, singleton=singleton,
                          forced_full_chain=full_chain(rows, widths, cap))
            if name in serial["cases"]:
                old = serial["cases"][name]["outcomes"][i]["winners"]["dp"]
                h = Hardware(**old["architecture"])
                plan = tuple(Segment(**group) for group in old["mapping"])
                checks["serial_winner_retimed"] = evaluate_overlap(rows, widths, h, plan)[0], h, plan
            controls = {key: witness(rows, widths, result) for key, result in checks.items()}
            if any(row["edp"] < reference["edp"] for row in controls.values()):
                raise AssertionError("a restricted control improves on the claimed optimum")
            result = dict(case=name, budget_bytes=cap, joint_edp=reference["edp"],
                          joint=outcome["witnesses"][reference["design"]]["architecture"], controls=controls)
            selections.append(result)
            print(json.dumps(dict(case=name, budget=cap, joint=result["joint"], reductions={
                key: 1 - reference["edp"] / row["edp"] for key, row in controls.items()
            })), flush=True)
    return dict(fixed_training_geometry=fixed[0], source_sha256=hashlib.sha256(raw).hexdigest(),
                serial_sha256=hashlib.sha256(serial_raw).hexdigest(), selections=selections)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--serial", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = run(args.reference.read_bytes(), args.serial.read_bytes())
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
