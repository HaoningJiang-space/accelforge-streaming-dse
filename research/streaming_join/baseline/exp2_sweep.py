"""Step 1: independent exact FFM per (GLB size, DRAM bandwidth) on GLU, tpu_v4i.
   Step 2 (B1): one RESOURCE_USAGE search at the largest GLB, then filter by capacity; compare best EDP."""
import json, os, sys, time
import numpy as np
import accelforge as af
from accelforge.mapper.FFM.main import make_pmappings, join_pmappings

GLU = os.path.expanduser("~/graph_dse/accelforge/examples/workloads/transformers/_feedforward_types/glu_standalone.yaml")
M, G, C = 512, 1024, 2048
MB = 1024 * 1024 * 8  # bits
SIZES = [0.5, 1, 2, 4, 8]          # GLB MB
BWS = [1 / 16, 1 / 4, 1]           # DRAM bandwidth scale vs 614 GB/s
OUT = sys.argv[1]

def build(size_mb, bscale, metrics):
    spec = af.Spec.from_yaml(af.examples.arches.tpu_v4i, GLU,
        jinja_parse_data={"BATCH_SIZE": 1, "N_NEW_TOKENS": M, "N_HIDDEN_DIMS": G, "N_FF_DIMS": C})
    spec.arch.find("GlobalBuffer").size = size_mb * MB
    for a in spec.arch.find("MainMemory").actions:
        a.throughput_scale = bscale
    spec.mapper.metrics = metrics
    return spec

def run(spec):
    t0 = time.time()
    pm = make_pmappings(spec, print_progress=False)
    t1 = time.time()
    res = join_pmappings(pm, spec.mapper.metrics, print_progress=False)
    t2 = time.time()
    return res, t1 - t0, t2 - t1

def rows(res):
    d = res.data
    E = d["Total<SEP>energy"].to_numpy(dtype=float)
    L = d["Total<SEP>latency"].to_numpy(dtype=float)
    assert (E > 0).all() and (L > 0).all(), "non-positive energy/latency"
    return E, L

log = open(OUT, "a")
def emit(**kw):
    log.write(json.dumps(kw) + "\n"); log.flush(); print(kw, flush=True)

# ---- Step 1: independent exact runs
indep = {}
for s in SIZES:
    for b in BWS:
        spec = build(s, b, af.Metrics.ENERGY | af.Metrics.LATENCY)
        res, tm, tj = run(spec)
        E, L = rows(res)
        i = int(np.argmin(E * L))
        indep[(s, b)] = float(E[i] * L[i])
        emit(kind="indep", size_mb=s, bw=b, make=tm, join=tj, n=len(E), edp=float(E[i] * L[i]), E=float(E[i]), L=float(L[i]))

# ---- Step 2 (B1): one resource-usage search at the largest GLB, ref bandwidth = 1
ref_s = max(SIZES)
spec = build(ref_s, 1.0, af.Metrics.ENERGY | af.Metrics.LATENCY | af.Metrics.RESOURCE_USAGE)
res, tm, tj = run(spec)
E, L = rows(res)
use = np.atleast_1d(res.resource_usage(list_if_one_mapping=True)["GlobalBuffer"]).astype(float) * ref_s * MB
emit(kind="shared", size_mb=ref_s, bw=1.0, make=tm, join=tj, n=len(E))
for s in SIZES:
    ok = use <= s * MB * (1 + 1e-9)
    if ok.any():
        j = int(np.argmin(np.where(ok, E * L, np.inf)))
        emit(kind="reuse_B1", size_mb=s, bw=1.0, n_ok=int(ok.sum()), edp=float(E[j] * L[j]),
             indep_edp=indep[(s, 1.0)], ratio=float(E[j] * L[j] / indep[(s, 1.0)]))
    else:
        emit(kind="reuse_B1", size_mb=s, bw=1.0, n_ok=0)
