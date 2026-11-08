"""Measure decision regret from timing assumptions under the same physical replay."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from research.runtime.dag_architecture_gate import graphs, objective, tied_architectures
from research.runtime.dag_calendar import events, replay
from research.runtime.dag_cases import CASES
from research.runtime.dag_model import Graph, Op, lifetimes
from research.runtime.dag_overlap_cost import score
from research.runtime.dag_overlap_search import exact_search


BUDGETS = (131072, 135168)


def mm3():
    return Graph(256, (("X", 256),), (Op("A", ("X",), 256), Op("B", ("A",), 256), Op("Y", ("B",), 256)))


def audited(graph, design):
    expected, hardware, plan = design
    actual = replay(graph, hardware, events(graph, hardware, plan), staging_report=True)
    if (actual["energy"], actual["ticks"]) != score(graph, hardware, plan):
        raise AssertionError("the executable and analytic finite calendars disagree")
    if actual["energy"] != expected[0]:
        raise AssertionError("timing controls changed the energy accounting")
    dram = sum(words for name, words in actual["actions"].items() if name.startswith("dram/"))
    return dict(architecture=asdict(hardware), groups=[asdict(group) for group in plan],
                predicted_ticks=expected[1], predicted_edp=expected[0]*expected[1],
                edp=actual["energy"]*actual["ticks"], dram_words=dram, **actual)


def compare(graph, budget):
    order = tuple(op.name for op in graph.ops)
    joint, _ = exact_search(graph, budget)
    finite = audited(graph, joint)
    by_model = {}
    for mode in ("free_staging", "serial", "roofline"):
        winner, _ = exact_search(graph, budget, overlap=mode)
        result = audited(graph, winner)
        if (mode in ("free_staging", "roofline") and result["predicted_ticks"] > result["ticks"]
                or mode == "serial" and result["predicted_ticks"] < result["ticks"]):
            raise AssertionError("control pricing violates the intended latency bound")
        by_model[mode] = result
    initial, _ = exact_search(graph, budget, fixed_order=order)
    profile = tuple(lifetimes(graph, order))
    tied = tied_architectures(graph, budget, profile, objective(initial), False, order)
    fixed, _ = exact_search(graph, budget, tied)
    by_model["architecture_first"] = audited(graph, fixed)
    for result in by_model.values():
        if result["edp"] < finite["edp"]:
            raise AssertionError("a control beats the independently replayed finite optimum")
        result["regret"] = result["edp"]/finite["edp"]-1
    return dict(budget_bytes=budget, rows=graph.rows, finite=finite, controls=by_model,
                fixed_order_architectures=tied, fixed_order_first=audited(graph, initial))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    workloads = {"3mm": mm3, **CASES}
    parser.add_argument("--cases", nargs="+", choices=workloads, default=list(workloads))
    parser.add_argument("--thresholds", action="store_true", help="Use the registered 24 synthetic threshold points.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if args.thresholds:
        points = ((dict(case=family, width=width, offset=offset), graph, budget)
                  for family, width, offset, budget, graph, _ in graphs())
    else:
        points = ((dict(case=name), workloads[name](), budget) for name in args.cases for budget in BUDGETS)
    results = []
    for metadata, graph, budget in points:
        row = compare(graph, budget)
        results.append(dict(**metadata, **row))
        print(json.dumps(dict(**metadata, budget=budget, regrets={name: value["regret"]
                         for name, value in row["controls"].items()})), flush=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(results, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
