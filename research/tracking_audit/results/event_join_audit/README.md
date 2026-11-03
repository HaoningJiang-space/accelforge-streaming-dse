# Event enumerator accounting and NVDLA Join audit

Both backends use `326999a6` plus the accounting fixes committed with this record.
`source_sha256.json` pins the changed production, benchmark and test files. The
benchmark was run before committing, so its parent `commit` field is `326999a6`.
The patch changes accounting and removes an uninitialized-mask exception; it does
not change the Pareto masks, capacity membership or Fusion policy.

## Correctness regressions

- Numerical Pareto keep rates now divide by the original row count in both paths,
  including when the reference obtains the mask from its exact request cache.
- The no-objective collapse also records its reduction; 144-to-1 must report 1/144.
- An unbounded first objective previously accessed `valid` before assignment.
  Constraint keep rates now measure the whole operation rather than its last mask.
- A deferred min-usage fallback that retained every partial candidate previously
  could report a zero keep rate. Its regression checks the retained complete rows
  and the product of logged rates.

`regression.txt`: 266 passing research/Streaming tests. `hash17.txt` and `hash71.txt`:
nine synthetic differential cases each in separate Python processes. The three RNG
seeds are 7/813/2603. Objectives, symbol order and targets are shuffled; constraint
reordering may legitimately change the answer, so each program is compared with
independent enumeration of that same program. The real-template tests also compare
keep-rate dictionaries and total-count estimates. These checks are relative to the
existing reference semantics, not full physical Mapping-space optimality proofs.

## Experiment

GLU (64,128,256), NVDLA, 64 log-spaced capacities from 1/32 to 1/4 MiB, fixed
bandwidth, unrestricted template count with the existing conservative Fusion
filter. Local Darwin arm64, Python 3.12.14, NumPy 2.3.5, one worker and numerical
thread, hash seed 0. Other dependency versions match the preceding
`target_enumeration/environment.json` experiment.

The reference is **already a shared full search** with independent target Tile
enumerations and an 8 MiB exact Pareto request cache. Events disable both prefix
and Pareto request caches. Normal symbolic/model caches are enabled in both.
After one full case warmup per method, the benchmark alternates execution order
over five pairs in the same process. Model caches remain warm. A further five
alternating pairs replay copies of the saved pre-Join inputs without generation.
Final query extraction, re-evaluation, snapshot copying and fingerprinting are
outside all reported search timers. The total is the sum of separately measured
generation and Join phases. This instrumented experiment does not time the added
fingerprinting/copying work as end-to-end application work.

| Median over five runs | Reference | Events |
| --- | ---: | ---: |
| Generation | 7.761 s | 4.247 s |
| Join after generation | 2.091 s | 2.026 s |
| Generation + Join | 9.898 s | 6.223 s |
| Join-only replay | 1.995 s | 1.987 s |

Median search ratio: **1.590x**. Medians of phases need not sum to the median total.
Generation/Join samples and replay samples are all saved, including replay
outliers. The earlier 4.49 s Join was not reproduced; without its input snapshot,
this does not establish exactly what caused that single timing. No general
speedup, repeated-fresh-process result or remote scaling claim is made.

All ten newly generated inputs have one common fingerprint, covering 197 groups,
2,943 rows, schema/dtypes, numeric data including row order, normalized template
provenance, indices, compatibility fields, count estimates and Pandas block layout.
The replay copies share a second common fingerprint: deep copying consolidates
blocks in 196 groups, with all other recorded fields unchanged. A replay therefore
does not retain the original fragmented layout; this distinction is explicit in
the record. Every result has the same 49-row numeric frontier, also equal to the
archived `326999a6` NVDLA K=64 frontier. All 64 target picks per method re-evaluate.

Separate timer-instrumented replays are diagnostic: each executes 144 pair joins
and 157 DataFrame Pareto calls. DataFrame Pareto takes 0.409/0.400 s; total profiled
Join takes 2.303/1.982 s. Nested inclusive times must not be summed. Uninstrumented
work remains in the parents' exclusive remainder; these counters are not dominance
comparison counts and do not isolate the effect of 64 membership columns.

## Files and reproduction

`alternating.json` contains raw times, inputs, profiles, final numeric values and
validated picks; `summary.json` records the strict equality checks and medians.
Repeated input schemas, block layouts and compatibility metadata are losslessly
interned under `input_metadata_tables`: for a group, replace `schema_id`, `blocks_id`
and `compatibility_id` with the corresponding table values under the original
field names before recomputing its input hash. Packing was checked by reconstructing
the original full JSON object and comparing it exactly. Hashes are diagnostic
fingerprints, not a proof of complete Fusion boundary sufficiency.

```sh
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
python research/tracking_audit/benchmark_event_join.py --output /tmp/event-join.json --repeats 5
python -m pytest -q research/tracking_audit research/streaming_join --disable-warnings
PYTHONHASHSEED=17 python -m pytest -q research/tracking_audit/test_target_enumeration.py -k 'deterministic_small_space_fuzz or non_nested_history' --disable-warnings
PYTHONHASHSEED=71 python -m pytest -q research/tracking_audit/test_target_enumeration.py -k 'deterministic_small_space_fuzz or non_nested_history' --disable-warnings
```

This audit does not implement compressed membership objectives, continuous regions,
a Fusion Copy Contract or a global Frontier memory budget. It preserves separate
evidence for search semantics, reduced work and measured execution time.
