"""Run native FFM remapping and a conservative architecture bound on a GPT block."""

import argparse
from dataclasses import asdict
import gzip
import json
import logging
from math import isclose
from pathlib import Path
from time import perf_counter

import accelforge as af
from accelforge.mapper.FFM.main import join_pmappings, make_pmappings
from accelforge.model.main import evaluate_mapping

from research.physical_cost.banked_scale import DeepArchitecture
from research.physical_cost.mixed_gate import DRAM_BIT_J, price_sram
from research.tracking_audit.common import clear_switches


ROOT = Path(__file__).resolve().parents[2]
WORKLOAD = ROOT / "examples/workloads/gpt3_6.7B.yaml"
ARCH = Path(__file__).with_name("two_level_nvdla.yaml")
METRICS = af.Metrics.ENERGY | af.Metrics.LATENCY
ENERGY, LATENCY, MAPPING = ("Total<SEP>energy", "Total<SEP>latency", "Total<SEP>mapping")
MAC_J = 0.084e-12
MAC_SECONDS = 1e-9
ARCHITECTURES = (
    DeepArchitecture(16, 64, 2, 16384, 1024, ddr_word_ns=4),
    DeepArchitecture(16, 128, 4, 16384, 1024),
    DeepArchitecture(32, 64, 2, 65536, 1024),
    DeepArchitecture(32, 128, 4, 16384, 1024, ddr_word_ns=1),
    DeepArchitecture(64, 64, 4, 16384, 1024),
)


def spec_for_block(hw, macros, tokens, width):
    spec = af.Spec.from_yaml(ARCH, WORKLOAD, jinja_parse_data={"N_TOKENS": tokens})
    spec.workload.rank_sizes.update({"D": width, "H": width // 16, "E": 16, "F": 16,
                                     "G": width, "J": width, "C": 4 * width})
    price_sram(spec, hw, macros)
    for action in ("read", "write"):
        spec.arch.find("MainMemory").actions[action].latency = hw.ddr_word_ns * 1e-9 / (64 * 8)
    spec.model.metrics = spec.mapper.ffm.metrics = METRICS
    spec.mapper.ffm.max_fused_loops = 1
    return spec


def compulsory_weights(width):
    return {("V", "WV"): 8 * width**2, ("K", "WK"): 8 * width**2,
            ("Q", "WQ"): 8 * width**2, ("Z", "WZ"): 8 * width**2,
            ("FFA", "WFFA"): 32 * width**2, ("FFB", "WFFB"): 32 * width**2}


def lower_bound(hw, macros, tokens, width, cold_ddr):
    # Q/K/V and output projections, both attention contractions, and the two FFN GEMMs.
    projections = 4 * tokens * width**2
    attention = 2 * tokens**2 * width
    feed_forward = 2 * tokens * width * (4 * width)
    macs = projections + attention + feed_forward
    seconds = macs * MAC_SECONDS / (hw.x * hw.y)
    dynamic = macs * MAC_J
    if cold_ddr:
        # The outermost MainMemory backs all six external weights. These
        # weights are each consumed in full, even when intermediates fuse.
        bits = sum(compulsory_weights(width).values())
        seconds = max(seconds, bits * hw.ddr_word_ns * 1e-9 / (64 * 8))
        dynamic += bits * DRAM_BIT_J
    leak_w = hw.sram_totals(macros, "leak_mw") * 1e-3
    return (dynamic + leak_w * seconds) * seconds


def remap(hw, macros, tokens, width, cold_ddr):
    start = perf_counter()
    spec = spec_for_block(hw, macros, tokens, width)
    partial = make_pmappings(spec, print_number_of_pmappings=False)
    generated = perf_counter()
    frontier = join_pmappings(partial).data
    if frontier.empty:
        raise RuntimeError(f"Native FFM returned no complete GPT mapping on {hw}")
    joined = perf_counter()
    leak_w = hw.sram_totals(macros, "leak_mw") * 1e-3
    objectives = (frontier[ENERGY] + leak_w * frontier[LATENCY]) * frontier[LATENCY]
    row = frontier.iloc[int(objectives.to_numpy().argmin())]
    spec.mapping = row[MAPPING]()
    if cold_ddr:
        spec.model.metrics |= af.Metrics.ACTIONS
    replay = evaluate_mapping(spec).data.iloc[0]
    if not all(isclose(float(replay[key]), float(row[key]), rel_tol=1e-6) for key in (ENERGY, LATENCY)):
        raise AssertionError(f"Native replay differs from joined energy or latency on {hw}")
    delay = float(row[LATENCY])
    edp = (float(row[ENERGY]) + leak_w * delay) * delay
    read_bits = {}
    if cold_ddr:
        for (op, weight), minimum in compulsory_weights(width).items():
            column = f"{op}<SEP>action<SEP>MainMemory<SEP>{weight}<SEP>read"
            read_bits[weight] = int(replay[column])
            if read_bits[weight] < minimum:
                raise AssertionError(f"Native replay violates the cold DDR input contract for {weight}")
    return {
        "edp_j_s": edp, "dynamic_j": float(row[ENERGY]), "seconds": delay,
        "replayed_dynamic_j": float(replay[ENERGY]), "replayed_seconds": float(replay[LATENCY]),
        "generation_wall_s": generated - start, "join_wall_s": joined - generated,
        "replay_wall_s": perf_counter() - joined, "frontier_rows": len(frontier),
        "einsums": list(spec.workload.einsum_names),
        "replayed_weight_read_bits": read_bits,
    }


def run(macros, tokens, width, output, cap, cold_ddr=False):
    hardware = tuple(hw for hw in ARCHITECTURES if hw.sram_totals(macros, "area_mm2") <= cap)
    if not hardware:
        raise ValueError("The SRAM cap excludes all native probe architectures")
    lower = {hw: lower_bound(hw, macros, tokens, width, cold_ddr) for hw in hardware}
    report = {"tokens": tokens, "width": width, "sram_area_cap_mm2": cap,
              "max_fused_loops": 1, "cold_ddr_bound": cold_ddr, "architectures": []}
    upper = float("inf")
    evaluations = {}

    def evaluate(hw, opened):
        result = remap(hw, macros, tokens, width, cold_ddr)
        if lower[hw] > result["edp_j_s"] * (1 + 1e-6):
            raise AssertionError(f"Compute lower bound exceeds native EDP on {hw}")
        evaluations[hw] = result["edp_j_s"]
        report["architectures"].append({
            "hardware": asdict(hw), "sram_mm2": hw.sram_totals(macros, "area_mm2"),
            "lower_edp_j_s": lower[hw], "opened_by_bound": opened, **result,
        })
        print(hw, "opened", opened, "lower", lower[hw], "EDP", result["edp_j_s"], flush=True)
        output.write_bytes(gzip.compress(json.dumps(report, indent=2).encode(), mtime=0))
        return result["edp_j_s"]

    ordered = sorted(hardware, key=lambda h: (lower[h], h))
    start = perf_counter()
    for hw in ordered:
        # A numerical margin keeps near-equality on the remap side.
        if lower[hw] >= upper * (1 + 1e-6):
            break
        upper = min(upper, evaluate(hw, True))
    report["proof_wall_s"] = perf_counter() - start
    # Independently remap every excluded architecture after the proof.
    for hw in ordered:
        if hw not in evaluations:
            evaluate(hw, False)
    if upper != min(evaluations.values()):
        raise AssertionError("The architecture bound disagrees with the exhaustive native sweep")
    report["exact_native_edp_j_s"] = upper
    report["architectures_opened"] = sum(row["opened_by_bound"] for row in report["architectures"])
    output.write_bytes(gzip.compress(json.dumps(report, indent=2).encode(), mtime=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--tokens", type=int, default=8)
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--area", type=float, default=1.35)
    parser.add_argument("--cold-ddr-bound", action="store_true")
    args = parser.parse_args()
    if args.tokens < 1 or args.width < 16 or args.width % 16:
        parser.error("Use a positive token count and a positive width divisible by the 16-element head")
    clear_switches()
    af.set_n_parallel_jobs(1)
    logging.basicConfig(level=logging.ERROR, force=True)
    macros = {int(k): v for k, v in json.loads(args.table.read_text())["macros"].items()}
    run(macros, args.tokens, args.width, args.output, args.area, args.cold_ddr_bound)


if __name__ == "__main__":
    main()
