"""Stress architectural choices around fork and residual live-set thresholds."""

import argparse
import json
from pathlib import Path

from research.joint_budget.protocol import Hardware
from research.runtime.benchmark_dag_calendar import audited
from research.runtime.dag_model import Graph, Op, lifetimes
from research.runtime.dag_overlap_search import exact_search, lower_geometry
from research.runtime.strip_codesign import GEOMETRIES


WIDTHS = (192, 256, 320)
BUDGETS = (131072, 135168)
OFFSETS = (-1, 1)


def graphs():
    for width in WIDTHS:
        templates = {
            "fork": (
                Op("S", ("X",), width), Op("A", ("S",), width), Op("B", ("S",), width),
                Op("J", ("A", "B"), width, "add"),
            ),
            "residual": (
                Op("S", ("X",), width), Op("A", ("S",), width * 2), Op("B", ("A",), width),
                Op("J", ("S", "B"), width, "add"),
            ),
        }
        for kind, ops in templates.items():
            order = tuple(op.name for op in ops)
            inputs = (("X", width),)
            nominal = tuple(lifetimes(Graph(1, inputs, ops), order))
            live = max(step.live_width for step in nominal)
            for budget in BUDGETS:
                for offset in OFFSETS:
                    rows = (budget - 3072) // live + offset
                    yield kind, width, offset, budget, Graph(rows, inputs, ops), order


def objective(result):
    e, t = result[0]
    return e * t


def tied_architectures(graph, budget, profile, optimum, singleton, order):
    eligible = []
    for x, y in GEOMETRIES:
        if lower_geometry(graph, Hardware(x, y, budget), profile) > optimum:
            continue
        witness, _ = exact_search(graph, budget, ((x, y),), singleton=singleton,
                                  fixed_order=None if singleton else order)
        if objective(witness) < optimum:
            raise AssertionError("architecture-first enumeration missed a shape")
        if objective(witness) == optimum:
            eligible.append((x, y))
    return tuple(eligible)


def run():
    outcomes = []
    for family, width, offset, budget, graph, order in graphs():
        joint, _ = exact_search(graph, budget)
        profile = tuple(lifetimes(graph, order))
        controls = {}
        for name, singleton in (("singleton_then_fuse", True), ("fixed_order_then_reorder", False)):
            initial, _ = exact_search(graph, budget, singleton=singleton,
                                      fixed_order=None if singleton else order)
            tied = tied_architectures(graph, budget, profile, objective(initial), singleton, order)
            search, _ = exact_search(graph, budget, tied)
            controls[name] = dict(tied_geometries=tied, witness=audited(graph, search),
                                  gain=1-objective(joint)/objective(search))
        outcomes.append(dict(family=family, width=width, offset=offset, budget_bytes=budget,
                             rows=graph.rows, joint=audited(graph, joint), controls=controls))
        print(json.dumps(dict(family=family, width=width, rows=graph.rows, budget=budget,
                              gains={name: row["gain"] for name, row in controls.items()})), flush=True)
    return dict(widths=WIDTHS, offsets=OFFSETS, budgets=BUDGETS, transition_target_bytes=3072, cases=outcomes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = run()
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
