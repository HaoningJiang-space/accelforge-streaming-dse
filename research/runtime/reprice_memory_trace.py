"""Reprice historical Event phase winners after the independent action audit."""

import argparse
from collections import Counter
import hashlib
import json
from math import isclose
from pathlib import Path

from research.runtime.audit_memory_trace import count, paths
from research.runtime.strip_codesign import COMPUTE, DRAM, GB_READ, GB_WRITE


def services(actions, cycles):
    words = Counter()
    for key, value in actions.items():
        _, kind, memory, _, direction = key.split("<SEP>")
        if kind != "action" or value < 0 or value != int(value):
            raise ValueError("invalid action count")
        if memory == "MAC":
            words[memory, direction] += int(value)
        else:
            if value % 8:
                raise ValueError("memory action has an incomplete word")
            words[memory, direction] += int(value) // 8
    dram = words["MainMemory", "read"] + words["MainMemory", "write"]
    reads, writes = words["GlobalBuffer", "read"], words["GlobalBuffer", "write"]
    energy = dram * DRAM[0] + reads * GB_READ[0] + writes * GB_WRITE[0]
    energy += words["MAC", "compute"] * COMPUTE[0]
    delay = max(dram * DRAM[1], reads * GB_READ[1], writes * GB_WRITE[1], cycles * COMPUTE[1])
    return energy, delay


def reprice(tail, phases):
    case = tail["case"]
    if (case["workload"], case["arch"]) != ("matmuls", "nvdla"):
        raise ValueError("dense NVDLA GEMM chain required")
    stages, rows, width = case["params"]
    out = []
    for selection in phases["selections"]:
        winner = selection["winner"]
        entry = next(x for x in tail["entries"] if x["architecture"] == winner["architecture"])
        candidate = entry["candidates"][winner["candidate_index"]]
        witness = candidate["witness"]
        if candidate["status"] != "verified" or candidate["changes"] != winner["changes"]:
            raise ValueError("archived phases do not identify an accepted candidate")
        independent = count(witness["mapping"], rows, width, stages)
        native = witness["actions"]
        corrections = {
            key: independent[key] - int(native.get(key, 0))
            for key in sorted(independent.keys() | native.keys())
            if independent[key] != native.get(key, 0)
        }
        loop_paths = {op: [n for n in nodes if n["type"] in {"Temporal", "Spatial"}]
                      for op, nodes in paths(witness["mapping"]["nodes"])}
        changed_loops = {op: loop_paths[op][idx] for op, idx, _ in candidate["changes"]}
        ticks = 0
        for op, trace in candidate["independent_trace"].items():
            phase = winner["operators"][op]
            wanted = {key: value for key, value in independent.items() if key.startswith(op + "<SEP>")}
            if phase["phase_count"] == 1:
                _, delay = services(wanted, trace["compute_cycles"])
                if not isclose(delay * 1e-9 / 1536, phase["phase_latency_s"], rel_tol=1e-12):
                    raise AssertionError("archived unpartitioned phase does not agree with trace")
                ticks += delay
                continue
            collected = Counter()
            for part in phase["phases"]:
                ledger = Counter(part["bit_actions"])
                if part["kind"] == "remainder":
                    index = int(op.removeprefix("Matmul"))
                    for key, delta in corrections.items():
                        if not key.startswith(op + "<SEP>"):
                            continue
                        if (key != f"{op}<SEP>action<SEP>GlobalBuffer<SEP>T{index+1}<SEP>read"
                                or changed_loops[op]["rank_variable"] != f"n{index}"
                                or delta != rows * width * 8):
                            raise ValueError("unclassified phase difference")
                        # The remainder follows a nonempty full reduction tile
                        # and updates the same output coordinate set.
                        ledger[key] += delta
                collected.update(ledger)
                _, delay = services(ledger, part["mac_cycles"])
                ticks += delay
            if +collected != Counter(wanted):
                raise ValueError("corrected phase actions do not conserve the independent whole")
        energy, _ = services(independent, 0)
        edp = energy * ticks * (4e-15 * 1e-9 / 1536)
        out.append(dict(budget=selection["budget"], architecture=winner["architecture"],
                        mapping_id=witness["mapping_id"], added_read_bits=corrections,
                        energy_j=energy * 4e-15, archived_phase_edp=winner["phase_edp"],
                        phase_latency_s=ticks * 1e-9 / 1536, corrected_phase_edp=edp))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tail", type=Path)
    parser.add_argument("phases", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = [source.read_bytes() for source in (args.tail, args.phases)]
    result = dict(
        scope="same archived winners and phase-throughput model, corrected memory counts",
        input_sha256=[hashlib.sha256(raw).hexdigest() for raw in inputs],
        selections=reprice(*(json.loads(raw) for raw in inputs)),
    )
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result["selections"]))


if __name__ == "__main__":
    main()
