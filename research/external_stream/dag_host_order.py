"""Test whether live-set ordering changes joint design quality in full STREAM."""

import argparse
import json
from math import isclose
from pathlib import Path
from time import perf_counter

from research.external_stream.dag import build, verify_graph
from research.external_stream.dag_host import GEOMETRIES, evaluate, graph_order
from research.runtime.dag_cases import CASES
from research.runtime.dag_overlap_search import transition_orders


def order_choices(graph):
    declared = tuple(op.name for op in graph.ops)
    transitions, profiles, terminal = transition_orders(graph, prune_orders=False)

    def live_cost(order):
        sizes = [step.live_width for step in profiles[order]]
        return max(sizes), sum(sizes), order != declared, order

    compact = min((order for end, order in transitions[0] if end == terminal), key=live_cost)
    return tuple((order, live_cost(order)[:2]) for order in dict.fromkeys((declared, compact)))


def select(trials, order):
    valid = [row for row in trials if row["feasible"]]
    if not valid:
        return {}
    joint = min(valid, key=lambda row: row["edp"])
    fixed = [row for row in valid if row["order"] == order]
    incumbent = min(fixed, key=lambda row: row["edp"], default=None)
    geometry = {tuple(row["shape"]) for row in fixed
                if isclose(row["edp"], incumbent["edp"], rel_tol=1e-12)}
    fixed_arch = min((row for row in valid if tuple(row["shape"]) in geometry),
                     key=lambda row: row["edp"], default=None)
    return dict(joint=joint, fixed_order=incumbent, fixed_order_architectures=sorted(geometry),
                fixed_order_then_reorder=fixed_arch,
                gain_over_fixed_order=1-joint["edp"]/incumbent["edp"] if incumbent else None,
                gain_over_architecture_first=1-joint["edp"]/fixed_arch["edp"] if fixed_arch else None)


def cut_options(order, shallow):
    if shallow:
        yield None
        yield ()
        yield from ((cut,) for cut in order[:-1])
    else:
        yield order[:-1]
        # Reopen exactly one boundary after giving the full per-layer plan to both orders.
        yield from (order[:i] + order[i+1:-1] for i in range(len(order)-1))


def run(name, budget, limit, shallow):
    graph = CASES[name]()
    candidates = order_choices(graph)
    start = perf_counter()
    trials = []
    for order, live in candidates:
        workload = build(graph, order)
        verify_graph(workload, graph)
        if graph_order(workload) != order:
            raise AssertionError("STREAM did not retain the declared graph ordering")
        for cuts in cut_options(order, shallow):
            for x, y in GEOMETRIES:
                row = evaluate(workload, (x, y, budget), cuts, limit)
                row.update(order=order, live_width=live)
                trials.append(row)
                print(json.dumps({key: row.get(key) for key in
                                 ("order", "cuts", "shape", "status", "feasible", "edp")}), flush=True)
    comparison = select(trials, candidates[0][0])
    return dict(case=name, budget_bytes=budget, order_choices=candidates, shallow=shallow,
                limit_per_allocation_s=limit,
                wall_s=perf_counter()-start, comparison=comparison, trials=trials)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, default="asymmetric")
    parser.add_argument("--budget", type=int, default=131072)
    parser.add_argument("--limit", type=float, default=10)
    parser.add_argument("--near-singletons", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = run(args.case, args.budget, args.limit, not args.near_singletons)
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
