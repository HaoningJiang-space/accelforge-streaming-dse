"""Replay square strip winners through the original AccelForge mapping IR."""

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from accelforge.frontend import mapping as ir
from research.joint_budget.protocol import Hardware
from research.joint_physical.replay import encode
from research.runtime.audit_memory_trace import count
from research.runtime.strip_codesign import Segment
from research.runtime.strip_trace import replay
from research.runtime.tail_tiles import exact_tail_evaluation, numeric
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build


def temporal(rank, width):
    node = ir.Temporal(rank_variable=rank, tile_shape=width)
    node._assume_perfect_factor = False
    return node


def storage(level, tensors):
    node = ir.Storage(component=level, tensors=tensors)
    node._lower = False  # Shared strip storage must stay above the stage's private loops.
    return node


def translate(plan, array):
    groups = []
    for segment in plan:
        start, stop = segment.start, segment.stop
        weights = [f"W{i}" for i in range(start, stop)]
        prefix = [storage("MainMemory", [f"T{start}", f"T{stop}", *weights])]
        pinned = [name for name, pin in zip(weights, segment.pinned) if pin]
        if pinned:
            prefix.append(storage("GlobalBuffer", pinned))
        prefix.extend([temporal("m", segment.rows),
                       storage("GlobalBuffer", [f"T{i}" for i in range(start, stop+1)])])
        stages = []
        for i, ((p, q), pin) in enumerate(zip(segment.tiles, segment.pinned), start):
            k, n, w = f"n{i}", f"n{i+1}", f"W{i}"
            nodes = [temporal(n, q), temporal(k, p)]
            if not pin:
                nodes.append(storage("GlobalBuffer", [w]))
            nodes.extend(ir.Spatial(component="ArrayFanout", rank_variable=rank, tile_shape=1,
                                    name=axis, component_object=array)
                         for rank, axis in ((k, "reuse_output"), (n, "reuse_input")))
            nodes.extend([storage("Register", [w]), temporal("m", 1),
                          ir.Compute(component="MAC", einsum=f"Matmul{i}")])
            stages.append(ir.Nested(nodes=nodes))
        groups.append(ir.Nested(nodes=[*prefix, ir.Sequential(nodes=stages)]))
    return ir.Mapping(nodes=[ir.Sequential(nodes=groups)])


def native_actions(words):
    names = {"DRAM": "MainMemory", "SRAM": "GlobalBuffer", "RF": "Register", "MAC": "MAC"}
    counts = Counter()
    for (i, level, tensor, direction), value in words.items():
        if level == "MAC":
            counts[f"Matmul{i}<SEP>action<SEP>MAC<SEP>None<SEP>compute"] += value
        else:
            counts[f"Matmul{i}<SEP>action<SEP>{names[level]}<SEP>{tensor}<SEP>{direction}"] += value * 8
    return counts


def run(raw):
    report = json.loads(raw)
    common.af.set_n_parallel_jobs(1)
    results = []
    for name, workload in report["cases"].items():
        rows, widths = workload["rows"], workload["widths"]
        if len(set(widths)) != 1:
            continue
        stages, width = len(widths)-1, widths[0]
        case = common.Case("matmuls", "nvdla", (stages, rows, width))
        for entry in workload["outcomes"]:
            winner = entry["winners"]["dp"]
            point = winner["architecture"]
            h = Hardware(**point)
            plan = [Segment(**group) for group in winner["mapping"]]
            spec = build(case, (h.px, h.py), h.capacity_bytes, common.RU)
            record = encode(translate(plan, spec.arch.find("ArrayFanout")))
            _, peak, events = replay(rows, widths, h, plan)
            reference = native_actions(events)
            if count(record, rows, width, stages) != reference:
                raise AssertionError("serialized mapping does not reproduce independent wave counts")
            with exact_tail_evaluation():
                witness, _, _, _ = numeric(case, point, record)
            if not witness["feasible"] or witness["gb_bytes"] != peak:
                raise AssertionError("native SRAM peak differs from the independent trace")
            native = witness["actions"]
            differences = {key: [reference[key], int(native.get(key, 0))]
                           for key in sorted(reference.keys() | native.keys())
                           if reference[key] != native.get(key, 0)}
            outcome = dict(case=name, budget_bytes=entry["budget_bytes"], architecture=asdict(h),
                           peak_bytes=peak, mapping_id=witness["mapping_id"], native_fusion_validated=True,
                           independent_projection_agrees=True, native_actions_agree=not differences,
                           native_action_differences=differences)
            results.append(outcome)
            print(json.dumps(outcome), flush=True)
    return dict(source_sha256=hashlib.sha256(raw).hexdigest(), selections=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = run(args.reference.read_bytes())
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
