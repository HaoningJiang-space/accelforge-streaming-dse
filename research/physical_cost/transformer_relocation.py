"""Construct a bank-preserving lifetime allocation outside the fixed-region grammar.

This is a mapping-coverage diagnostic, not a new optimizer or a hardware
implementation: descriptor/address-generation costs are not calibrated.
"""

import argparse
from collections import defaultdict
from dataclasses import replace
import gzip
from hashlib import sha256
from heapq import heappop, heappush
import json
from pathlib import Path
import subprocess
import sys

from research.physical_cost.paid_area import PaidArchitecture
from research.physical_cost.serving_exhaustive import write_atomic
from research.physical_cost.serving_trace import run
from research.physical_cost.transformer_serving import Workload, Plan, compile_program
from research.physical_cost.transformer_validation import verify


def relocate(spans, capacity):
    events = [(end if way == "w" else begin, way == "r", i, (bank, row), value, begin, end)
              for i, (begin, end, _, way, bank, row, value, _) in enumerate(spans) if way != "core"]
    current, lives, span_version = {}, {}, {}
    for _, read, i, loc, value, begin, end in sorted(events):
        if read:
            old, born = current[loc]
            assert old == value
        else:
            born = begin
            current[loc] = value, born
        key = loc, born
        lives[key] = end
        span_version[i] = key
    per_bank = defaultdict(list)
    for key, end in lives.items():
        loc, born = key
        per_bank[loc[0]].append((born, end, key))
    colors, peaks = {}, {}
    for bank, entries in per_bank.items():
        active, free, next_row = [], [], 0
        for born, end, key in sorted(entries):
            while active and active[0][0] <= born:
                _, row = heappop(active)
                heappush(free, row)
            if free:
                row = heappop(free)
            else:
                row = next_row
                next_row += 1
            colors[key] = bank, row
            heappush(active, (end, row))
        peaks[bank] = next_row * 64
    # Independently replay the resulting physical locations and versions.
    current = {}
    occupied_until = {}
    for _, read, i, _, value, begin, end in sorted(events):
        loc = colors[span_version[i]]
        assert loc[0] == spans[i][4]  # bank, port demand and command times unchanged
        if read:
            assert current[loc] == value
        else:
            assert occupied_until.get(loc, 0) <= begin
            current[loc] = value
            occupied_until[loc] = lives[span_version[i]]
    return {"fits": max(peaks.values()) <= capacity, "bank_bytes": peaks,
            "tensor_versions": len(lives), "checked_accesses": len(events),
            "assignment_sha256": sha256(repr(sorted(colors.items())).encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sram", type=Path)
    parser.add_argument("ramulator", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("reports", nargs="+", type=Path)
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "-C", str(args.ramulator), "rev-parse", "HEAD"], text=True).strip()
    assert revision == "7bead6cb7c4b03e095c6d4769ae3181a8e0bf6da"
    sys.path.insert(0, str(args.ramulator / "python"))
    from ramulator.dram import DDR4

    device = DDR4(org_preset="DDR4_8Gb_x8", timing_preset="DDR4_2400R", rank=1)
    macros = {int(k): v for k, v in json.loads(args.sram.read_text())["macros"].items()}
    report = {"scope": "bank-preserving per-version row allocation; outside fixed-region grammar; address-generator cost uncalibrated",
              "ramulator_revision": revision, "cases": []}
    for path in args.reports:
        data = json.loads(gzip.decompress(path.read_bytes()))
        work = Workload(**data["workload"])
        oracle = data["summary"]["episode_winners"][0]
        plan = Plan(**data["reference"]["episode"][oracle]["best"]["plan"])
        for index in data["summary"]["decode_ties"]:
            hw = PaidArchitecture(**data["hardware"][index])
            if compile_program(hw, work, plan) is not None:
                continue
            expanded = replace(hw, global_depth=64)
            program = compile_program(expanded, work, plan)
            assert program is not None
            program.hardware = hw  # Preserve real macro timing, energy, area and leakage.
            result = run(program, macros, record=True)
            audit = verify(program, result, macros, device, work, allow_reservation_overflow=True)
            coloring = relocate(result["trace"][0], hw.global_capacity)
            assert max(coloring["bank_bytes"].values()) == max(audit["peak_live_bank_bytes"])
            report["cases"].append({"case": path.name, "target_index": index, "source_index": oracle,
                                    "plan": data["reference"]["episode"][oracle]["best"]["plan"],
                                    "hardware": data["hardware"][index], "audit": audit, "allocation": coloring,
                                    "edp": result["edp"], "grammar_oracle_edp": data["summary"]["oracle_edp"],
                                    "decode_first_edp": data["summary"]["decode_first_edp"]})
            write_atomic(args.output, report)
            print(path.name, "relocated", index, coloring["fits"], max(coloring["bank_bytes"].values()), flush=True)


if __name__ == "__main__":
    main()
