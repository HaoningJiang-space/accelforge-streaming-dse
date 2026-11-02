"""P0: CPU (AccelForge numba SFS+BNL) vs GPU Pareto on real dumped FFM Pareto inputs.

GPU method: per column, replace values by dense ranks (int32, exact order-preserving), group by
'diff' columns, sort each group by rank-sum. A point can only be dominated by an earlier point
with a strictly smaller rank-sum, so each thread scans only that prefix of its group.
usage: CUDA_VISIBLE_DEVICES=1 python p0_bench.py file.npz ...
"""
import sys, time
import numpy as np
import pandas as pd
import cupy as cp
from accelforge.mapper.FFM._pareto_df.fast_pareto import fast_pareto_mask, _dedup_mask

MAX_DIMS = 32  # size of the per-thread rank buffer ri[] in the kernel below
KERNEL = cp.RawKernel(r"""
extern "C" __global__
void pareto(const int* __restrict__ R, const long long* __restrict__ seg_start,
            const long long* __restrict__ sum_start, int n, int d, unsigned char* keep) {
    // R: n x d ranks in sorted order. seg_start[i]: first index of i's group.
    // sum_start[i]: first index in the group whose rank-sum equals i's (candidates are before it).
    long long i = (long long)blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    int ri[32];
    for (int k = 0; k < d; k++) ri[k] = R[i * d + k];
    for (long long j = seg_start[i]; j < sum_start[i]; j++) {
        bool leq = true;
        for (int k = 0; k < d; k++) { if (R[j * d + k] > ri[k]) { leq = false; break; } }
        if (leq) { keep[i] = 0; return; }   // smaller sum + all <= implies strictly dominates
    }
    keep[i] = 1;
}
""", "pareto")


def prep(data, goals):
    """Mirror fast_pareto_mask: min/max columns (drop constants), diff columns as groups."""
    cols, diff = [], []
    for c, g in enumerate(goals):
        col = data[:, c]
        if g == "diff":
            diff.append(col)
        elif g in ("min", "max"):
            if col.min() == col.max():
                continue
            cols.append(col if g == "min" else -col)
        else:
            raise ValueError(g)
    n = len(data)
    ranks = np.empty((n, len(cols)), dtype=np.int32)
    for k, col in enumerate(cols):
        ranks[:, k] = np.unique(col, return_inverse=True)[1]
    if diff:
        df = pd.DataFrame(np.column_stack(diff))
        gid = df.groupby(list(df.columns), sort=False).ngroup().to_numpy()
    else:
        gid = np.zeros(n, dtype=np.int64)
    return ranks, gid


def gpu_pareto(data, goals):
    t0 = time.perf_counter()
    ranks, gid = prep(data, goals)
    n, d = ranks.shape
    if d > MAX_DIMS:
        raise ValueError(f'{d} Pareto dimensions exceed the kernel limit of {MAX_DIMS}')
    rsum = ranks.sum(axis=1, dtype=np.int64)
    order = np.lexsort((rsum, gid))
    g_s, s_s = gid[order], rsum[order]
    idx = np.arange(n)
    new_g = np.r_[True, g_s[1:] != g_s[:-1]]
    seg_start = np.maximum.accumulate(np.where(new_g, idx, 0))
    new_s = new_g | np.r_[True, s_s[1:] != s_s[:-1]]
    sum_start = np.maximum.accumulate(np.where(new_s, idx, 0))
    t1 = time.perf_counter()
    R = cp.asarray(np.ascontiguousarray(ranks[order]))
    keep = cp.zeros(n, dtype=cp.uint8)
    KERNEL(((n + 255) // 256,), (256,), (R, cp.asarray(seg_start), cp.asarray(sum_start), np.int32(n), np.int32(d), keep))
    k = cp.asnumpy(keep).astype(bool)
    t2 = time.perf_counter()
    mask = np.zeros(n, dtype=bool)
    mask[order[k]] = True
    # same duplicate removal as fast_pareto_mask (first occurrence among Pareto rows)
    pidx = np.where(mask)[0]
    dup = pd.DataFrame(data[pidx]).duplicated(keep="first").values
    mask[pidx[dup]] = False
    t3 = time.perf_counter()
    return mask, {"prep": t1 - t0, "gpu": t2 - t1, "post": t3 - t2, "d": d, "groups": int(gid.max()) + 1}


cp.zeros(1).sum()  # init context
fast_pareto_mask(np.random.rand(100, 3), ["min"] * 3)  # numba warmup
for f in sys.argv[1:]:
    z = np.load(f)
    data, goals = z["data"], list(z["goals"])
    t = time.perf_counter(); m_cpu = fast_pareto_mask(data, goals); t_cpu = time.perf_counter() - t
    gpu_pareto(data[:1000], goals)  # kernel warmup
    t = time.perf_counter(); m_gpu, info = gpu_pareto(data, goals); t_gpu = time.perf_counter() - t
    same = bool((m_cpu == m_gpu).all())
    print(f"{f}: n={len(data)} dims={info['d']} groups={info['groups']} front={m_cpu.sum()} "
          f"cpu={t_cpu:.3f}s gpu_total={t_gpu:.3f}s (prep {info['prep']:.3f} kernel+copy {info['gpu']:.3f} post {info['post']:.3f}) "
          f"speedup={t_cpu / t_gpu:.1f}x match={same} diff={(m_cpu != m_gpu).sum()}", flush=True)
