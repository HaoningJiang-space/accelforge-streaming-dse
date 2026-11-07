"""Reoptimize architecture and mapping for executable next-wave DMA."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from time import perf_counter

from research.runtime.dag_architecture_gate import objective
from research.runtime.dag_calendar import events, replay
from research.runtime.dag_cases import CASES
from research.runtime.dag_overlap_cost import score
from research.runtime.dag_overlap_search import exact_search
from research.runtime.dag_staging_gate import BUDGETS, mm3
from research.runtime.strip_codesign import GEOMETRIES


def witness(graph, design):
    _, hardware, plan = design
    actual = replay(graph, hardware, events(graph, hardware, plan), prefetch=True, staging_report=True)
    if (actual["energy"], actual["ticks"]) != score(graph, hardware, plan, "prefetch"):
        raise ValueError("next-wave DMA pricing disagrees with the event calendar")
    return dict(architecture=asdict(hardware), groups=[asdict(group) for group in plan],
                edp=actual["energy"]*actual["ticks"], **actual)


def compare(graph, budget, geometries):
    start = perf_counter()
    joint, _ = exact_search(graph, budget, geometries, overlap="prefetch")
    search_seconds = perf_counter()-start
    old, _ = exact_search(graph, budget, geometries)
    order = tuple(op.name for op in graph.ops)
    tied = set()
    initial, _ = exact_search(graph, budget, geometries, fixed_order=order, overlap="prefetch", tied_shapes=tied)
    shape = joint[1].px, joint[1].py
    if objective(initial) == objective(joint):
        fixed = initial
    elif shape in tied:
        fixed = joint
    else:
        fixed, _ = exact_search(graph, budget, tuple(sorted(tied)), overlap="prefetch")
    result = {name: witness(graph, design) for name, design in (("joint", joint), ("architecture_first", fixed),
                                                               ("prior_mapping", old))}
    for name in ("joint", "architecture_first"):
        if result[name]["edp"] != objective(joint if name == "joint" else fixed):
            raise ValueError("prefetch optimum did not replay exactly")
    reductions = {name: 1-result["joint"]["edp"]/result[name]["edp"] for name in ("architecture_first", "prior_mapping")}
    if min(reductions.values()) < 0:
        raise ValueError("a control improved on the exact policy optimum")
    return dict(budget_bytes=budget, search_s=search_seconds, previous_edp_without_prefetch=objective(old),
                fixed_order_architectures=sorted(tied), reductions=reductions, **result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    workloads = {"3mm": mm3, **CASES}
    parser.add_argument("--cases", nargs="+", choices=workloads, default=list(workloads))
    parser.add_argument("--budgets", nargs="+", type=int, choices=BUDGETS, default=BUDGETS)
    parser.add_argument("--projection", action="store_true", help="Use the three common STREAM array shapes.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    shapes = ((32, 192), (48, 128), (64, 96)) if args.projection else GEOMETRIES
    rows = []
    for name in args.cases:
        for budget in args.budgets:
            result = compare(workloads[name](), budget, shapes)
            rows.append(dict(case=name, **result))
            print(name, budget, result["search_s"], result["reductions"], flush=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(dict(geometries=shapes, cases=rows), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
