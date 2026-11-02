"""P0: where does FFM join time and memory go? Serial join with timing hooks; dumps the
largest Pareto inputs for CPU/GPU Pareto microbenchmarks.

usage: python p0_profile.py {mm3|glu} OUTDIR
"""
import os, sys, time, json, resource
import numpy as np
import pandas
import accelforge as af
from accelforge.mapper.FFM.main import make_pmappings, join_pmappings
from accelforge.mapper.FFM._join_pmappings import pmapping_dataframe as pdf_mod
from accelforge.mapper.FFM._pareto_df import pareto as pareto_mod

case, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)

def peak_gb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**2

# ---------------------------------------------------------------- hooks
T = {"pd_merge": 0.0, "merge_next": 0.0, "limit_capacity": 0.0, "makepareto": 0.0, "fast_pareto": 0.0}
events = []
n_dumped = [0]

_orig_merge = pandas.merge
def merge_hook(*a, **k):
    t = time.perf_counter(); r = _orig_merge(*a, **k); dt = time.perf_counter() - t
    T["pd_merge"] += dt
    events.append({"ev": "pd_merge", "how": k.get("how"), "n_out": len(r), "ncols": r.shape[1], "t": dt,
                   "mem_mb": r.memory_usage(deep=False).sum() / 2**20})
    return r
pandas.merge = merge_hook

def wrap_method(cls, name, key, size_fn):
    orig = getattr(cls, name)
    def w(self, *a, **k):
        n_in = size_fn(self, a)
        t = time.perf_counter(); r = orig(self, *a, **k); dt = time.perf_counter() - t
        T[key] += dt
        events.append({"ev": key, "n_in": n_in, "n_out": len(r.data) if hasattr(r, "data") else None, "t": dt,
                       "peak_gb": peak_gb()})
        return r
    setattr(cls, name, w)

PDF = pdf_mod.PmappingDataframe
wrap_method(PDF, "merge_next", "merge_next", lambda s, a: (len(s.data), len(a[0].data)))
wrap_method(PDF, "limit_capacity", "limit_capacity", lambda s, a: len(s.data))

_orig_mp = pdf_mod.makepareto
def mp_hook(mappings, *a, **k):
    t = time.perf_counter(); r = _orig_mp(mappings, *a, **k); dt = time.perf_counter() - t
    T["makepareto"] += dt
    events.append({"ev": "makepareto", "n_in": len(mappings), "n_out": len(r), "t": dt})
    return r
pdf_mod.makepareto = mp_hook

_orig_fpm = pareto_mod.fast_pareto_mask
def fpm_hook(values, goals, *a, **k):
    t = time.perf_counter(); r = _orig_fpm(values, goals, *a, **k); dt = time.perf_counter() - t
    T["fast_pareto"] += dt
    n = len(values)
    e = {"ev": "fast_pareto", "n_in": n, "n_out": int(r.sum()), "t": dt,
         "n_min": goals.count("min"), "n_diff": goals.count("diff")}
    if n >= 100_000 and n_dumped[0] < 6:
        f = os.path.join(outdir, f"pareto_in_{n_dumped[0]}.npz")
        np.savez(f, data=np.asarray(values), goals=np.array(goals), mask=r)
        e["dump"] = f; n_dumped[0] += 1
    events.append(e)
    return r
pareto_mod.fast_pareto_mask = fpm_hook

# ---------------------------------------------------------------- spec
if case == "mm3":
    spec = af.Spec.from_yaml(af.examples.arches.snowcat, af.examples.workloads.basic.matmuls,
                             jinja_parse_data={"N_EINSUMS": 3, "M": 1024, "KN": 1024})
    spec.mapper.metrics = af.Metrics.ENERGY | af.Metrics.RESOURCE_USAGE
elif case.startswith("glu"):
    # glu: ENERGY|LATENCY at full size. glu_ru<k>: + RESOURCE_USAGE with M,G,C divided by k.
    k = int(case[6:]) if case.startswith("glu_ru") else 1
    GLU = os.path.expanduser("~/graph_dse/accelforge/examples/workloads/transformers/_feedforward_types/glu_standalone.yaml")
    spec = af.Spec.from_yaml(af.examples.arches.tpu_v4i, GLU,
                             jinja_parse_data={"BATCH_SIZE": 1, "N_NEW_TOKENS": 512 // k, "N_HIDDEN_DIMS": 1024 // k, "N_FF_DIMS": 2048 // k})
    spec.arch.find("GlobalBuffer").size = 8 * 1024 * 1024 * 8
    spec.mapper.metrics = af.Metrics.ENERGY | af.Metrics.LATENCY
    if case.startswith("glu_ru"):
        spec.mapper.metrics |= af.Metrics.RESOURCE_USAGE
else:
    raise SystemExit(case)

af.set_n_parallel_jobs(8)
t0 = time.time()
pm = make_pmappings(spec, print_progress=False)
t1 = time.time()
print(f"make={t1-t0:.1f}s peak={peak_gb():.2f}GB", flush=True)

af.set_n_parallel_jobs(1)  # serial join: all work in this process, so hooks see it
events.clear(); [T.__setitem__(k, 0.0) for k in T]
res, stats = join_pmappings(pm, spec.mapper.metrics, print_progress=False, report_statistics=True)
t2 = time.time()

summary = {"case": case, "make_s": t1 - t0, "join_s": t2 - t1, "n_front": len(res.data),
           "peak_rss_gb": peak_gb(), "times": T}
print(json.dumps(summary, indent=1), flush=True)
big = sorted([e for e in events if e["ev"] in ("pd_merge", "fast_pareto")], key=lambda e: -e["n_in" if "n_in" in e else "n_out"])[:12]
for e in big:
    print(e)
json.dump({"summary": summary, "events": events}, open(os.path.join(outdir, "profile.json"), "w"), default=str)
