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

## Results (half scale 256,512,1024; strict = `evaluate_mapping` at the exact capacity)

| GLB | independent FFM | shared, join-only (`var`) | shared, generation pushdown (`push`) |
|---|---|---|---|
| 0.25 MiB | 1.8361e-8 | 1.8202e-8, valid | 1.8361e-8, valid |
| 0.375 MiB | 1.8361e-8 | 1.8105e-8, **invalid** (reports 0.375 MiB GB, true 0.5 MiB) | 1.8260e-8, valid |
| 1, 4 MiB | 1.5488e-8 | same, valid | same, valid |

- The `var` join path under-counts the GlobalBuffer reservation of at least one mapping.
- Independent ENERGY|LATENCY FFM misses valid mappings under capacity pressure: 1.8202e-8 is valid
  at 0.25 MiB (hence also at 0.375 MiB), but independent FFM returns 1.8361e-8 at both capacities.
- The `jobs` fix (54a7c6ff) does not change the independent result at 0.375 MiB.
- At small scale (64,128,256) all three agree and every pick is valid; `push` took 173 s vs 214 s for `var`.

## Locating the independent-FFM loss (0.25 MiB, ENERGY|LATENCY, `AF_ABL_KEEP`)

| memories kept fully tracked | best EDP |
|---|---|
| none (default: LocalBuffer and MainMemory "big enough", Register pmapping-only) | 1.8361e-8 |
| Register | 1.8361e-8 |
| LocalBuffer | **1.8202e-8** |
| LocalBuffer, Register | **1.8202e-8** |

Dropping LocalBuffer through the "big enough to hold every tensor" proof loses the valid 1.8202e-8 mapping.
The mechanism is not yet known: tag1 adds energy and latency across Einsums, so the extra LocalBuffer
Pareto dimension should not matter if the proof were exact.

## The invalid 0.375 MiB pick is not caused by sharing

Running the `var` configuration directly at 0.375 MiB (the join checks the real capacity at every step)
returns the same row: reported GB 0.375 MiB, EDP 1.8105e-8, and re-evaluation fails at 0.375 MiB. The row's
reported energy (2.5087e-4) also differs from the re-evaluated energy of its reconstructed mapping
(2.4992e-4), so either the RESOURCE_USAGE path under-counts or the row is reconstructed into a different mapping.
