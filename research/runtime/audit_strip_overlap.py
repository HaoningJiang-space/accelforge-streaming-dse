"""Compare native timing, independent component arithmetic and a port calendar."""

import argparse
import hashlib
import json
from math import isclose
from pathlib import Path

from research.joint_budget.protocol import Hardware
from research.joint_physical.replay import decode, encode
from research.runtime.replay_strip_native import native_actions, translate
from research.runtime.strip_codesign import Segment
from research.runtime.strip_native_timing import by_stage
from research.runtime.strip_overlap import audit
from research.runtime.strip_trace import replay
from research.runtime.tail_tiles import exact_tail_evaluation
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import RAW_GB, build


TICK = 1e-9 / 1536


def inspect(rows, width, hardware, plan):
    case = common.Case("matmuls", "nvdla", (plan[-1].stop, rows, width))
    widths = (width,) * (plan[-1].stop + 1)
    spec = build(case, (hardware.px, hardware.py), hardware.capacity_bytes,
                 common.RU | common.af.Metrics.ACTIONS)
    record = encode(translate(plan, spec.arch.find("ArrayFanout")))
    components = {}

    def component(operator, name):
        if operator not in components:
            components[operator] = spec.calculate_component_area_energy_latency_leak(
                einsum_name=operator, area=False
            )
        return components[operator].arch.find(name)

    spec.mapping = decode(record, component)
    with exact_tail_evaluation():
        data = common.evaluate_mapping(spec).data.iloc[0]
    costs, peak, words = replay(rows, widths, hardware, plan)
    actions = native_actions(words)
    native = {k: float(v) for k, v in data.items() if "<SEP>action<SEP>" in k}
    differences = {key: [actions[key], int(native.get(key, 0))]
                   for key in sorted(actions.keys() | native.keys())
                   if actions[key] != native.get(key, 0)}
    if int(data[RAW_GB]) != peak * 8:
        raise AssertionError("independent and native lifetimes disagree")

    predicted = by_stage(rows, widths, plan)
    measured = {op: {comp: float(data.get(f"{op}<SEP>latency<SEP>{comp}", 0)) / TICK
                     for comp in components}
                for op, components in predicted.items()}
    latency = float(data[common.LATENCY]) / TICK
    reproduced = sum(max(components.values()) for components in predicted.values())
    if not isclose(latency, sum(max(components.values()) for components in measured.values()),
                   rel_tol=1e-12):
        raise AssertionError("native total does not sum stage maxima")
    timing_differences = {f"{op}/{comp}": [value, measured[op][comp]]
                          for op, components in predicted.items()
                          for comp, value in components.items()
                          if not isclose(value, measured[op][comp], abs_tol=1e-6, rel_tol=1e-12)}
    calendar = audit(rows, widths, hardware, plan)
    floor = max(calendar["service_ticks"].values())
    return dict(mapping_actions_agree=not differences, action_differences=differences,
                native_ticks=latency, independently_reproduced_ticks=reproduced,
                native_component_ticks=measured, reconstructed_component_ticks=predicted,
                timing_differences=timing_differences, native_peak_bytes=peak,
                independent_energy_units=costs[0], physical_work_floor_ticks=floor,
                native_below_work_floor=latency < floor - 1e-6, calendar=calendar)


def run(raw):
    source = json.loads(raw)
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    rows = []
    for name in ("3mm256", "3mm512"):
        workload = source["cases"][name]
        for entry in workload["outcomes"]:
            winner = entry["winners"]["dp"]
            hardware = Hardware(**winner["architecture"])
            plan = [Segment(**group) for group in winner["mapping"]]
            result = inspect(workload["rows"], workload["widths"][0], hardware, plan)
            rows.append(dict(case=name, budget_bytes=entry["budget_bytes"], **result))
    # A 17-wide stage has independently checkable 16+1 reduction and
    # output tiles. The reduction remainder must read the running sum.
    hardware = Hardware(48, 128, 131072)
    for name, m, k, b, p, q in (
        ("partial_sum_5x17x17", 5, 17, 4, 16, 16),
        ("perfect_1x64x64", 1, 64, 1, 32, 32),
        ("tail_1x64x64", 1, 64, 1, 48, 48),
    ):
        probe = inspect(m, k, hardware, [Segment(0, 1, b, (False,), ((p, q),))])
        rows.append(dict(case=name, **probe))
    for entry in rows:
        print(json.dumps({k: entry[k] for k in ("case", "mapping_actions_agree",
                         "native_ticks", "independently_reproduced_ticks", "timing_differences",
                         "physical_work_floor_ticks", "native_below_work_floor")}), flush=True)
    return dict(source_sha256=hashlib.sha256(raw).hexdigest(), cases=rows)


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
