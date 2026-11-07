"""Co-search a MAC-equivalent pointwise allocation, SRAM, and native mappings."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time
from unittest.mock import patch

from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.enumeration_reuse import EnumerationReuse
from research.fusion_envelope.search import PolicyOracle, problem
from research.joint_budget import region_search
from research.joint_budget.protocol import Hardware
from research.joint_physical import replay as codec
from research.tracking_audit import common, shape_capacity_audit as validation


TOTAL_SITES = 6144
ROWS = 64
LANES = (0, 64, 128)


def geometry(lanes):
    if lanes not in LANES or (TOTAL_SITES - lanes) % ROWS:
        raise ValueError("unregistered compute split")
    return ROWS, (TOTAL_SITES - lanes) // ROWS


def builder(lanes, energy_scale=1.0):
    def build(case, shape, capacity, metrics, *args, **kwargs):
        if shape != geometry(lanes):
            raise ValueError("pointwise lanes plus MACs must match the compute-site budget")
        spec = validation_original(case, shape, capacity, metrics, *args, **kwargs)
        if lanes:
            # Fold the lane path into the native leaf's per-Einsum action.
            # Both paths share the same GlobalBuffer. The weight-only register
            # holds no value for this two-tensor operation. Width scales the
            # aggregate throughput, while each pointwise result pays its own
            # action energy. No extra spatial unrolling of that action is legal.
            action = next(a for a in spec.arch.find("MAC").actions if a.name == "compute")
            action.latency = f"1e-9 / {lanes} if len(All) == 2 else 1e-9"
            action.energy = f"0.084e-12 * {energy_scale!r} if len(All) == 2 else 0.084e-12"
        return spec
    return build


validation_original = validation.build


def compute_components(record):
    result = {record["einsum"]: record["component"]} if record["type"] == "Compute" else {}
    for child in record.get("nodes", ()):
        for name, component in compute_components(child).items():
            if name in result:
                raise ValueError(f"duplicate compute witness for {name}")
            result[name] = component
    return result


def run(workload, output, energy_scale):
    case, _, budgets = problem(workload, "factors96")
    if energy_scale < 1:
        raise ValueError("pointwise energy per action must be at least that of a MAC action")
    common.clear_switches()
    common.af.set_n_parallel_jobs(1)
    records = []
    started = time.perf_counter()
    for lanes in LANES:
        shape = geometry(lanes)
        assert shape[0] * shape[1] + lanes == TOTAL_SITES
        points = tuple(Hardware(*shape, b.max_sram_bytes) for b in budgets)
        oracle = PolicyOracle(case, "relaxed")
        physical = builder(lanes, energy_scale)
        with patch.object(region_search, "build", physical), EnumerationReuse() as cache:
            oracle.solve(shape, points, cache)
        picks = []
        with patch.object(validation, "build", physical):
            for point in points:
                row = common.best_row(oracle.outputs[point])
                witness = validation.validate_pick(case, shape, point.capacity_bytes, row, capture_actions=True)
                if not witness["ok"] or not witness["feasible"]:
                    raise ValueError("pointwise mapping is invalid")
                witness["mapping"] = codec.encode(row["Total<SEP>mapping"]())
                components = compute_components(witness["mapping"])
                proxy = next(s["used"] for s in witness["spatial"] if s["einsum"] == "QK_softmax")
                if proxy != [1, 1] or set(components) != {"QK", "QK_softmax", "AV"}:
                    raise ValueError("pointwise throughput action was replicated or compute scope changed")
                picks.append(dict(architecture=asdict(point), pointwise_lanes=lanes,
                                  compute_components=components,
                                  logical_compute_paths={"QK":"MAC array","AV":"MAC array",
                                      "QK_softmax":"pointwise lanes" if lanes else "MAC array"},
                                  witness=witness))
        records.append(dict(pointwise_lanes=lanes, shape=shape, maps=picks, native_oracle=oracle.details))
        print(json.dumps(dict(pointwise_lanes=lanes, shape=shape,
                              edp=[p["witness"]["edp"] for p in picks])), flush=True)
    best = [min((p for r in records for p in r["maps"] if p["architecture"]["capacity_bytes"]<=b.max_sram_bytes),
                key=lambda p:p["witness"]["edp"]) for b in budgets]
    result = dict(status="complete", case=dict(workload=case.workload, arch=case.arch, params=list(case.params)),
                  scope="three registered compute splits, four SRAM budgets, native Event mapspace per split",
                  physical_implementation_validated=False, external_sota_acceptance=False,
                  cost_assumption="one MAC-equivalent compute site per pointwise lane, fixed SRAM/DRAM ports",
                  total_compute_sites=TOTAL_SITES, pointwise_energy_scale=energy_scale, splits=records,
                  budget_selections=best, elapsed_s=time.perf_counter()-started)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def verify(path):
    data = json.loads(path.read_bytes())
    case = common.Case(data["case"]["workload"], data["case"]["arch"], tuple(data["case"]["params"]))
    common.af.set_n_parallel_jobs(1)
    checked = 0
    for split in data["splits"]:
        lanes = split["pointwise_lanes"]
        physical = builder(lanes, data["pointwise_energy_scale"])
        if tuple(split["shape"]) != geometry(lanes):
            raise ValueError("bad saved compute split")
        with patch.object(codec, "build", physical), patch.object(validation, "build", physical):
            for point in split["maps"]:
                codec.replay(case, point["architecture"], point["witness"])
                checked += 1
    targets = [v["witness"]["edp"] for v in data["budget_selections"]]
    ratio = [p["witness"]["edp"] / e for p, e in zip(data["splits"][0]["maps"], targets, strict=True)]
    return dict(status="verified", physical_witnesses=checked, canonical_edp=targets,
                speed_quality_ratio_edp=ratio, external_sota_acceptance=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", choices=("attention", "attention256", "attention512"), default="attention")
    parser.add_argument("--pointwise-energy-scale", type=float, default=1.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if args.replay:
        result = verify(args.replay)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(result), flush=True)
    else:
        run(args.workload, args.output, args.pointwise_energy_scale)


if __name__ == "__main__":
    main()
