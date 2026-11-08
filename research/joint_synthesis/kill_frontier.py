"""Count the residual mapping bank before building a late-binding search."""

import argparse
import json
import logging
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

import numpy as np
from paretoset import paretoset

from accelforge.frontend.mapping import TensorHolder
from accelforge.mapper.FFM._pareto_df import exact_resources
from research.joint_search import ffm_backend as ffm
from research.tracking_audit import common


CASES = {
    "glu": (256, 512, 1024),
    "attention": (256, 8, 64),
    "resnet": (),
}
SHAPE = (32, 192)
GB_BITS = 2 * 2**23
REGISTER_BITS = 8
DEMANDS = ("reuse_input", "reuse_output", "GlobalBuffer", "Register")
ACTIONS = tuple(
    (memory, action)
    for memory in ("MainMemory", "GlobalBuffer", "Register")
    for action in ("read", "write")
) + (("MAC", "compute"),)
SERVICE = ("MAC", "MainMemory", "GlobalBuffer")
N_DEMANDS = len(DEMANDS)
GB_BW_MIN = 0.25
GB_BW_MAX = 2.0
BUDGET = 1.5
TARGET = 1000


def workload_spec(case, metrics):
    if case == "resnet":
        spec = common.af.Spec.from_yaml(
            common.ROOT / "examples/arches/nvdla.yaml",
            Path(__file__).with_name("resnet_bottleneck.yaml"),
        )
    else:
        spec = common.build(common.Case(case, "nvdla", CASES[case]), 2, metrics)
    return configure_spec(spec, SHAPE, GB_BITS)


def configure_spec(spec, shape, gb_bits, bandwidth=1.0):
    buffer = spec.arch.find("GlobalBuffer")
    buffer.size = gb_bits
    buffer.latency_scale = 1 / bandwidth
    spec.arch.find("MainMemory").tensors.keep = "All"
    spec.arch.find("Register").size = REGISTER_BITS
    for dimension, size in zip(spec.arch.find("ArrayFanout").spatial, shape, strict=True):
        dimension.fanout = size
        dimension.min_usage = 0
    return spec._spec_eval_expressions(eval_arch=False, eval_non_arch=True)


def native_jobs(spec, metrics):
    jobs = ffm.pmapper.get_jobs(spec, metrics, spec.workload.einsum_names, True)
    ffm.pmapper._fill_jobs_with_memories_to_track(jobs, spec, metrics, False)
    return jobs


def native_signature(job):
    """Retain native tiles at the boundary before cross-template Pareto."""
    original_model = ffm.tiles.run_model

    def capture(job):
        symbols, columns, memories, spatial, tensor_mapping = original_model(job)
        for dimension in job.spec.arch.find("ArrayFanout").spatial:
            key = f"usage<SEP>spatial<SEP>ArrayFanout<SEP>{dimension.name}"
            columns[f"signature_{dimension.name}"] = (
                spatial[key] * dimension.fanout / dimension.usage_scale
            )
        for memory in ("GlobalBuffer", "Register"):
            # The reservation prefix is already tracked in bits by native FFM.
            key = f"usage<SEP>memory<SEP>{memory}"
            columns[f"reservation<SEP>{memory}<SEP>signature"] = memories.get(key, 0)
        return symbols, columns, memories, spatial, tensor_mapping

    with patch.object(ffm.tiles, "run_model", capture):
        frame, _ = ffm.tiles._make_tile_shapes(job)
    if frame.empty:
        return np.empty((0, N_DEMANDS + len(ACTIONS) + len(SERVICE))), np.empty(0)

    demand_cols = [f"signature_{name}" for name in DEMANDS[:2]] + [
        f"reservation<SEP>{name}<SEP>signature" for name in DEMANDS[2:]
    ]
    demands = frame[demand_cols].to_numpy(dtype=np.float64)
    if not np.allclose(demands, np.rint(demands), rtol=0, atol=1e-6):
        raise ValueError(f"Nonintegral physical demands in {job.einsum_name}")
    demands = np.rint(demands)
    if np.any(demands > [*SHAPE, GB_BITS, REGISTER_BITS]):
        raise ValueError(f"Candidate exceeds the envelope in {job.einsum_name}")

    counts = {key: np.zeros(len(frame)) for key in ACTIONS}
    for column in frame:
        if column.startswith("action<SEP>"):
            _, component, _, action = column.split("<SEP>")
            counts[component, action] += frame[column].to_numpy(dtype=np.float64)
    actions = np.column_stack(list(counts.values()))
    prices = np.array(
        [job.spec.arch.find(c).actions[a].energy for c, a in ACTIONS]
    ) * 1e12
    if (prices < 0).any():
        raise ValueError("Component prices must be nonnegative")
    energy = actions @ prices
    np.testing.assert_allclose(energy, frame["Total<SEP>energy"] * 1e12, rtol=1e-6)

    service = np.column_stack(
        [np.asarray(frame[f"latency<SEP>{c}"], dtype=np.float64) * 1e9 for c in SERVICE]
    )
    np.testing.assert_allclose(service.max(axis=1), frame["Total<SEP>latency"] * 1e9, rtol=1e-6)
    signature = np.column_stack((demands, actions, service))
    if not np.isfinite(signature).all() or (signature < 0).any():
        raise ValueError(f"Invalid signature in {job.einsum_name}")
    return signature, energy


def pareto_indices(values):
    varying = np.any(values != values[0], axis=0)
    if not varying.any():
        return np.array([0])
    return np.flatnonzero(paretoset(values[:, varying], distinct=True))


def epsilon_indices(values, factor):
    """One exact demand antichain in each box of component costs."""
    costs = values[:, N_DEMANDS:]
    positive = costs > 0
    logs = np.zeros_like(costs)
    np.log(costs, out=logs, where=positive)
    boxes = np.floor(logs / np.log(factor))
    boxes[~positive] = -np.inf
    _, assignment = np.unique(boxes, axis=0, return_inverse=True)
    order = np.argsort(assignment, kind="stable")
    starts = np.r_[0, np.flatnonzero(np.diff(assignment[order])) + 1, len(order)]
    keep = []
    for start, end in zip(starts[:-1], starts[1:]):
        group = order[start:end]
        # Enforce the approximation even if a floating-point box edge is rounded.
        if np.any(costs[group].max(axis=0) > factor * costs[group].min(axis=0)):
            keep.extend(group)
        else:
            keep.extend(group[pareto_indices(values[group, :N_DEMANDS])])
    return np.asarray(keep, dtype=np.intp)


def max_bandwidth(x, y, bits):
    return np.minimum(GB_BW_MAX, 2 * (BUDGET - x * y / np.prod(SHAPE) - bits / GB_BITS))


def latency(rows, bandwidth):
    mac, dram, gb = rows[:, -len(SERVICE):].T
    return np.maximum(np.maximum(mac, dram), gb / bandwidth)


def graph_bound(banks):
    """One-operator branches with a shared budget and a feasible incumbent."""
    feasible = []
    fits_budget = []
    for rows, energy in banks:
        bandwidth = max_bandwidth(*rows[:, :3].T)
        keep = bandwidth >= GB_BW_MIN
        if not keep.any():
            raise ValueError("No mappings fit the budget")
        feasible.append((rows[keep], energy[keep], latency(rows[keep], bandwidth[keep])))
        fits_budget.append(keep)

    incumbent = float("inf")
    incumbent_arch = None
    for x in (1, 2, 4, 8, 16, SHAPE[0]):
        for y in (1, 4, 16, 32, 64, SHAPE[1]):
            for bits in (32 * 8192, 128 * 8192, 512 * 8192, GB_BITS):
                bw = max_bandwidth(x, y, bits)
                if bw < GB_BW_MIN:
                    continue
                graph_e = graph_t = 0.0
                for rows, energy, _ in feasible:
                    fits = np.all(rows[:, :3] <= (x, y, bits), axis=1)
                    if not fits.any():
                        break
                    e, t = energy[fits], latency(rows[fits], bw)
                    pick = np.argmin(e * t)
                    graph_e += e[pick]
                    graph_t += t[pick]
                else:
                    if graph_e * graph_t < incumbent:
                        incumbent = graph_e * graph_t
                        incumbent_arch = [x, y, bits, float(bw)]

    # Each layer can use its own relaxed hardware and choose E and T separately.
    # Condition only the branch's layer on the selected mapping.
    min_e = [energy.min() for _, energy, _ in feasible]
    min_t = [times.min() for _, _, times in feasible]
    masks = []
    for i, (_, energy, times) in enumerate(feasible):
        others_e = sum(min_e[:i] + min_e[i + 1:])
        others_t = sum(min_t[:i] + min_t[i + 1:])
        lower = (energy + others_e) * (times + others_t)
        mask = fits_budget[i].copy()
        mask[mask] = lower <= incumbent * (1 + 1e-12)
        masks.append(mask)
    return {
        "incumbent_edp_pj_ns": float(incumbent) if incumbent_arch else None,
        "incumbent_arch_x_y_bits_bw": incumbent_arch,
        "relaxed_graph_edp_pj_ns": float(sum(min_e) * sum(min_t)),
        "fits_budget": [len(rows) for rows, _, _ in feasible],
        "survivors": [int(mask.sum()) for mask in masks],
    }, masks


def run(case, output, epsilon_edp):
    common.clear_switches()
    if not exact_resources.enabled():
        raise ValueError("The experiment requires bit-exact capacity accounting")
    common.set_jobs(1)
    logging.disable(logging.CRITICAL)
    metrics = common.RU | common.af.Metrics.ACTIONS
    factor = np.sqrt(1 + epsilon_edp)
    result = {
        "case": case,
        "shape_parameters": CASES[case],
        "envelope_x_y_gb_bits_register_bits": [*SHAPE, GB_BITS, REGISTER_BITS],
        "normalized_budget": BUDGET,
        "gb_bandwidth_multiplier_range": [GB_BW_MIN, GB_BW_MAX],
        "epsilon_edp": epsilon_edp,
        "status": "generating",
        "operators": {},
    }
    start = perf_counter()

    def save():
        result["seconds"] = round(perf_counter() - start, 3)
        temporary = output.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        temporary.replace(output)

    save()
    spec = workload_spec(case, metrics)
    jobs = native_jobs(spec, metrics)
    exact_banks, epsilon_banks = [], []
    for op, groups in jobs.items():
        chunks, energies = [], []
        num_templates = 0
        for group in groups.values():
            for job in group:
                backing = {
                    t for node in job.mapping.nodes
                    if isinstance(node, TensorHolder) and node.component == "MainMemory"
                    for t in node.tensors
                }
                if backing != spec.workload.einsums[op].tensor_names:
                    raise ValueError(f"Unexpected nonmaterialized template for {op}")
                rows, energy = native_signature(job)
                chunks.append(rows)
                energies.append(energy)
                num_templates += 1
        rows, energy = np.concatenate(chunks), np.concatenate(energies)
        if not len(rows):
            raise ValueError(f"No tile rows for {op}")
        front = pareto_indices(rows)
        rounded = front[epsilon_indices(rows[front], factor)]
        exact_banks.append((rows[front], energy[front]))
        epsilon_banks.append((rows[rounded], energy[rounded]))
        result["operators"][op] = {
            "templates": num_templates,
            "native_rows": len(rows),
            "distinct_signatures": len(np.unique(rows, axis=0)),
            "safe_dominance": len(front),
            "epsilon_boxes": len(rounded),
        }
        save()
        print(op, result["operators"][op], flush=True)

    for name, banks in (("exact", exact_banks), ("epsilon", epsilon_banks)):
        bound, _ = graph_bound(banks)
        for operator, fits, survives in zip(
            result["operators"].values(), bound.pop("fits_budget"), bound.pop("survivors"), strict=True
        ):
            operator[f"{name}_fits_budget"] = fits
            operator[f"{name}_after_bound"] = survives
        result[f"{name}_bound"] = bound
    result["status"] = "complete"
    result["meets_residual_target"] = result["epsilon_bound"]["incumbent_edp_pj_ns"] is not None and all(
        0 < op["epsilon_after_bound"] <= TARGET for op in result["operators"].values()
    )
    save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=CASES)
    parser.add_argument("output", type=Path)
    parser.add_argument("--epsilon-edp", type=float, default=0.10)
    args = parser.parse_args()
    if not 1e-6 <= args.epsilon_edp <= 1:
        parser.error("--epsilon-edp must be between 1e-6 and 1")
    run(args.case, args.output, args.epsilon_edp)


if __name__ == "__main__":
    main()
