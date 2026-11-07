"""Check exported STREAM schedules against the first native mapping intersection."""

import argparse
from collections import defaultdict
import json
from math import prod
from pathlib import Path


def audit(report, px, py, capacity):
    issues = defaultdict(list)
    for group_id, group in report["allocation_ir"].items():
        latency = group["latency"]
        if latency["overlap_between_iterations"] or group["performance"]["overlap"]["overlap_cycles"]:
            issues["overlapped_execution"].append(group_id)
        for node, metrics in group["performance"]["nodes"].items():
            if metrics["n_cores"] != 1:
                issues["multicore_operator"].append(node)
        compute_cores = {
            location["id"]
            for node in group["mapping_nodes"].values()
            for allocations in node["resource_allocation"]
            for location in allocations
            if location["type"] == "core"}
        if len(compute_cores) != 1:
            issues["different_compute_cores"].append(sorted(compute_cores))
        for layout in group["performance"]["layouts"]:
            if layout["converts"]:
                issues["explicit_layout_conversion"].append(layout["transfer"])
        memories = [m for m in group["performance"]["memory_occupancy"] if m["cores"]]
        if len(memories) != 1 or memories[0]["capacity_bits"] != capacity * 8:
            issues["buffer_geometry"].append([m["capacity_bits"] for m in memories])
        if sum(m["resident_bits"] for m in memories) > capacity * 8:
            issues["buffer_footprint"].append(sum(m["resident_bits"] for m in memories))
        sizes = defaultdict(list)
        for loop in group["steady_state"]["loops"]:
            if loop["type"] not in ("core_spatial", "core_temporal"):
                continue
            sizes[(loop["node"], loop["dim"])].append(loop["size"])
        for (node, dim), factors in sizes.items():
            if any(factor < 1 or factor & (factor - 1) for factor in factors):
                issues["outside_perfect_power_of_two_factor_space"].append(
                    dict(node=node, dim=dim, factors=factors, product=prod(factors)))
    if report.get("projected_hardware") != dict(px=px, py=py, capacity_bytes=capacity):
        issues["no_matching_declared_fanout_and_capacity"].append(report["hardware"])
    expected_nodes = {node["name"] for node in report["affine_workload"]}
    traced = {node["node"] for node in report.get("last_group_core_mappings", ())}
    if expected_nodes - traced:
        issues["missing_exact_operand_residency_and_spatial_axis"].extend(sorted(expected_nodes - traced))
    # A geometry projection does not establish equal execution/action semantics.
    # Even with complete core schedules, no converter currently validates the
    # outer graph's transfer schedules and tensor lifetime against native FFM.
    issues["outer_schedule_not_replayed_in_native_evaluator"].append("all fusion groups")
    return dict(status="rejected_from_current_native_intersection",
                evaluated_schedules=1, translated_schedules=0, failures=dict(issues),
                domain=dict(px=px, py=py, capacity_bytes=capacity),
                external_sota_acceptance=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--px", type=int, default=64)
    parser.add_argument("--py", type=int, default=96)
    parser.add_argument("--capacity", type=int, default=32768)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(json.loads(args.report.read_bytes()), args.px, args.py, args.capacity)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
