"""Measure joint DAG decisions and verify every incumbent independently."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from time import perf_counter

from research.runtime.dag_calendar import events, replay
from research.runtime.dag_cases import CASES
from research.runtime.dag_overlap_search import exact_search, transition_orders


BUDGETS = (131072, 135168, 262144)


def audited(graph, design):
    cost, h, plan = design
    witness = replay(graph, h, events(graph, h, plan))
    if cost != (witness["energy"], witness["ticks"]):
        raise AssertionError("independent event calendar disagrees with DAG search")
    return dict(architecture=asdict(h), groups=[asdict(g) for g in plan], edp=cost[0] * cost[1], **witness)


def run(cases, budgets):
    results = {}
    for name in cases:
        graph = CASES[name]()
        order = tuple(op.name for op in graph.ops)
        pruned, _, _ = transition_orders(graph)
        full, _, _ = transition_orders(graph, prune_orders=False)
        rows = []
        for capacity in budgets:
            t0 = perf_counter()
            result, geometries = exact_search(graph, capacity)
            elapsed = perf_counter() - t0
            joint = audited(graph, result)
            no_fusion, _ = exact_search(graph, capacity, singleton=True)
            preset = (no_fusion[1].px, no_fusion[1].py)
            hardware_first, _ = exact_search(graph, capacity, (preset,))
            fixed_order, _ = exact_search(graph, capacity, fixed_order=order)
            refs = {key: audited(graph, design) for key, design in
                    (("singleton", no_fusion), ("architecture_first", hardware_first), ("fixed_order", fixed_order))}
            if any(row["edp"] < joint["edp"] for row in refs.values()):
                raise AssertionError("restricted control beats the joint optimum")
            rows.append(dict(budget_bytes=capacity, search_s=elapsed, geometries=geometries,
                             joint=joint, controls=refs))
            print(json.dumps(dict(case=name, budget=capacity, seconds=elapsed,
                                  architecture=joint["architecture"], order=[g["order"] for g in joint["groups"]],
                                  edp=joint["edp"], overlap=joint["overlapped_waves"],
                                  reductions={k: 1-joint["edp"]/v["edp"] for k, v in refs.items()})), flush=True)
        results[name] = dict(graph=asdict(graph), states=len(full),
                             transitions=sum(map(len, full.values())),
                             retained_transitions=sum(map(len, pruned.values())), outcomes=rows)
    return dict(energy_unit_j=4e-15, tick_seconds=1e-9/1536, cases=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--budgets", nargs="+", type=int, choices=BUDGETS, default=BUDGETS)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = run(args.cases, args.budgets)
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
