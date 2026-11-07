"""Run the complete pinned STREAM pipeline on the shared branched workload."""

import argparse
from importlib.metadata import version
import json
from math import prod
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter

from xdsl.dialects.builtin import i8
from xdsl.ir.affine import AffineMap

from stream.api import SolveOptions, evaluate_mapping
from stream.workload.node import ComputationNode, InEdge, OutEdge
from stream.workload.tensor import Tensor
from stream.workload.workload import Workload

from research.external_stream.hardware import project
from research.external_stream.run import core_mappings
from research.runtime.dag_cases import CASES


def build(graph, order=None):
    tensors = {name: Tensor.create(name, i8, (graph.rows, width)) for name, width in graph.inputs}
    nodes = [InEdge(name=name, outputs=(tensor,)) for name, tensor in tensors.items()]
    gemm_maps = tuple(AffineMap.from_callable(fn) for fn in (
        lambda m, k, n: (m, k), lambda m, k, n: (k, n), lambda m, k, n: (m, n)
    ))
    ops = graph.ops if order is None else (graph.operators[name] for name in order)
    for op in ops:
        inputs = [tensors[name] for name in op.inputs]
        out = Tensor.create(op.name, i8, (graph.rows, op.width))
        if op.kind == "gemm":
            weights = Tensor.create("W_" + op.name, i8, (graph.widths[op.inputs[0]], op.width))
            nodes.append(InEdge(name=weights.name, outputs=(weights,), parameter=True))
            inputs.append(weights)
        maps = gemm_maps if op.kind == "gemm" else (AffineMap.identity(2),) * 3
        kind = {"gemm": "MatMul", "add": "Add", "mul": "Mul"}[op.kind]
        nodes.append(ComputationNode(name=op.name, type=kind, inputs=tuple(inputs),
                                     outputs=(out,), operand_mapping=maps))
        tensors[op.name] = out
    nodes.extend(OutEdge(name=f"sink_{name}", inputs=(tensors[name],)) for name in graph.outputs)
    return Workload(nodes)


def verify_graph(workload, graph):
    manifest = []
    for node in workload.dataflow_sort():
        if not isinstance(node, ComputationNode):
            continue
        op = graph.operators[node.name]
        count = prod(workload.get_dimension_size(d) for d in workload.get_dims(node))
        expected = graph.rows * op.width * (graph.widths[op.inputs[0]] if op.kind == "gemm" else 1)
        if count != expected or any(t.operand_type.bitwidth != 8 for t in node.tensors):
            raise AssertionError("STREAM changed the graph's work or precision")
        if tuple(t.name for t in node.inputs[:len(op.inputs)]) != op.inputs:
            raise AssertionError("STREAM changed an activation edge")
        manifest.append(dict(name=node.name, dependencies=op.inputs, iterations=count,
                             precision_bits=8, kind=node.type))
    if len(manifest) != len(graph.ops):
        raise AssertionError("STREAM graph has missing operators")
    return manifest


def inspect_schedule(allocations, local_maps, manifest, capacity):
    overlap = {}
    footprint = {}
    for group, allocation in allocations.items():
        timing = allocation["latency"]
        cycles = timing.get("overlap_between_iterations", 0)
        if cycles:
            overlap[group] = cycles
        footprint[group] = allocation["performance"]["memory_occupancy"]
    traced = {entry["node"] for entry in local_maps}
    # The DAG calendar completes each band's operation before the next one.
    # Cross-iteration overlap is an independent scheduling decision in STREAM.
    failures = []
    if overlap:
        failures.append("inter-iteration overlap has no equivalent in the common calendar")
    missing = sorted({op["name"] for op in manifest} - traced)
    if missing:
        failures.append("operand mappings for earlier groups were not exposed")
    gemm_nodes = {op["name"] for op in manifest if op["kind"] == "MatMul"}
    fanout = []
    for entry in local_maps:
        if entry["node"] not in gemm_nodes:
            continue
        axes = entry["spatial_by_axis"]
        if any(dim != wanted and factor > 1
               for axis, wanted in (("D1", "D2"), ("D2", "D1"))
               for dim, factor in axes.get(axis, [])):
            fanout.append(entry["node"])
    if fanout:
        failures.append("GEMM wave uses a different physical reuse axis")
    failures.append("no lossless translation of STREAM lifetimes, tile issue and transfer events")
    return dict(shared_sram_bytes=capacity, overlap_between_iterations=overlap,
                native_occupancy=footprint, missing_local_mappings=missing, different_fanout=fanout,
                full_schedule_translated=False, mismatches=failures)


def run(name, shape, seconds, tile_search, row_band):
    graph = CASES[name]()
    workload = build(graph)
    manifest = verify_graph(workload, graph)
    root = Path(__file__).resolve().parents[2]
    checkout = root / "libraries" / "stream"
    with TemporaryDirectory(prefix="stream-fork-join-") as temporary:
        path = Path(temporary)
        t0 = perf_counter()
        hardware = project(path, *shape)
        options = {}
        if row_band is not None:
            options["intra_core_tiling"] = [{"dim": op.name + ".D0", "tile": row_band} for op in graph.ops]
        estimate = evaluate_mapping(str(hardware), workload, str(path / "out"), options=SolveOptions(
            time_limit_s=seconds, tile_search=tile_search, artifacts=False, stage_options=options
        ))
        elapsed = perf_counter() - t0
        allocation = estimate.context.get("group_allocations")
        mappings = core_mappings(estimate.context)
    if not allocation or not all(allocation.values()):
        raise ValueError("STREAM failed to allocate a fusion group")
    return dict(case=name, graph=manifest, geometry=dict(zip(("px", "py", "capacity_bytes"), shape)),
                stream_revision=subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                                                        text=True).strip(),
                versions={pkg: version(pkg) for pkg in ("stream-dse", "zigzag-dse", "ortools")},
                tile_search=tile_search, requested_row_band=row_band, seconds=elapsed, vendor_cycles=estimate.cycles,
                groups=estimate.group_cycles, allocation=allocation, local_mappings=mappings,
                intersection=inspect_schedule(allocation, mappings, manifest, shape[-1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--geometry", type=int, nargs=3, required=True)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--tile-search", action="store_true")
    parser.add_argument("--row-band", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = run(args.case, args.geometry, args.seconds, args.tile_search, args.row_band)
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ("case", "vendor_cycles", "groups", "intersection")}))


if __name__ == "__main__":
    main()
