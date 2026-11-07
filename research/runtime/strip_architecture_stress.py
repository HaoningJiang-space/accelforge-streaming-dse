"""Test joint choice against all architecture-first ties at SRAM transitions."""

import argparse
import hashlib
import json
from math import prod
from pathlib import Path

from research.runtime.benchmark_strip_overlap import BUDGETS, edp, witness
from research.runtime.strip_codesign import GEOMETRIES
from research.runtime.strip_overlap_search import exact_search, lower_geometry


WIDTHS = (192, 224, 256, 320, 384)
OFFSETS = (-1, 1)
STAGING_TARGET_BYTES = 3072


def best_training_geometry():
    """Train one geometry across all 3mm256 budgets using an exact objective."""
    widths = (256,) * 4
    trained = {}
    for geometry in GEOMETRIES:
        scores = [edp(exact_search(256, widths, cap, geometries=(geometry,))[0])
                  for cap in BUDGETS]
        trained[geometry] = prod(scores)
    return min(trained, key=trained.get)


def architecture_first(rows, widths, cap):
    start, _ = exact_search(rows, widths, cap, fuse=False)
    optimum = edp(start)
    selected = (start[1].px, start[1].py)
    ties = [selected]
    for x, y in GEOMETRIES:
        if (x, y) == selected or lower_geometry(rows, widths, x, y) > optimum:
            continue
        result, _ = exact_search(rows, widths, cap, geometries=((x, y),), fuse=False)
        if edp(result) == optimum:
            ties.append((x, y))
        elif edp(result) < optimum:
            raise AssertionError("the singleton architecture search missed an eligible geometry")
    result, _ = exact_search(rows, widths, cap, geometries=tuple(ties))
    return result, ties


def run(raw):
    report = json.loads(raw)
    fixed = best_training_geometry()
    reference = {(case, o["budget_bytes"]): o["trials"][0]["demand"]["history"][-1]["edp"]
                 for case, c in report["cases"].items() for o in c["outcomes"]}
    original = [(case, c["rows"], tuple(c["widths"]), o["budget_bytes"])
                for case, c in report["cases"].items() for o in c["outcomes"]]
    # Two row counts bracket the same declared activation-plus-staging target
    # in every SRAM tier. All points are measured, including ties.
    knee = [
        (f"transition_{width}_{shift:+d}", (cap - STAGING_TARGET_BYTES) // (2 * width) + shift,
         (width,) * 4, cap)
        for width in WIDTHS for cap in BUDGETS for shift in OFFSETS
    ]
    outputs = []
    for case, rows, widths, cap in [*original, *knee]:
        joint, _ = exact_search(rows, widths, cap)
        if (case, cap) in reference and edp(joint) != reference[case, cap]:
            raise AssertionError("repeated joint search differs from the external benchmark")
        adaptive, ties = architecture_first(rows, widths, cap)
        frozen, _ = exact_search(rows, widths, cap, geometries=(fixed,))
        if edp(joint) > min(edp(adaptive), edp(frozen)):
            raise AssertionError("the joint optimum is worse than a restricted candidate")
        scores = {name: witness(rows, widths, design)
                  for name, design in (("joint", joint), ("two_stage_tie_oracle", adaptive),
                                       ("fixed_training", frozen))}
        outputs.append(dict(case=case, rows=rows, widths=widths, budget_bytes=cap,
                            singleton_optimal_geometries=ties, results=scores))
        print(json.dumps(dict(case=case, rows=rows, capacity=cap, ties=len(ties),
                              gain=1-edp(joint)/edp(adaptive),
                              fixed_gain=1-edp(joint)/edp(frozen))), flush=True)
    return dict(source_sha256=hashlib.sha256(raw).hexdigest(), fixed_training_geometry=fixed,
                training="3mm256 across all three budgets", transition_widths=WIDTHS,
                transition_offsets=OFFSETS, transition_target_bytes=STAGING_TARGET_BYTES,
                results=outputs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = run(args.reference.read_bytes())
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
