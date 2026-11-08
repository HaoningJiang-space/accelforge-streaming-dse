"""Measure the penalty of one shared SRAM architecture for unlike native mappings."""

import argparse
from dataclasses import asdict, dataclass
from itertools import product
import json
import logging
from math import ceil, isclose
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

import numpy as np

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


@dataclass(frozen=True, order=True)
class Architecture:
    x: int
    y: int
    global_banks: int
    global_bank_bytes: int
    weight_bytes_per_stripe: int

    def sram_totals(self, macros, metric):
        return (self.global_banks * macros[self.global_bank_bytes][metric]
                + self.x * macros[self.weight_bytes_per_stripe][metric])


def spec_for(architecture, macros):
    root = Path(__file__).parent
    spec = common.af.Spec.from_yaml(root / "two_level_nvdla.yaml", root / "mixed_phases.yaml")
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
            action.latency = transaction_ns * 1e-9 / (macro["word_bytes"] * 8 * banks)
    return spec._spec_eval_expressions(eval_arch=False, eval_non_arch=True)


def frontier(energy, times):
    indices = energy_latency_front(energy, times)
    return energy[indices], times[indices]


def evaluate(architecture, macros):
    metrics = common.EL | common.af.Metrics.ACTIONS
    spec = spec_for(architecture, macros)
    jobs = native_jobs(spec, metrics)
    original_model = ffm_backend.tiles.run_model
    prices = {
        (component, action): macros[size][f"{action}_nj"] * 1e-9 / (macros[size]["word_bytes"] * 8)
        for component, size in (("GlobalBuffer", GB_BYTES[0]), ("WeightBuffer", LOCAL_BYTES[0]))
        for action in ("read", "write")
    }
    leakage_mw = architecture.sram_totals(macros, "leak_mw")
    physical, proxy, sizes = [], [], []
    for phase in ("Prefill", "Decode"):
        frames = []
        for group in jobs[phase].values():
            for job in group:
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
                    return symbols, columns, usage, spatial, mappings

                with patch.object(ffm_backend.tiles, "run_model", capture):
                    frame, _ = ffm_backend.tiles._make_tile_shapes(job)
                if not frame.empty:
                    frames.append(frame[["Total<SEP>energy", "Total<SEP>proxy_energy", "Total<SEP>latency"]].to_numpy())
        if not frames:
            raise ValueError(f"No native mapping for {phase} on {architecture}")
        actual, flat, seconds = np.concatenate(frames).T
        if not (np.isfinite(actual).all() and np.isfinite(flat).all() and np.isfinite(seconds).all()):
            raise ValueError("Nonfinite native result")
        ns = seconds * 1e9
        physical.append(frontier(actual * 1e12 + leakage_mw * ns, ns))
        proxy.append(frontier(flat * 1e12, ns))
        sizes.append(len(actual))
    return physical, proxy, sizes


def mix_edp(phases, steps):
    prefill, (decode_energy, decode_latency) = phases
    return serial_edp([prefill, (decode_energy * steps, decode_latency * steps)])


def assess(architectures, macros, budget, steps):
    admitted = {
        hardware: (physical, proxy)
        for hardware, (physical, proxy, _) in architectures.items()
        if hardware.sram_totals(macros, "area_mm2") <= budget
    }
    shared = {hardware: mix_edp(physical, steps) for hardware, (physical, _) in admitted.items()}
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
    lower = mix_edp(independent, steps)
    if lower > shared[best] * (1 + 1e-9):
        raise AssertionError("Independent-hardware relaxation exceeds the shared solution")

    proxy_scores = {hw: mix_edp(proxy, steps) for hw, (_, proxy) in admitted.items()}
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
    return {
        "sram_area_limit_mm2": budget,
        "decode_steps": steps,
        "hardware_points": len(admitted),
        "shared_edp_pj_ns": shared[best],
        "shared_winner": asdict(best),
        "independent_hardware_edp_pj_ns": lower,
        "independent_phase_edp_winners": phase_winners,
        "shared_hardware_penalty": shared[best] / lower - 1,
        "architecture_first": controls,
    }


def run(table, output, *, smoke=False):
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
        architectures[hardware] = evaluate(hardware, macros)
        print("NATIVE_POINT " + json.dumps({
            "hardware": asdict(hardware),
            "sram_area_mm2": hardware.sram_totals(macros, "area_mm2"),
            "sram_leak_mw": hardware.sram_totals(macros, "leak_mw"),
            "native_rows": architectures[hardware][2],
            "seconds": round(perf_counter() - t0, 3),
        }), flush=True)
    cases = [assess(architectures, macros, reference * factor, steps)
             for factor, steps in product(BUDGET_FACTORS, DECODE_STEPS)]
    report = {
        "cacti_revision": CACTI_REVISION,
        "scope": "one prefill GEMM and repeated cold fixed-context decode GEMV",
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
    args = parser.parse_args()
    run(json.loads(args.table.read_text(encoding="utf-8")), args.output, smoke=args.smoke)


if __name__ == "__main__":
    main()
