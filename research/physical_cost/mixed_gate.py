"""Measure the penalty of one shared SRAM architecture for unlike native mappings."""

import argparse
from contextlib import nullcontext
from dataclasses import asdict, dataclass
from importlib import import_module
from itertools import product
import json
import logging
from math import ceil, isclose
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

import numpy as np

from accelforge.frontend.mapping import TensorHolder
from research.joint_search import ffm_backend
from research.late_binding.kill_frontier import native_jobs
from research.late_binding.late_binding_grid import energy_latency_front, serial_edp
from research.physical_cost.cacti_sram import CACTI_REVISION, CAPACITIES, TECH_NM, word_bytes
from research.tracking_audit import common


SHAPES = ((16, 128), (32, 64), (64, 32))
GB_BANKS = (2, 4)
GB_BYTES = (16384, 65536)
LOCAL_BYTES = (1024, 4096)
DECODE_STEPS = (16, 64, 256)
BUDGET_FACTORS = (1, 1.5, 2)
REFERENCE = (32, 64, 4, 16384, 1024)
DRAM_BIT_J = 7.03e-12
DRAM_BIT_SECONDS = 1 / (8 * 38.4e9)


@dataclass(frozen=True, order=True)
class Architecture:
    x: int
    y: int
    global_banks: int
    global_bank_bytes: int
    weight_bytes_per_stripe: int

    @property
    def global_capacity(self):
        return self.global_bank_bytes

    @property
    def private_capacity(self):
        return self.weight_bytes_per_stripe

    def sram_totals(self, macros, metric):
        return (self.global_banks * macros[self.global_bank_bytes][metric]
                + self.x * macros[self.weight_bytes_per_stripe][metric])


def spec_for(architecture, macros, context, resident=False, single_bank=False):
    root = Path(__file__).parent
    spec = common.af.Spec.from_yaml(
        root / "two_level_nvdla.yaml", root / "mixed_phases.yaml",
        jinja_parse_data={"CONTEXT": context},
    )
    spec.arch.find("InputFanout").spatial[0].fanout = architecture.x
    spec.arch.find("OutputFanout").spatial[0].fanout = architecture.y
    for component, size, banks in (
        ("GlobalBuffer", architecture.global_bank_bytes, architecture.global_banks),
        ("WeightBuffer", architecture.weight_bytes_per_stripe, 1),
    ):
        macro, memory = macros[size], spec.arch.find(component)
        memory.size = size * banks * 8
        transaction_ns = ceil(max(macro["access_ns"], macro["cycle_ns"]))
        for name in ("read", "write"):
            action = memory.actions[name]
            action.energy = macro[f"{name}_nj"] * 1e-9 / (macro["word_bytes"] * 8)
            parallel_banks = 1 if single_bank else banks
            action.latency = transaction_ns * 1e-9 / (macro["word_bytes"] * 8 * parallel_banks)
    if resident:
        spec.arch.find("MainMemory").tensors.keep = "~KCache"
        spec.arch.find("MainMemory").tensors.may_keep = "Nothing"
        spec.arch.find("GlobalBuffer").tensors.back = "KCache"
    return spec._spec_eval_expressions(eval_arch=False, eval_non_arch=True)


def frontier(energy, times):
    indices = energy_latency_front(energy, times)
    return energy[indices], times[indices]


def evaluate_phase(groups, prices, leakage_mw, resident_bits=0):
    original_model = ffm_backend.tiles.run_model
    native_model = import_module(original_model.__module__)
    original_reuse = native_model.analyze_reuse_and_add_reservations_to_mapping

    def reserve_full_kv(job):
        reuse = original_reuse(job)
        entries = [stats for buffer, stats in reuse.buffet_stats.items()
                   if buffer.level == "GlobalBuffer" and buffer.tensor == "KCache"]
        if len(entries) != 1:
            raise AssertionError("Expected one GlobalBuffer allocation for the resident KV")
        # Native tile occupancy counts the currently addressed subregion.
        # The whole KV remains allocated across every decode loop and step.
        entries[0].max_occupancy = resident_bits
        entries[0].persistent = True
        return reuse

    frames = []
    for group in groups.values():
        for job in group:
            if resident_bits:
                if not any(isinstance(node, TensorHolder) and node.component == "GlobalBuffer"
                           and "KCache" in node._backing for node in job.mapping.nodes):
                    raise AssertionError("Native template failed to place the resident KV backing")
                job.ignored_resources = set(job.ignored_resources) - {"GlobalBuffer"}
                job.memories_track_all = set(job.memories_track_all) | {"GlobalBuffer"}
                job.memories_track_pmappings_only = set(job.memories_track_pmappings_only) - {"GlobalBuffer"}

            def capture(cur_job):
                symbols, columns, usage, spatial, mappings = original_model(cur_job)
                proxy_energy = 0
                for key, count in columns.items():
                    if key.startswith("action<SEP>"):
                        _, component, _, action = key.split("<SEP>")
                        price = prices.get((component, action))
                        if price is None:
                            price = cur_job.spec.arch.find(component).actions[action].energy
                        proxy_energy += price * count
                columns["Total<SEP>proxy_energy"] = proxy_energy
                if resident_bits:
                    columns["reservation<SEP>GlobalBuffer<SEP>gate_kv"] = usage[
                        "usage<SEP>memory<SEP>GlobalBuffer"
                    ]
                return symbols, columns, usage, spatial, mappings

            reservation_patch = (
                patch.object(native_model, "analyze_reuse_and_add_reservations_to_mapping", reserve_full_kv)
                if resident_bits else nullcontext()
            )
            with reservation_patch, patch.object(ffm_backend.tiles, "run_model", capture):
                frame, _ = ffm_backend.tiles._make_tile_shapes(job)
            if frame.empty:
                continue
            if resident_bits:
                occupancy = frame["reservation<SEP>GlobalBuffer<SEP>gate_kv"]
                cap = frame["resource_capacity_bits<SEP>GlobalBuffer"]
                if (np.any(occupancy < resident_bits) or np.any(occupancy > cap)
                        or np.any(frame.get("action<SEP>MainMemory<SEP>KCache<SEP>read", 0))):
                    raise AssertionError("A resident KV mapping fails its capacity or backing audit")
            frames.append(frame[["Total<SEP>energy", "Total<SEP>proxy_energy", "Total<SEP>latency"]].to_numpy())
    if not frames:
        return None
    actual, flat, seconds = np.concatenate(frames).T
    if not (np.isfinite(actual).all() and np.isfinite(flat).all() and np.isfinite(seconds).all()):
        raise ValueError("Nonfinite native result")
    ns = seconds * 1e9
    return (frontier(actual * 1e12 + leakage_mw * ns, ns),
            frontier(flat * 1e12, ns), len(actual))


def evaluate(architecture, macros, context, resident_kv, single_bank):
    metrics = common.EL | common.af.Metrics.ACTIONS
    spec = spec_for(architecture, macros, context, single_bank=single_bank)
    jobs = native_jobs(spec, metrics)
    prices = {
        (component, action): macros[size][f"{action}_nj"] * 1e-9 / (macros[size]["word_bytes"] * 8)
        for component, size in (("GlobalBuffer", GB_BYTES[0]), ("WeightBuffer", LOCAL_BYTES[0]))
        for action in ("read", "write")
    }
    leakage_mw = architecture.sram_totals(macros, "leak_mw")
    phases = [evaluate_phase(jobs[phase], prices, leakage_mw) for phase in ("Prefill", "Decode")]
    if any(phase is None for phase in phases):
        raise ValueError(f"No cold native mapping on {architecture}")
    resident = None
    kv_bits = context * 64 * 8
    if resident_kv and kv_bits < architecture.global_banks * architecture.global_bank_bytes * 8:
        spec = spec_for(architecture, macros, context, resident=True, single_bank=single_bank)
        pmapper = ffm_backend.pmapper
        jobs = pmapper.get_jobs(spec, metrics, ["Decode"], True)
        pmapper._fill_jobs_with_memories_to_track(jobs, spec, metrics, False)
        native = evaluate_phase(jobs["Decode"], prices, leakage_mw, kv_bits)
        if native is not None:
            action = spec.arch.find("GlobalBuffer").actions["write"]
            # DMA books both ports. The budget includes the initial full KV transfer.
            fill_ns = kv_bits * max(DRAM_BIT_SECONDS, action.latency) * 1e9
            fill_pj = kv_bits * (DRAM_BIT_J + action.energy) * 1e12 + leakage_mw * fill_ns
            flat_fill_pj = kv_bits * (DRAM_BIT_J + prices["GlobalBuffer", "write"]) * 1e12
            resident = (native, (fill_pj, flat_fill_pj, fill_ns))
    return phases, resident


def episode(costs, steps, price_model):
    (prefill, decode), resident = costs
    energy, time = decode[price_model]
    energy, time = energy * steps, time * steps
    if resident is not None:
        native, fill = resident
        e, t = native[price_model]
        energy = np.concatenate((energy, e * steps + fill[price_model]))
        time = np.concatenate((time, t * steps + fill[2]))
    return prefill[price_model], frontier(energy, time)


def assess(architectures, macros, budget, steps):
    admitted = {
        hardware: (episode(costs, steps, 0), episode(costs, steps, 1))
        for hardware, costs in architectures.items()
        if hardware.sram_totals(macros, "area_mm2") <= budget
    }
    shared = {hardware: serial_edp(physical) for hardware, (physical, _) in admitted.items()}
    best = min(shared, key=shared.get)

    independent = []
    phase_winners = {}
    for phase, phase_name in enumerate(("Prefill", "Decode")):
        fronts = [physical[phase] for physical, _ in admitted.values()]
        energies, times = zip(*fronts, strict=True)
        independent.append(frontier(np.concatenate(energies), np.concatenate(times)))
        phase_edp = {hardware: float(np.min(np.prod(physical[phase], axis=0)))
                     for hardware, (physical, _) in admitted.items()}
        phase_winners[phase_name] = [asdict(hw) for hw, edp in phase_edp.items()
                                    if isclose(edp, min(phase_edp.values()), rel_tol=1e-9)]
    lower = serial_edp(independent)
    if lower > shared[best] * (1 + 1e-9):
        raise AssertionError("Independent-hardware relaxation exceeds the shared solution")

    proxy_scores = {hw: serial_edp(proxy) for hw, (_, proxy) in admitted.items()}
    prefill_scores = {hw: float(np.min(np.prod(physical[0], axis=0)))
                      for hw, (physical, _) in admitted.items()}
    controls = {}
    for name, scores in (("flat_energy", proxy_scores), ("prefill_only", prefill_scores)):
        optimum = min(scores.values())
        tied = [hw for hw, score in scores.items() if isclose(score, optimum, rel_tol=1e-9)]
        remapped = min(shared[hw] for hw in tied)
        controls[name] = {
            "tied_hardware": [asdict(hw) for hw in tied],
            "remapped_edp_pj_ns": remapped,
            "regret": remapped / shared[best] - 1,
        }
    best_phases, _ = admitted[best]
    energy = np.add.outer(best_phases[0][0], best_phases[1][0])
    delay = np.add.outer(best_phases[0][1], best_phases[1][1])
    chosen = np.unravel_index((energy * delay).argmin(), energy.shape)
    leakage_pj = best.sram_totals(macros, "leak_mw") * delay[chosen]
    cold_at_winner = serial_edp(episode((architectures[best][0], None), steps, 0))
    return {
        "sram_area_limit_mm2": budget,
        "decode_steps": steps,
        "hardware_points": len(admitted),
        "shared_edp_pj_ns": shared[best],
        "shared_winner": asdict(best),
        "winner_energy_pj": float(energy[chosen]),
        "winner_latency_ns": float(delay[chosen]),
        "winner_sram_area_mm2": best.sram_totals(macros, "area_mm2"),
        "winner_sram_leakage_fraction": float(leakage_pj / energy[chosen]),
        "winner_uses_resident_kv": shared[best] < cold_at_winner * (1 - 1e-9),
        "resident_eligible_points": sum(architectures[hw][1] is not None for hw in admitted),
        "cold_only_shared_edp_pj_ns": min(
            serial_edp(episode((architectures[hw][0], None), steps, 0)) for hw in admitted
        ),
        "independent_hardware_edp_pj_ns": lower,
        "independent_phase_edp_winners": phase_winners,
        "shared_hardware_penalty": shared[best] / lower - 1,
        "architecture_first": controls,
    }


def run(table, output, *, smoke=False, context=512, resident_kv=False, single_bank=False):
    if (table["cacti_revision"] != CACTI_REVISION or table["technology_nm"] != TECH_NM
            or table["read_ports"] != 1 or table["write_ports"] != 1):
        raise ValueError("Unexpected CACTI macro characterization")
    macros = {size: table["macros"][str(size)] for size in CAPACITIES}
    if any(macros[size]["word_bytes"] != word_bytes(size) for size in CAPACITIES):
        raise ValueError("Unexpected SRAM transaction widths")
    common.clear_switches()
    common.set_jobs(1)
    logging.disable(logging.CRITICAL)
    architectures = {}
    start = perf_counter()
    reference = Architecture(*REFERENCE).sram_totals(macros, "area_mm2")
    candidates = [Architecture(*shape, banks, gb, local)
                  for shape, banks, gb, local in product(SHAPES, GB_BANKS, GB_BYTES, LOCAL_BYTES)]
    candidates = [hw for hw in candidates if hw.sram_totals(macros, "area_mm2") <= max(BUDGET_FACTORS) * reference]
    if smoke:
        candidates = [Architecture(*REFERENCE)]
    for hardware in candidates:
        t0 = perf_counter()
        phases, resident = architectures[hardware] = evaluate(
            hardware, macros, context, resident_kv, single_bank,
        )
        print("NATIVE_POINT " + json.dumps({
            "hardware": asdict(hardware),
            "sram_area_mm2": hardware.sram_totals(macros, "area_mm2"),
            "sram_leak_mw": hardware.sram_totals(macros, "leak_mw"),
            "native_rows": [phase[2] for phase in phases],
            "resident_decode_rows": resident[0][2] if resident else 0,
            "seconds": round(perf_counter() - t0, 3),
        }), flush=True)
    cases = [assess(architectures, macros, reference * factor, steps)
             for factor, steps in product(BUDGET_FACTORS, DECODE_STEPS)]
    report = {
        "cacti_revision": CACTI_REVISION,
        "scope": "one prefill GEMM and repeated fixed-context decode GEMV",
        "decode_context": context,
        "resident_kv": resident_kv,
        "global_bank_service": "one bank" if single_bank else "all banks",
        "sram_area_reference_mm2": reference,
        "hardware_evaluated": len(architectures),
        "smoke": smoke,
        "seconds": round(perf_counter() - start, 3),
        "cases": cases,
    }
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("MIXED_GATE " + json.dumps(report, separators=(",", ":"), allow_nan=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--context", type=int, default=512)
    parser.add_argument("--resident-kv", action="store_true")
    parser.add_argument("--single-bank-service", action="store_true")
    args = parser.parse_args()
    if args.context <= 0:
        parser.error("--context must be positive")
    run(json.loads(args.table.read_text(encoding="utf-8")), args.output,
        smoke=args.smoke, context=args.context, resident_kv=args.resident_kv,
        single_bank=args.single_bank_service)


if __name__ == "__main__":
    main()
