# Finite-target capacity-event enumeration

Reference implementation revision: `46733378`. Both measured backends use the
source committed alongside these records. `implementation_sha256.json` identifies
the final core sources. Reports were captured before committing: their `commit`
field therefore names the parent revision, and their tracked diff omits the
then-untracked `target_enumeration.py`. Use the source manifest and this commit's
files together to reproduce the changed implementation.

The baseline remains a shared capacity search, with each target's Tile enumeration
performed separately and the previous exact Pareto request cache enabled (8 MiB).
Events use live target cohorts and disable both prefix/Pareto execution caches.
Normal symbolic/model preparation caching is enabled in both. This comparison
does not measure independent full FFM searches at every configuration.

## Results and validation

`comparison.json` checks complete numeric-frontier hashes and Mapping validation
before calculating ratios. All four GLU pairs match, including every repeat.
NVDLA capacities span 1/32--1/4 MiB; TPU capacities span 1/4--4 MiB, log spaced.
Bandwidth is fixed. K=16 averages two warm runs per backend; K=64 has only one
warm run. Each process also records its first full search as cold, following a
tiny Matmul warmup. Wall times include generation and Join, exclude final query
extraction/re-evaluation, and are unprofiled. Processes run sequentially, with
one worker and numerical threads fixed to one; see `environment.json`.

| Case | K | Reference warm | Events warm | Ratio |
| --- | ---: | ---: | ---: | ---: |
| GLU/NVDLA | 16 | 6.175 s | 5.250 s | 1.176x |
| GLU/NVDLA | 64 | 9.937 s | 9.854 s | 1.008x |
| GLU/TPU v4i | 16 | 35.767 s | 19.785 s | 1.808x |
| GLU/TPU v4i | 64 | 89.033 s | 35.946 s | 2.477x |

NVDLA K=64 is effectively unchanged. These preliminary local observations do not
establish stable server speedups. Peak RSS includes validation and is not an
algorithmic memory bound. State byte counters exclude transient arrays, hash keys,
model objects and the final membership table.

`controlled.json` instruments actual expansion, padding and Pareto helpers for
K=2/4/8/16/32/64 with fixed bounds and two consecutive fallbacks, in three rotated
method-order repetitions. Every target is checked against plain enumeration,
including union dtype. At K=64, expansion calls fall 186 -> 24, expanded rows
11,102 -> 2,358, and padding calls 622 -> 142. These are executed batch operations,
not unique full-Mapping nodes. This controlled template does not call numerical
Pareto; the real GLU searches do.

`counter_grid_{independent,events}.json` compares the historical Matmul chain
(2,4,8), NVDLA, 64/128 bytes, latency scales 1/32/256. Both produce 49 generated
rows and the same 11-row final numerical frontier, and all six picks re-evaluate.
`counter_grid_pre_fix_events.json` is an explicitly **rejected diagnostic**, not
a valid speed measurement: the first implementation lost float64 promotion from
empty target arrays and produced 43/12 rows. Its selected best EDPs still matched;
this is why full frontiers and dtype checks are required. `dtype_regression.json`
records before/fixed source identification and hashes. The corrected implementation
was rerun for all four GLU event measurements and the controlled experiment.

`regression.txt` records 255 passing research/Streaming tests. This evidence is
limited to the tested input templates and existing conservative Fusion space.
The new backend retains K membership columns, serves only declared target
capacities, and does not implement continuous parameter regions, a Fusion Copy
Contract or a global memory budget. Event-cohort execution also avoids repeated
per-target formula logging; the total timing benefit includes this reduced
diagnostic/preparation work.

## Reproduction

From the repository root, using the dependency versions in `environment.json`:

```sh
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
python -m pytest -q research/tracking_audit research/streaming_join --disable-warnings
python research/tracking_audit/benchmark_target_scaling.py --output /tmp/controlled.json
python research/tracking_audit/benchmark_generation_scaling.py --repo . --output-dir /tmp/independent --counts 16 --repeats 3 --target-mode independent --pareto-bytes 8388608
python research/tracking_audit/benchmark_generation_scaling.py --repo . --output-dir /tmp/events --counts 16 --repeats 3 --target-mode events
python research/tracking_audit/benchmark_generation_scaling.py --repo . --output-dir /tmp/independent --counts 64 --repeats 2 --target-mode independent --pareto-bytes 8388608
python research/tracking_audit/benchmark_generation_scaling.py --repo . --output-dir /tmp/events --counts 64 --repeats 2 --target-mode events
python research/tracking_audit/summarize_generation_scaling.py --reference /tmp/independent --changed /tmp/events --output /tmp/comparison.json
python research/tracking_audit/benchmark_symbolic_generation.py --repo . --workload matmuls --arch nvdla --params 2,4,8 --caps 0.00006103515625,0.0001220703125 --factors 1,32,256 --repeats 2 --target-mode events --output /tmp/counter-events.json
```

Run the last command again with `--target-mode independent --pareto-bytes 8388608`
and a different output path for the counter-grid oracle. Correctness comparison
uses `summarize_generation_scaling.compare()` on the two report objects.

Report JSON formatting compacts flat numerical arrays without changing values.
No local log paths are required to reconstruct the saved numeric comparisons.
