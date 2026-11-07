"""Make branch issue order explicit and audit the resulting STREAM allocation."""

import argparse
from contextlib import contextmanager
from dataclasses import replace
import json
from math import ceil, isclose
from pathlib import Path
from unittest.mock import patch

import networkx as nx
from stream import api
from stream.stages.allocation.steady_state_allocation import AllocationStage
from stream.stages.generation import normalization_expansion
from stream.stages.generation.tile_search import TileSearchStage
from stream.stages.stage import Stage
from stream.workload.node import ComputationNode, InEdge, OutEdge
from stream.workload.workload import Workload

from research.external_stream.dag import build, verify_graph
from research.external_stream.dag_host import evaluate, graph_order
from research.runtime.dag_cases import CASES


class SlotGraph(nx.DiGraph):
    def node_positions(self):
        return {node: index for index, node in enumerate(self.nodes)}


def ordered_problem(problem, order):
    """Add compute precedence only to slot placement, preserving all tensor edges."""
    nodes = {node.name: node for node in problem.workload.get_computation_nodes()}
    ordered = [nodes[name] for name in order if name in nodes]
    if len(ordered) != len(nodes):
        raise ValueError("the issue order must cover every lowered computation")
    if len(ordered) < 2:
        return problem
    slots = SlotGraph(problem.workload)
    slots.add_edges_from(zip(ordered, ordered[1:]))
    timeslots = Workload.get_timeslots(slots, problem.mapping)
    return replace(problem, timeslots=timeslots)


def timing_witness(allocation):
    problem, solution = allocation.problem, allocation.solution
    latency, slots = solution.latency, solution.slot_latencies
    if not isclose(sum(slots.values()), latency.per_iteration, abs_tol=1e-5):
        raise ValueError("slot durations do not reconstruct the native period")
    period = latency.per_iteration - latency.overlap
    total = latency.per_iteration + (problem.iterations-1) * period + latency.fill
    if period <= 0 or latency.fill < 0 or total != latency.total:
        raise ValueError("period, fill and iteration count do not reconstruct native cycles")
    if any(problem.timeslots[src] >= problem.timeslots[dst] for src, dst in problem.workload.edges):
        raise ValueError("a native tensor dependency crosses slots out of order")
    breakdown = solution.slot_latency_breakdown
    if breakdown is None or solution.performance is None:
        raise ValueError("native timing records are missing")
    starts = {}
    elapsed = 0.0
    for slot, duration in sorted(slots.items()):
        starts[slot] = elapsed
        elapsed += duration
    core = []
    link = []
    for row in breakdown["slots"]:
        slot = row["slot"]
        for entry in row["compute_contributors"]:
            core.append((slot, entry["node"], entry["active_latency_cycles"], entry["active_fraction"]))
        for entry in row["transfer_contributors"]:
            if entry["latency_contribution_cycles"] > 0:
                link.append((slot, entry["transfer"], entry["latency_contribution_cycles"]))
    issue = tuple(name for _, name, _, _ in sorted(core))
    by_slot = tuple(node.name for node in sorted(problem.workload.get_computation_nodes(),
                                                key=problem.timeslots.__getitem__))
    if issue != by_slot or len({row[0] for row in core}) != len(core):
        raise ValueError("native compute report does not describe one array's issue order")
    ports = []
    for row in solution.performance["memory_ports"]:
        rate, bits = row["bw_bits_per_cycle"], row["bits_per_iteration"]
        if (not isclose(row["allowed_cycle"], period, abs_tol=1e-5)
                or not isclose(row["real_cycle"], bits/rate, abs_tol=1e-5)):
            raise ValueError("native port report does not reconstruct its demand")
        if row["kind"] == "memory_port" and (bits > rate * period + 1e-5
                or (row["burst_utilization"] or 0) > 1 + 1e-6):
            raise ValueError("native port report exceeds its slot or period bandwidth")
        ports.append((row["kind"], row["resource"], rate, bits, row["burst_utilization"]))

    def conflicts(events):
        # A single-core, single-link topology, with representative slots repeated at the solved II.
        copies = min(problem.iterations, ceil(latency.per_iteration/period) + 1)
        windows = sorted((k*period + starts[slot], k*period + starts[slot] + duration, k, name)
                         for k in range(copies) for slot, name, duration, *_ in events if duration > 0)
        return [(left[2:], right[2:]) for left, right in zip(windows, windows[1:])
                if left[1] > right[0] + 1e-5]

    return dict(issue_order=issue, iterations=problem.iterations, cycles=total, fill=latency.fill,
                period=period, overlap=latency.overlap, slots=tuple(sorted(slots.items())),
                compute=tuple(sorted(core)), transfers=tuple(sorted(link)), ports=ports,
                fractional_compute=sum(fraction != 1 for *_, fraction in core),
                representative_core_conflicts=conflicts(core), representative_link_conflicts=conflicts(link))


@contextmanager
def observe_stream(order, witnesses):
    """Keep the native tiler, inner allocation and costing for both issue policies."""

    def keep_order(workload):
        if any(type(node) not in (InEdge, OutEdge, ComputationNode) for node in workload.nodes):
            raise ValueError("explicit issue order requires an already normalized affine DAG")
        if graph_order(workload) != order:
            raise ValueError("the source DAG does not match the requested issue order")
        return workload

    class OrderSlots(Stage):
        reads = ("allocation_problem",)
        writes = ("allocation_problem",)

        def run(self):
            problem = self.ctx.get("allocation_problem")
            self.ctx.set(allocation_problem=ordered_problem(problem, order))
            yield from self.list_of_callables[0](self.list_of_callables[1:], self.ctx).run()

    class Observe(Stage):
        result_reads = ("allocation",)

        def run(self):
            for result in self.list_of_callables[0](self.list_of_callables[1:], self.ctx).run():
                witnesses.append(result.get("allocation"))
                yield result

    stages = list(api._ALLOCATION_STAGES)
    stages.insert(stages.index(TileSearchStage), Observe)
    if order is None:
        with patch.object(api, "_ALLOCATION_STAGES", stages):
            yield
    else:
        stages.insert(stages.index(AllocationStage), OrderSlots)
        with (patch.object(api, "_ALLOCATION_STAGES", stages),
              patch.object(normalization_expansion, "expand_normalizations", keep_order)):
            yield


def price(workload, shape, cuts, limit, order=None, audit=True):
    allocations = []
    with observe_stream(order, allocations):
        result = evaluate(workload, shape, cuts, limit)
    if not result["feasible"]:
        return result
    issued = [tuple(node.name for node in sorted(a.problem.workload.get_computation_nodes(),
                                                 key=a.problem.timeslots.__getitem__)) for a in allocations]
    if len(issued) != len(result["groups"]):
        raise ValueError("native trace did not retain every successful group")
    if order is not None and sum(issued, ()) != order:
        raise ValueError("the requested issue order was not executed")
    result["issue_order"] = issued
    if audit:
        result["timing"] = [timing_witness(a) for a in allocations]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    graph = CASES["glu"]()
    declared = tuple(op.name for op in graph.ops)
    reversed_fork = (declared[1], declared[0], *declared[2:])
    results = []
    for order in (None, declared, reversed_fork):
        workload = build(graph, order)
        verify_graph(workload, graph)
        result = price(workload, (32, 192, 131072), (), 10, order)
        if not result["feasible"]:
            raise ValueError(f"expected feasible GLU timing witness: {result}")
        results.append(dict(requested_order=order, **result))
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(results, indent=2, allow_nan=False) + "\n")
    for row in results:
        print(row["issue_order"], row["cycles"], row["edp"], flush=True)


if __name__ == "__main__":
    main()
