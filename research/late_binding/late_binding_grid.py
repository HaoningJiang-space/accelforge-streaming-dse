"""Compare exact mapping-first binding with architecture-first search on one bank."""

import argparse
from bisect import bisect_right
from itertools import product
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np

from research.late_binding.kill_frontier import (
    CASES, GB_BITS, SHAPE, latency, native_jobs, native_signature, pareto_indices, workload_spec,
)
from research.tracking_audit import common


CAPACITY_BITS = 32 * 8192
LIMITS = (*SHAPE, GB_BITS // CAPACITY_BITS)
BW_TICKS = np.arange(2, 17)
CAPACITY_PRICE = 96
BW_PRICE = 384
AREA_TICKS = (9216, 4608)
CHECKPOINTS = (0.025, 0.25, 1.0)
# Shared anchors include the full array and two smaller geometries.
ANCHORS = ((32, 192, 4), (32, 192, 16), (16, 96, 8), (24, 144, 8), (8, 48, 4))


def fastest(x, y, banks, budget):
    return np.minimum(BW_TICKS[-1], (budget - x * y - CAPACITY_PRICE * banks) // BW_PRICE)


def energy_latency_front(energy, times):
    order = np.lexsort((times, energy))
    ordered_t = times[order]
    best_before = np.r_[np.inf, np.minimum.accumulate(ordered_t[:-1])]
    return order[ordered_t < best_before]


def serial_edp(layers):
    sum_e, sum_t = np.zeros(1), np.zeros(1)
    for e, t in layers:
        if not len(e):
            return float("inf")
        keep = energy_latency_front(e, t)
        sum_e = np.add.outer(sum_e, e[keep]).ravel()
        sum_t = np.add.outer(sum_t, t[keep]).ravel()
        keep = energy_latency_front(sum_e, sum_t)
        sum_e, sum_t = sum_e[keep], sum_t[keep]
    return float(np.min(sum_e * sum_t))


def fixed_arch_edp(bank, architecture, budget):
    """Exact fixed-hardware EDP by the two-dimensional serial cost frontier."""
    x, y, capacity = architecture
    bw = fastest(x, y, capacity, budget)
    if bw < BW_TICKS[0]:
        return float("inf")
    layers = []
    for rows, energy in bank:
        mask = np.all(rows[:, :3] <= (x, y, capacity * CAPACITY_BITS), axis=1)
        layers.append((energy[mask], latency(rows[mask], bw / 8)))
    return serial_edp(layers)


def exact_architecture_sweep(bank, budget, target):
    """Independent architecture-first oracle over all demand breakpoints."""
    start = perf_counter()
    demands = np.vstack([rows[:, :3] for rows, _ in bank]).astype(np.int64)
    demands[:, 2] = (demands[:, 2] + CAPACITY_BITS - 1) // CAPACITY_BITS
    axes = [np.unique(np.maximum(1, column)).tolist() for column in demands.T]
    best, reached, legal = float("inf"), None, 0
    for x, y, banks in product(*(axis[::-1] for axis in axes)):
        if fastest(x, y, banks, budget) < BW_TICKS[0]:
            continue
        legal += 1
        best = min(best, fixed_arch_edp(bank, (x, y, banks), budget))
        if reached is None and best <= target * (1 + 1e-9):
            reached = perf_counter() - start
    elapsed = perf_counter() - start
    np.testing.assert_allclose(best, target, rtol=1e-9)
    return {"legal_breakpoints": legal, "seconds": elapsed, "time_to_exact_s": reached}


def load_bank(path):
    bank = []
    with np.load(path, allow_pickle=False) as archive:
        for key in archive:
            if key.endswith("_rows"):
                rows, energy = archive[key], archive[key.removesuffix("_rows") + "_energy"]
                front = pareto_indices(rows)
                bank.append((rows[front], energy[front]))
    return bank


def replay(case, result_path):
    """Regenerate the native tile bank at each reported hardware witness."""
    common.clear_switches()
    common.set_jobs(1)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result["bank"] != case:
        raise ValueError("Replay workload differs from benchmark workload")
    metrics = common.RU | common.af.Metrics.ACTIONS
    for record in result["budgets"]:
        x, y, banks, bw = record["exact_arch_x_y_banks_bw_ticks"]
        spec = workload_spec(case, metrics, shape=(x, y), gb_bits=banks * CAPACITY_BITS, bandwidth=bw / 8)
        jobs = native_jobs(spec, metrics)
        layers = []
        for groups in jobs.values():
            rows, energy = zip(*(native_signature(job) for group in groups.values() for job in group))
            layers.append((np.concatenate(energy), latency(np.concatenate(rows), 1.0)))
        native = serial_edp(layers)
        record["regenerated_native_edp_pj_ns"] = native if np.isfinite(native) else None
        record["regenerated_matches_bank"] = bool(np.isclose(native, record["exact_edp_pj_ns"], rtol=1e-6))
        result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def bind(bank, budget, initial, anchors):
    """Exact branch-and-bound with an integer hardware completion for each prefix."""
    demands, energies, times = [], [], []
    for rows, energy in sorted(bank, key=lambda item: len(item[0])):
        d = rows[:, :3].astype(np.int64)
        d[:, 2] = (d[:, 2] + CAPACITY_BITS - 1) // CAPACITY_BITS
        demands.append(d)
        energies.append(energy)
        times.append(np.column_stack([latency(rows, bw / 8) for bw in BW_TICKS]))
    min_e = np.r_[np.cumsum([e.min() for e in energies][::-1])[::-1], 0]
    min_t = np.vstack([
        np.cumsum([t.min(axis=0) for t in times][::-1], axis=0)[::-1],
        np.zeros(len(BW_TICKS)),
    ])
    incumbent = initial
    witness = min(anchors, key=anchors.get) if np.isfinite(initial) else None
    branches = completed = 0

    def visit(depth, demand, energy, prefix_times):
        nonlocal incumbent, witness, branches, completed
        new_demand = np.maximum(demands[depth], demand)
        bandwidth = fastest(*new_demand.T, budget)
        fits = np.flatnonzero(bandwidth >= BW_TICKS[0])
        rate_indices = bandwidth[fits] - BW_TICKS[0]
        new_e = energy + energies[depth][fits]
        new_t = prefix_times[rate_indices] + times[depth][fits, rate_indices]
        lower = (new_e + min_e[depth + 1]) * (new_t + min_t[depth + 1, rate_indices])
        branches += len(fits)
        for position in np.argsort(lower):
            if lower[position] > incumbent * (1 + 1e-12):
                break
            candidate = fits[position]
            if depth + 1 == len(energies):
                completed += 1
                if lower[position] < incumbent:
                    incumbent = float(lower[position])
                    witness = tuple(map(int, new_demand[candidate]))
            else:
                visit(depth + 1, new_demand[candidate], new_e[position], prefix_times + times[depth][candidate])

    visit(0, np.ones(3, dtype=np.int64), 0.0, np.zeros(len(BW_TICKS)))
    if witness is None:
        raise ValueError("No feasible graph mapping in the architecture grid")
    np.testing.assert_allclose(fixed_arch_edp(bank, witness, budget), incumbent, rtol=1e-9)
    return incumbent, witness, branches, completed


def black_box(bank, budget, anchors, target, method, seed, optuna):
    rng = np.random.default_rng(seed)
    cache = dict(anchors)
    best = min(cache.values())
    reached = 0.0 if best <= target * (1 + 1e-9) else None
    timestamps, history = [0.0], [(best, 0)]
    start = perf_counter()
    if method == "tpe":
        study = optuna.create_study(sampler=optuna.samplers.TPESampler(seed=seed, multivariate=True))
        for point, edp in anchors.items():
            distributions = {
                name: optuna.distributions.IntDistribution(1, limit)
                for name, limit in zip(("x", "y", "banks"), LIMITS, strict=True)
            }
            study.add_trial(optuna.trial.create_trial(
                params=dict(zip(distributions, point, strict=True)), distributions=distributions, value=edp
            ))
    parents = [point for point in sorted(anchors, key=anchors.get) if np.isfinite(anchors[point])]
    queries = 0
    while perf_counter() - start < CHECKPOINTS[-1]:
        random_point = rng.integers(1, np.array(LIMITS) + 1)
        if method == "tpe":
            trial = study.ask()
            point = tuple(trial.suggest_int(name, 1, limit)
                          for name, limit in zip(("x", "y", "banks"), LIMITS, strict=True))
        elif method == "ga" and len(parents) >= 2 and rng.random() < 0.85:
            mom, dad = rng.integers(len(parents), size=2)
            child = np.where(rng.random(3) < 0.5, parents[mom], parents[dad])
            point = tuple(np.where(rng.random(3) < 0.3, random_point, child))
        else:
            point = tuple(random_point)
        if point not in cache:
            cache[point] = fixed_arch_edp(bank, point, budget)
            queries += 1
            if method == "ga" and np.isfinite(cache[point]):
                parents = sorted([*parents, point], key=cache.get)[:16]
        score = cache[point]
        if method == "tpe":
            study.tell(trial, score)
        finished = perf_counter() - start
        if score < target * (1 - 1e-9):
            raise ValueError(f"{method} beat the claimed optimum at {point}")
        best = min(best, score)
        timestamps.append(finished)
        history.append((best, queries))
        if reached is None and score <= target * (1 + 1e-9) and finished <= CHECKPOINTS[-1]:
            reached = finished
    snapshots = []
    for checkpoint in CHECKPOINTS:
        score, queries = history[bisect_right(timestamps, checkpoint) - 1]
        snapshots.append([checkpoint, score if np.isfinite(score) else None, queries])
    return {"seed": seed, "time_to_exact_s": reached, "checkpoints": snapshots}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bank", type=Path, help="Native .npz archive, or a workload name for replay")
    parser.add_argument("output", type=Path)
    parser.add_argument("--optuna-path", type=Path)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--replay-native", action="store_true", help="Regenerate the witnesses in an existing report")
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error("--seeds must be positive")
    if args.replay_native:
        if args.bank.name not in CASES:
            parser.error("--replay-native requires a registered workload name")
        replay(args.bank.name, args.output)
        return
    if args.optuna_path:
        sys.path.append(str(args.optuna_path.resolve()))
    import optuna
    optuna.logging.set_verbosity(optuna.logging.ERROR)
    start = perf_counter()
    bank = load_bank(args.bank)
    setup_s = perf_counter() - start
    result = {"bank": args.bank.stem, "shared_front_seconds": setup_s, "budgets": []}
    x, y, capacity = np.ogrid[1:LIMITS[0] + 1, 1:LIMITS[1] + 1, 1:LIMITS[2] + 1]
    for budget in AREA_TICKS:
        bw = fastest(x, y, capacity, budget)
        start = perf_counter()
        anchors = {point: fixed_arch_edp(bank, point, budget) for point in ANCHORS}
        anchor_s = perf_counter() - start
        start = perf_counter()
        score, arch, branches, leaves = bind(bank, budget, min(anchors.values()), anchors)
        exact_s = perf_counter() - start
        runs = {method: [black_box(bank, budget, anchors, score, method, seed, optuna)
                         for seed in range(args.seeds)] for method in ("random", "ga", "tpe")}
        result["budgets"].append({
            "budget_ticks": budget,
            "legal_architectures": int(np.maximum(0, bw - BW_TICKS[0] + 1).sum()),
            "max_bandwidth_architectures": int((bw >= BW_TICKS[0]).sum()),
            "common_anchor_seconds": anchor_s,
            "common_anchor_edp": min(anchors.values()) if any(np.isfinite(list(anchors.values()))) else None,
            "exact_edp_pj_ns": score,
            "exact_arch_x_y_banks_bw_ticks": [*arch, int(fastest(*arch, budget))],
            "exact_search_s": exact_s,
            "bound_evaluations": branches,
            "completed_graph_mappings": leaves,
            "black_box": runs,
            "architecture_sweep": exact_architecture_sweep(bank, budget, score),
        })
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
