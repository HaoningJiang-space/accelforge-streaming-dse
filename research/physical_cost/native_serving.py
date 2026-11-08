"""Compare paid, fixed-DDR architectures on native prefill and long decode."""

import argparse
from dataclasses import asdict
import gzip
from itertools import product
import json
import logging
from math import isclose
from pathlib import Path
from time import perf_counter

import accelforge as af
from accelforge.mapper.FFM.main import join_pmappings, make_pmappings
from accelforge.model.main import evaluate_mapping

from research.physical_cost.banked_scale import DeepArchitecture
from research.physical_cost.mixed_gate import price_sram
from research.physical_cost.native_block import ARCH, ENERGY, LATENCY, MAPPING, MAC_J, METRICS
from research.physical_cost.paid_area import Ledger
from research.tracking_audit.common import clear_switches


TOKENS = 256
WIDTH = 256
HEAD_BYTES = 64
STEPS = (1, 8, 32, 128)


def architectures(macros, ledger, cap):
    result = []
    for y in (32, 64, 128):
        same_shape = (ledger.price(DeepArchitecture(32, y, banks, 65536, 1024))
                      for banks in range(2, 25))
        choices = [hw for hw in same_shape if hw.total_area_mm2(macros) <= cap]
        if choices:
            result.append(choices[-1])
    return result


def phase_spec(hw, macros, context, phase):
    workload = Path(__file__).with_name("mixed_phases.yaml" if phase == "prefill" else "long_decode.yaml")
    spec = af.Spec.from_yaml(ARCH, workload, jinja_parse_data={"CONTEXT": context})
    if phase == "prefill":
        spec.workload.einsums[:] = [spec.workload.einsums["Prefill"]]
        spec.workload.rank_sizes.update({"M": TOKENS, "K": WIDTH, "N": WIDTH})
    price_sram(spec, hw, macros)
    memory = spec.arch.find("MainMemory")
    for direction, energy in (("read", hw.ddr_read_aj), ("write", hw.ddr_write_aj)):
        memory.actions[direction].energy = energy * 1e-18 / 512
        memory.actions[direction].latency = hw.ddr_word_ns * 1e-9 / 512
    if phase == "resident":
        # Reserve both full caches. The native mapper also charges the
        # active K/V tiles against staging, a conservative extra reservation.
        staging = hw.global_banks * hw.global_capacity - 2 * context * HEAD_BYTES
        if staging <= 0:
            return None
        memory.tensors.keep = "All - (K | V)"
        memory.tensors.may_keep = "Nothing"
        buffer = spec.arch.find("GlobalBuffer")
        buffer.tensors.back = "All & (K | V)"
        buffer.size = staging * 8
    spec.mapper.ffm.metrics = METRICS
    spec.model.metrics = METRICS | af.Metrics.ACTIONS
    spec.mapper.ffm.max_fused_loops = 1
    return spec


def external_traffic(context, phase):
    if phase == "prefill":
        return (("Prefill", "X", "read", TOKENS * WIDTH * 8),
                ("Prefill", "W", "read", WIDTH**2 * 8),
                ("Prefill", "P", "write", TOKENS * WIDTH * 8))
    activation = (("QK", "Q", "read", HEAD_BYTES * 8), ("AV", "Value", "write", HEAD_BYTES * 8))
    kv_bits = context * HEAD_BYTES * 8 if phase == "cold" else 0
    return (*activation, ("QK", "K", "read", kv_bits), ("AV", "V", "read", kv_bits))


def phase_bound(hw, macros, context, phase):
    macs = TOKENS * WIDTH**2 if phase == "prefill" else 2 * context * HEAD_BYTES
    reads = sum(bits for _, _, action, bits in external_traffic(context, phase) if action == "read")
    writes = sum(bits for _, _, action, bits in external_traffic(context, phase) if action == "write")
    mac_ns = macs / (hw.x * hw.y)
    ddr_ns = max(reads, writes) * hw.ddr_word_ns / 512
    seconds = max(mac_ns, ddr_ns) * 1e-9
    energy = (macs * MAC_J + (reads * hw.ddr_read_aj + writes * hw.ddr_write_aj) * 1e-18 / 512
              + hw.standby_mw(macros) * 1e-3 * seconds)
    return energy, seconds


def remap(hw, macros, context, phase):
    spec = phase_spec(hw, macros, context, phase)
    if spec is None:
        return None
    start = perf_counter()
    candidates = join_pmappings(make_pmappings(spec, print_number_of_pmappings=False)).data
    if candidates.empty:
        raise RuntimeError(f"No complete native mapping for {phase} on {hw}")
    lower_e, lower_t = phase_bound(hw, macros, context, phase)
    plans = []
    for _, row in candidates.iterrows():
        spec.mapping = row[MAPPING]()
        replay = evaluate_mapping(spec).data.iloc[0]
        for field in (ENERGY, LATENCY):
            if not isclose(row[field], replay[field], rel_tol=1e-6):
                raise AssertionError(f"Native {phase} replay changed {field}")
        ledger = {}
        for op, tensor, action, minimum in external_traffic(context, phase):
            field = f"{op}<SEP>action<SEP>MainMemory<SEP>{tensor}<SEP>{action}"
            actual = int(replay.get(field, 0))
            if actual < minimum or (phase == "resident" and tensor in {"K", "V"} and actual):
                raise AssertionError(f"Unexpected native traffic for {phase} {tensor}: {actual}, min {minimum}")
            ledger[tensor] = actual
        seconds = float(row[LATENCY])
        energy = float(row[ENERGY]) + hw.standby_mw(macros) * 1e-3 * seconds
        if energy < lower_e * (1 - 1e-6) or seconds < lower_t * (1 - 1e-6):
            raise AssertionError(f"The native boundary bound exceeds {phase} replay")
        plans.append({"joules": energy, "seconds": seconds, "ddr_bits": ledger})
    return {"plans": plans, "lower_joules": lower_e, "lower_seconds": lower_t,
            "wall_seconds": perf_counter() - start}


def resident_fill(hw, macros, context):
    bytes_ = 2 * context * HEAD_BYTES
    macro = macros[hw.global_bank_bytes]
    words = bytes_ // 64
    # Sequential port reservation. All benchmark context sizes are line aligned.
    ns = words * hw.ddr_word_ns
    joules = (words * hw.ddr_read_aj * 1e-18 + words * macro["write_nj"] * 1e-9
              + hw.standby_mw(macros) * 1e-3 * ns * 1e-9)
    return joules, ns * 1e-9


def options(row, macros, context, steps):
    for phase in ("cold", "resident"):
        result = row["phases"].get(phase)
        if result is None:
            continue
        fill_e, fill_t = resident_fill(row["hardware"], macros, context) if phase == "resident" else (0, 0)
        for plan in result["plans"]:
            yield plan["joules"] * steps + fill_e, plan["seconds"] * steps + fill_t, phase


def episode_bounds(row, macros, context, steps):
    hw, phases = row["hardware"], row["phases"]
    p = phases["prefill"]
    p_energy, p_seconds = p["lower_joules"], p["lower_seconds"]
    mode_lowers = []
    for mode in ("cold", "resident"):
        d = phases.get(mode)
        if d is None:
            continue
        fill_e, fill_t = resident_fill(hw, macros, context) if mode == "resident" else (0, 0)
        mode_lowers.append((p_energy + fill_e + d["lower_joules"] * steps)
                           * (p_seconds + fill_t + d["lower_seconds"] * steps))

    # Give the cache every byte of modeled on-chip storage at each
    # autoregressive step boundary, including private SRAM and PE registers.
    # The first scan starts off chip. Later scans may retain any subset.
    kv_bytes = 2 * context * HEAD_BYTES
    capacity = hw.global_banks * hw.global_capacity + hw.x * hw.private_capacity + hw.x * hw.y
    refetch_bytes = max(0, kv_bytes - capacity)
    kv_read_bytes = kv_bytes + (steps - 1) * refetch_bytes
    read_bits = (kv_read_bytes + steps * HEAD_BYTES) * 8
    write_bits = steps * HEAD_BYTES * 8
    decode_macs = 2 * context * HEAD_BYTES * steps
    decode_seconds = max(decode_macs / (hw.x * hw.y),
                         max(read_bits, write_bits) * hw.ddr_word_ns / 512) * 1e-9
    decode_energy = (decode_macs * MAC_J
                     + (read_bits * hw.ddr_read_aj + write_bits * hw.ddr_write_aj) * 1e-18 / 512
                     + hw.standby_mw(macros) * 1e-3 * decode_seconds)
    relaxed = (p_energy + decode_energy) * (p_seconds + decode_seconds)
    return {"partial_cache_lower": relaxed, "declared_mode_lower": max(relaxed, min(mode_lowers)),
            "refetch_bytes_per_later_step": refetch_bytes}


def certified_prefix(bounds, exact):
    upper = float("inf")
    opened = []
    for i in sorted(range(len(bounds)), key=lambda i: (bounds[i], i)):
        if bounds[i] >= upper * (1 + 1e-6):
            break
        upper = min(upper, exact[i])
        opened.append(i)
    if not isclose(upper, min(exact), rel_tol=1e-6):
        raise AssertionError("Native episode bound disagrees with the full remap sweep")
    return opened


def compare(rows, macros, context, steps):
    results = []
    for i, p in enumerate(rows):
        for j, d in enumerate(rows):
            for prefill, (decode_e, decode_t, mode) in product(p["phases"]["prefill"]["plans"],
                                                              options(d, macros, context, steps)):
                edp = (prefill["joules"] + decode_e) * (prefill["seconds"] + decode_t)
                results.append((edp, i, j, mode))
    shared = min(r for r in results if r[1] == r[2])
    independent = min(results)
    pbest = min((p["joules"] * p["seconds"], i) for i, row in enumerate(rows)
                for p in row["phases"]["prefill"]["plans"])
    dbest = min((e * t, i, mode) for i, row in enumerate(rows)
                for e, t, mode in options(row, macros, context, steps))
    exact = [min(r[0] for r in results if r[1] == r[2] == i) for i in range(len(rows))]
    bounds = [episode_bounds(row, macros, context, steps) for row in rows]
    for bound, score in zip(bounds, exact, strict=True):
        if bound["declared_mode_lower"] > score * (1 + 1e-6):
            raise AssertionError("Native episode lower bound exceeds a verified mapping")
    prefill_ties = {i for i, row in enumerate(rows)
                    if min(p["joules"] * p["seconds"] for p in row["phases"]["prefill"]["plans"]) == pbest[0]}
    return {"steps": steps, "shared": shared, "independent": independent,
            "prefill_only": pbest, "decode_only": dbest,
            "shared_penalty": shared[0] / independent[0] - 1,
            "prefill_first_regret": min(exact[i] for i in prefill_ties) / shared[0] - 1,
            "per_architecture_edp": exact, "per_architecture_bounds": bounds,
            "opened_with_partial_cache_bound": certified_prefix(
                [b["partial_cache_lower"] for b in bounds], exact),
            "opened_with_declared_mode_bound": certified_prefix(
                [b["declared_mode_lower"] for b in bounds], exact)}


def run(macros, ledger, context, output):
    cap = ledger.reference_overhead() + 4.5
    hardware = architectures(macros, ledger, cap)
    rows = []
    report = {"tokens": TOKENS, "width": WIDTH, "context": context, "total_area_cap_mm2": cap}
    for hw in hardware:
        phases = {}
        for phase in ("prefill", "cold", "resident"):
            phases[phase] = remap(hw, macros, context, phase)
            print(hw.x, hw.y, hw.global_banks, phase,
                  None if phases[phase] is None else len(phases[phase]["plans"]), flush=True)
        rows.append({"hardware": hw, "total_area_mm2": hw.total_area_mm2(macros), "phases": phases})
        report["architectures"] = [{**row, "hardware": asdict(row["hardware"])} for row in rows]
        report["steps"] = [compare(rows, macros, context, count) for count in STEPS]
        output.write_bytes(gzip.compress(json.dumps(report, indent=2).encode(), mtime=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sram", type=Path)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--context", type=int, default=5120)
    args = parser.parse_args()
    if args.context < 1:
        parser.error("Context must be positive")
    clear_switches()
    af.set_n_parallel_jobs(1)
    logging.basicConfig(level=logging.ERROR, force=True)
    macros = {int(k): v for k, v in json.loads(args.sram.read_text())["macros"].items()}
    run(macros, Ledger(json.loads(args.ledger.read_text())), args.context, args.output)


if __name__ == "__main__":
    main()
