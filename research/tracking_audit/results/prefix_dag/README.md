# Factorized prefix pool: less expansion, slower than the existing cache

Base `5e206e34`; this is an experimental **single-template** backend, not the
default FFM mapper, a complete six-template search, or a fused-graph search.
It tests the two heavy 256x256 NVDLA MatMul templates previously profiled as
indices 1 and 3. Their [canonical template identities](template_identity.json)
were checked against the previous six-template experiment.

## What changed

[FactorizedPrefixRegions](../../factorized_prefix_dag.py) keeps one unique
numeric prefix pool per symbol depth. Regions hold ordered `uint32` IDs into
that pool, their parameter-box Guards and separate Pareto histories. At a new
symbol, all live unique parents are expanded together once; temporary
parent-to-child edges reconstruct each region's original ordered expansion.
Formula evaluation can share the current pool, while fallback and Pareto remain
region-local. States merge only when their ordered IDs **and** history match.

This is a **layer-wise prefix pool with temporary edges**, not a persistent,
fully factorized DAG. Per-region ID vectors and Guard partitions are still
materialized, and the backend reconstructs numeric leaf arrays for the existing
query interface. It does not eliminate the number of live regional state rows,
region splits or Pareto calls. Unsupported object-valued pools, state-budget
excess and other unsupported conditions fail rather than discard work.

## Work and memory

Work counts below are actual work, not the 287x row-occurrence ratio reported by
the earlier profile. For cached FFM, the expansion count is its cache misses
across the 256-query sequence. For region/DAG it is the whole offline build.

| Template | Original region expanded rows | Factorized pool expanded rows | Existing cache expanded rows | Original peak region payload | ID-vector peak payload | Peak numeric pool payload |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 44,583 | 3,642 | 6,153 | 28,634,920 B | 2,863,492 B | 112,320 B |
| 3 | 40,880 | 4,079 | 5,456 | 34,394,160 B | 3,439,416 B | 118,800 B |

The ID-vector payload is one tenth of the original full-row region payload;
the numeric pool and temporary arrays are additional. These are selected NumPy
payload measurements, **not** a 10x process-RSS reduction. Python objects,
boxes, formula arrays and temporary buffers are not fully accounted for.
The maxima may occur at different points and must not be summed as a measured
simultaneous peak.

The peak number of region-held row/ID occurrences remains **715,873** and
**859,854**, respectively; peak box counts remain **2,038** and **1,913**.
Prefix Pareto calls remain **78** and **104**. Therefore this implementation
shares values and expansion, but does not remove the repeated region-level
selection and dominance work.

## Build plus 256 new architecture queries

Each method runs in three independent, serial processes, rotating order. One
worker, one numeric thread, same seed and JIT warmup. All three methods select
the same template structurally and prepare just its symbolic model; preparation,
offline compilation where applicable, queries and best-Mapping reconstruction
are timed. Query points are generated after the region/DAG compilation. Cache
baseline uses the existing `EnumerationReuse` and performs the original FFM
per-target enumeration, cost and Pareto. Validation and result serialization
are outside all timers.

| Template | Original region | Factorized pool | Prepared FFM + existing cache |
|---:|---:|---:|---:|
| 1 | 3.171 s | 3.041 s | **1.917 s** |
| 3 | 3.392 s | 3.250 s | **1.994 s** |

Values are three-run medians on the local machine. The factorized prototype is
about **1.59x** and **1.63x** as slow as the existing cache at 256 queries,
respectively. It is faster than the old region interpreter in this run, but
has not repaid preprocessing against the cache at any reported checkpoint up
to 256. Do not extrapolate a later break-even or multiply these numbers by
previous cross-capacity results.

Median process peak RSS, including Python, models, query state and temporary
allocations, is 0.330 / 0.265 / 0.262 GiB for template 1 and 0.339 / 0.267 /
0.263 GiB for template 3, in original / factorized / cached order. These are
process high-water marks, not isolated region-state memory. Full repeats,
checkpoints, operation counts and source hashes are in [summary.json](summary.json)
and the 18 raw JSON runs in this directory.

## Correctness and limitations

For **every one of 256 queries, every method and every repeat**, the summary
checks canonical candidate arrays including dtype and all numeric local frontier
rows. Eight selected Mapping reconstructions per run are independently
re-evaluated on the requested target after timing; these 144 validations are
instances, not necessarily 144 different Mappings. Tests compare every final
region, ordered Tile row, dtype, Pareto history and local frontier with the
original interpreter for both heavy templates. They also cover ordered fallback,
the noncontiguous 128-capacity historical counterexample, loop limits, shuffled
symbol/constraint order and explicit budget failures. Six separately prepared
physical architectures per template check target candidate/frontier equality.
[regression.txt](regression.txt) reports targeted results, not a full-repository
run.

The evidence supports the hypothesis that repeated **numeric prefix data** and
expansion exist. It does not establish that an optimized persistent DAG would
beat the cache, or that arbitrary FFM programs and Fusion boundaries can use
this state equivalence. The next decision should be based on whether the
remaining region split/mask/Pareto work can be eliminated without changing the
ordered policy, and on a realistic full-search workload; no new speedup is
claimed here.

## Reproduce

```sh
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
out=/tmp/prefix-dag-results
mkdir -p "$out"
for template in 1 3; do
  for entry in region:1 dag:1 cached:1 dag:2 cached:2 region:2 cached:3 region:3 dag:3; do
    mode=${entry%:*}; repeat=${entry#*:}
    python -m research.tracking_audit.benchmark_prefix_dag --template "$template" --mode "$mode" --queries 256 --output "$out/${template}_${mode}_${repeat}.json"
  done
done
python -m research.tracking_audit.summarize_prefix_dag "$out"
python -m pytest -q --disable-warnings research/tracking_audit/test_factorized_prefix_dag.py research/tracking_audit/test_parametric_template.py research/tracking_audit/test_parametric_operator.py research/tracking_audit/test_target_enumeration.py research/tracking_audit/test_factorized_region_experiment.py research/tracking_audit/test_enumeration_prefix.py
```
