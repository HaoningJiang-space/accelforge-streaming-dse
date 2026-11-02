# Tracking audit

Bounded experiments behind the 1/2-scale GLU shared-vs-independent EDP mismatch.

- `run_capped.sh CAP_GB TIMEOUT_S LOG -- cmd...`: runs `cmd` in its own process group and kills only that
  group when total RSS or wall time exceeds the cap. Set `NO_VLIMIT=1` for CUDA runs.
- `diag_half.py [CAP_MIB]`: half-scale GLU (256,512,1024) on tpu_v4i. Runs (A) shared RESOURCE_USAGE
  search at 4 MiB with `AF_VARIABLE_RESOURCES=GlobalBuffer`, filters it to CAP and re-evaluates the
  best mapping at CAP; (B) independent ENERGY|LATENCY at CAP; (C) independent with RESOURCE_USAGE at CAP.
- `p0_profile.py`, `p0_bench.py`, `p0_diag.py`, `sumprof.py`: join profiling and CPU-vs-GPU Pareto
  microbenchmarks. They were written against upstream `04cf894e` and are kept for reference.

Observed on tag1 (`ea09a3df`), unlimited templates, fixed bandwidth: at 0.25 and 0.375 MiB the shared
search returned EDP 1.8202e-8 and 1.8105e-8 while independent FFM returned 1.8361e-8 for both.
