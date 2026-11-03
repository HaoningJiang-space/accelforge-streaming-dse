# Generation scaling and exact Pareto request reuse

Reference checkout: `6a4f486d`. Changed source is committed with these records;
`implementation_sha256.json` fingerprints the core source files. Runs were made
before committing, so changed reports contain the reference HEAD plus a tracked-file
diff. That diff alone omits the then-untracked `enumeration_pareto.py`; use the
committed source and fingerprint manifest to reproduce the changed implementation.

All searches use one worker, fixed bandwidth, prefix reuse disabled, and the same
conservative Fusion filter. The environment is recorded in `environment.json`.
Capacities are log-spaced with fixed endpoints; configuration and full canonical
numeric frontiers, including target exclusions, are in each raw JSON report.
Mapping reconstruction/re-evaluation occurs outside the search timer.

- `phase_reference/` and `phase_changed/`: K=2,4,8,16 for both architectures,
  phase timers enabled, one cold and one warm search. Changed enables both model
  preparation reuse and an 8 MiB per-template Pareto payload cache.
- `phase_comparison.json`: exact-frontier validation and timings for those pairs.
- `profile_reference_nvdla_k16.json`: selected functions from a separate cProfile
  warm run; cumulative timings overlap and must not be used as wall-time speedups.
- `unprofiled_baseline/`, `unprofiled_model/`, `unprofiled_combined/`: K=16, each in
  a fresh process, one cold and two warm searches. Model-only disables Pareto reuse;
  combined enables it. `unprofiled_comparison.json` separates those effects.
- `regression.txt`: research/Streaming regression outcome, including the equal-
  metrics Fusion ablation regression. No new full Fusion ablation was run here.

Example from the repository root, using a Python environment matching the recorded
dependencies (the driver sets hash seed and numerical thread limits in children):

```sh
PYTHONPATH=. python research/tracking_audit/benchmark_generation_scaling.py \
  --repo /path/to/reference-checkout --output-dir /tmp/generation-reference \
  --counts 2,4,8,16 --arches nvdla,tpu_v4i --repeats 2 --phases
PYTHONPATH=. python research/tracking_audit/benchmark_generation_scaling.py \
  --repo "$PWD" --output-dir /tmp/generation-changed \
  --counts 2,4,8,16 --arches nvdla,tpu_v4i --repeats 2 --phases \
  --pareto-bytes 8388608
python research/tracking_audit/summarize_generation_scaling.py \
  --reference /tmp/generation-reference --changed /tmp/generation-changed \
  --output /tmp/generation-comparison.json
```

For unprofiled K=16 ablations, omit `--phases`, use `--counts 16 --repeats 3`, and
run the changed checkout with `--pareto-bytes 0` then `8388608` in separate processes.
Run benchmarks sequentially. First-case timings include cold case-specific caches
after a tiny Matmul warmup; they are not cold OS-cache measurements. Warm means the
mean of repeats 1 and 2, not multiple independent process repetitions.

The profiler, K curve and unprofiled runs are distinct experiments; do not combine
their timing components or multiply these shared-search improvements by historical
shared-versus-independent FFM ratios. These results do not remove the repeated
per-target constraint processing or establish event-driven enumeration complexity.
