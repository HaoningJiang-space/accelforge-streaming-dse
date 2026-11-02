"""Explain CPU/GPU Pareto mask mismatches with an exact (slow but simple) reference on mismatched rows."""
import sys
import numpy as np
import pandas as pd
from accelforge.mapper.FFM._pareto_df.fast_pareto import fast_pareto_mask
sys.argv, files = sys.argv[:1], sys.argv[1:]
import p0_bench  # noqa: E402  (reuses gpu_pareto; its own loop has no files to run)

for f in files:
    z = np.load(f)
    data, goals = z["data"], list(z["goals"])
    print(f, "dtype", data.dtype, "goals", goals)
    for c, g in enumerate(goals):
        col = data[:, c]
        print(f"  col{c} {g}: nan={np.isnan(col).sum()} negzero={(np.signbit(col) & (col == 0)).sum()} uniq={len(np.unique(col))}")
    m_cpu = fast_pareto_mask(data, goals)
    m_gpu, _ = p0_bench.gpu_pareto(data, goals)
    cpu_only, gpu_only = np.where(m_cpu & ~m_gpu)[0], np.where(m_gpu & ~m_cpu)[0]
    print("  cpu_only", len(cpu_only), "gpu_only", len(gpu_only))
    # exact reference for a few mismatched rows: dominated by any row in the same diff group?
    mins = [c for c, g in enumerate(goals) if g == "min"]
    diffs = [c for c, g in enumerate(goals) if g == "diff"]
    X = data[:, mins].astype(np.float64)
    for name, rows in (("cpu_only", cpu_only[:5]), ("gpu_only", gpu_only[:5])):
        for i in rows:
            same = np.ones(len(data), bool)
            for c in diffs:
                same &= (data[:, c] == data[i, c]) | (np.isnan(data[:, c]) & np.isnan(data[i, c]))
            dom = same & (X <= X[i]).all(1) & (X < X[i]).any(1)
            dup_before = same[:i] & (X[:i] == X[i]).all(1)
            print(f"   {name} row {i}: dominated={dom.any()} dup_earlier={dup_before.any()} diffvals={data[i, diffs]}")
