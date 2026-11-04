# Prefix sharing experiment: measured duplication, but no speedup yet

Base commit `9638448d`. These are local experiments on the two heaviest MatMul
NVDLA templates in the six-template family, not production mapper changes.
Architecture bounds, objectives, exact arithmetic and FFM selection policy match
[the six-template experiment](../parametric_operator/README.md).

## Intrusive duplication profile

The [profiler](../../profile_parametric_factorization.py) records the highest
aggregate live row count at each symbol depth, retains those arrays, and only
then computes distinct full prefix rows, separating dtypes. This is a count of
row occurrences across states, not process RSS, bytes saved, or a count of
independent mappings. Formula-input counts distinguish formula, symbol order,
min/max padding direction, exactness and dtype. Profiling changes memory use and
adds substantial work, so its timing must not be used for a speedup claim.

| Canonical template index | Peak live rows | Distinct prefixes at that peak | Row-occurrence ratio | Formula rows requested | Distinct inputs across formula contexts |
|---:|---:|---:|---:|---:|---:|
| 1 | 715,873 | 2,496 | 286.8 | 1,095,955 | 12,270 |
| 3 | 859,854 | 2,970 | 289.5 | 1,258,975 | 14,697 |

Distinct formula inputs are summed *within each execution context*, not globally
across different formulas. The profile counts mask-result payload bytes and bytes
passed into merge hashing, but these are cumulative logical byte volumes, not
hardware traffic or a measured peak. [Raw profile](profile.json).

## Shared formula values experiment

[SharedEvaluationRegions](../../factorized_region_experiment.py) interns exact
prefix rows as IDs and caches objective results by the full evaluation context.
It preserves independent per-region ordered arrays, decisions and Pareto history;
it **does not** share the expansion operation, replace region arrays with IDs,
or implement the requested full CandidatePool/DAG state representation. Thus
it tests formula sharing separately and must not be described as a completed DAG.
The Python implementation is deliberately experimental, without a memory budget
or a general correctness guarantee for arbitrary FFM expressions.

Three fresh processes per method and template, one numeric thread, rotated order
`baseline, shared, shared, baseline, baseline, shared`; measured interval is
`RegionEnumerator.build()` only, excluding template preparation and query costs.
Every run has an identical ordered-leaf fingerprint, including boxes, dtype,
rows and Pareto history. [Raw measurements and source hashes](summary.json).

| Template | Original build median | Shared values median | Requested → evaluated formula rows |
|---:|---:|---:|---:|
| 1 | 2.618 s | 3.515 s | 1,095,955 → 12,270 |
| 3 | 2.900 s | 3.885 s | 1,258,975 → 14,697 |

The prototype is slower by roughly 34% on both templates. Per-row Python ID
lookup and constructing arrays remain; reduced numerical evaluations alone do
not remove the main state/guard work. Process RSS ranges overlap; no memory
improvement is established. The source of the extra time is an inference from
the implementation, not a detailed CPU attribution.

## Correctness and limits

The tests compare exact region boxes, row order, dtype and history against the
original interpreter for both templates; the complete six-template test compares
all 1,382 joint-cell representatives and their terminal frontiers. This is
relative to the existing FFM policy and its previously audited family; it is not
a proof for arbitrary workloads, Fusion or physical mapping completeness. The
instrumentation itself has an independent result-preservation test. Test results
are recorded in [regression.txt](regression.txt): five new tests pass. The
[existing parameterized-template and operator tests](existing_regression.txt)
also pass (40 tests); this is not a new full-repository test run.

Reproduce in a dedicated environment, running each process serially:

```sh
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
python -m research.tracking_audit.profile_parametric_factorization --formula-distinct --output /tmp/profile.json
for template in 1 3; do
  for entry in baseline:1 shared:1 shared:2 baseline:2 baseline:3 shared:3; do
    mode=${entry%:*}; repeat=${entry#*:}
    python -m research.tracking_audit.benchmark_factorized_region --template "$template" --mode "$mode" --output "/tmp/${template}_${mode}_${repeat}.json"
  done
done
python -m pytest -q --disable-warnings research/tracking_audit/test_factorized_region_experiment.py
```

The next implementation question remains open: whether a vectorized or compiled
shared prefix pool and indexed region sets can eliminate repeated allocation and
set operations without changing ordered fallback/Pareto semantics. This result
alone does not support a decision to replace the existing backend.
