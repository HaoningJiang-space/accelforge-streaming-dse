"""Run the pinned external mapper and export its original allocation IR."""

import argparse
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory
import time

from stream.api import SolveOptions, evaluate_mapping

from .workloads import attention_proxy, inspect, three_mm
from .hardware import project


def core_mappings(context):
    lut = context.get("cost_lut")
    if lut is None:
        return []
    mappings = []
    for node in lut.get_nodes():
        for core in lut.get_cores(node):
            entry = lut.get_cost(node, core)
            cme = entry.cme
            if cme is None or entry.layer is None:
                continue
            temporal = cme.temporal_mapping.mapping_dic_origin
            spatial = cme.layer.spatial_mapping
            mappings.append(dict(node=node.name, core=core.id,
                temporal_inner_to_outer={str(op): [[[str(dim), float(factor)] for dim, factor in level]
                                         for level in levels] for op, levels in temporal.items()},
                spatial_by_axis={str(axis): [[str(dim), float(factor)] for dim, factor in spatial[axis].items()]
                                 for axis in spatial}))
    return mappings


def run(args):
    root = Path(__file__).resolve().parents[2]
    stream_checkout = root / "libraries" / "stream"
    hardware = stream_checkout / "stream" / "inputs" / "examples" / "hardware" / f"{args.hardware}.yaml"
    if args.workload == "3mm":
        graph = three_mm(args.size, args.size)
        expected = [args.size**3] * 3
    else:
        graph = attention_proxy(args.size)
        expected = [args.size**2 * 64, args.size**2, args.size**2 * 64]
    manifest = inspect(graph, expected)
    result = {
        "workload": args.workload, "size": args.size, "affine_workload": manifest,
        "stream_version": version("stream-dse"), "zigzag_version": version("zigzag-dse"),
        "ortools_version": version("ortools"), "python": platform.python_version(),
        "stream_revision": subprocess.check_output(["git", "-C", str(stream_checkout), "rev-parse", "HEAD"],
                                                  text=True).strip(),
        "hardware": args.hardware, "cost_model": "official STREAM/ZigZag hardware and cost model",
        "matched_native_costs": False, "external_sota_acceptance": False,
        "status": "workload_validated",
    }
    if not args.workload_only:
        with TemporaryDirectory(prefix="stream-repro-") as temp:
            tmp = Path(temp)
            begin = time.perf_counter()
            if args.nvdla_geometry:
                hardware = project(tmp, *args.nvdla_geometry)
                result["projected_hardware"] = dict(zip(("px", "py", "capacity_bytes"), args.nvdla_geometry))
                result["hardware"] = "single-core NVDLA geometry projection; STREAM costs"
            estimate = evaluate_mapping(str(hardware), graph, str(tmp / "out"),
                options=SolveOptions(time_limit_s=args.limit, artifacts=False, tile_search=args.tile_search,
                    stage_options={"core_cost_options": {"zigzag": {"mapping_objective": args.local_objective}}}))
            trace = core_mappings(estimate.context)
            wall_s = time.perf_counter() - begin
        allocation = estimate.context.get("group_allocations")
        if not allocation or not all(allocation.values()):
            raise ValueError("STREAM did not produce a schedule for every fusion group")
        result.update(status="official_stream_solved", wall_s=wall_s,
                      solver="ortools_gscip", group_cycles=estimate.group_cycles, cycles=estimate.cycles,
                      tile_search=args.tile_search, allocation_ir=allocation,
                      local_objective=args.local_objective, last_group_core_mappings=trace)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", choices=("3mm", "attention"), required=True)
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--hardware", choices=("eyeriss_like_single_core", "tpu_like_quad_core"),
                        default="eyeriss_like_single_core")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=float, default=30)
    parser.add_argument("--tile-search", action="store_true")
    parser.add_argument("--nvdla-geometry", type=int, nargs=3, metavar=("PX", "PY", "SRAM_BYTES"))
    parser.add_argument("--local-objective", choices=("edp", "latency", "energy"), default="latency")
    parser.add_argument("--workload-only", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
