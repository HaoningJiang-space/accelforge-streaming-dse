"""Offline check: would a utilization-aware max(compute, memory) model pick good GEMM tiles?

Post-hoc and offline: it re-scores accepted PyTorchSim runs already archived in
results/gemm_fidelity and results/gemm_cycle_model; no simulation is run and no
prediction was frozen. See MAX_MODEL_CHECK.md.

Usage: python3 -m research.dnn_benchmarks.max_model_check
"""
import json
import math
import statistics
from pathlib import Path

from .gemm_fidelity import BUDGETS, cells, useful_bytes

RESULTS = Path(__file__).with_name('results')
ARRAYS, DIM = 2, 128


def accepted_runs():
    runs = {}
    for experiment in ('gemm_fidelity', 'gemm_cycle_model'):
        for line in (RESULTS / experiment / 'runs.jsonl').read_text().splitlines():
            audit = json.loads(line).get('audit') or {}
            if audit.get('timing_accepted') and audit.get('numerical_equal') and audit.get('mode') == 'external':
                runs.setdefault(tuple(audit['shape']), {})[tuple(audit['requested_tile'][:3])] = audit['total_cycles']
    return runs


def predictions(shape, tile, bandwidth):
    (m, n, k), (tm, tn, tk) = shape, tile
    iterations = (m // tm) * (n // tn) * (k // tk)
    memory = useful_bytes(shape, tile) / bandwidth
    # Weight-stationary passes: each holds at most DIM x DIM of the (tk, tn) slice.
    passes = iterations * tm * math.ceil(tn / DIM) * math.ceil(tk / DIM) / ARRAYS
    ideal = m * n * k / (ARRAYS * DIM * DIM)
    return {'traffic': useful_bytes(shape, tile), 'max_ideal': max(memory, ideal),
            'max_util': max(memory, passes), 'sum_util': memory + passes}


def main():
    runs = accepted_runs()
    for bandwidth in (390, 1024, 2048):
        print(f'bandwidth {bandwidth} B/cycle')
        regrets = {}
        for shape, measured in runs.items():
            for budget in BUDGETS:
                within = [t for t in measured if cells(t) <= budget]
                if len(within) < 3:
                    continue
                fastest = min(measured[t] for t in within)
                for name in ('traffic', 'max_ideal', 'max_util', 'sum_util'):
                    score = {t: predictions(shape, t, bandwidth)[name] for t in within}
                    tied = [t for t in within if score[t] <= 1.01 * min(score.values())]
                    ratios = [measured[t] / fastest for t in tied]
                    regrets.setdefault(name, []).append((min(ratios), max(ratios)))
        for name, pairs in regrets.items():
            best, worst = zip(*pairs)
            print(f'  {name:9s} groups={len(pairs)} best-tie median={statistics.median(best):.2f} '
                  f'>1.1x={sum(r > 1.1 for r in best)} | worst-tie median={statistics.median(worst):.2f} '
                  f'max={max(worst):.2f} >1.1x={sum(r > 1.1 for r in worst)}')


if __name__ == '__main__':
    main()
