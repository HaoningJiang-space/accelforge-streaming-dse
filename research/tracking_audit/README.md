# Capacity-tracking audit

This is the current experiment entry point for fixed-bandwidth GlobalBuffer capacity
reuse on tag 1.0 (GLU, a matmul chain and MobileNet; tpu_v4i and nvdla). The three paths are `indep` (one search per capacity), `var`
(shared generation, selective resource tracking at Join), and `push` (also eliminate
provably unnecessary fixed resources during generation).

## Current status and limits

### Direct membership output and early target-intersection filtering

Bitset mode now builds allowed-target words directly from final Event cohorts or
independent-reference parts. It no longer creates the NxK Boolean exclusion matrix
before packing. The original enumerator API still defaults to Boolean exclusions;
`membership_format='packed'` is an explicit output choice. Candidate enumeration,
ordered fallback, empty-target dtype promotion and target membership are unchanged.
Both original target order and sorted column-label order are covered, including
multiple words and duplicate target IDs inside the enumeration API.

`AF_MEMBERSHIP_JOIN=early` is an opt-in post-`pd.merge` filter. It intersects target
words before numeric/resource composition and removes rows with no allowed target.
The default remains `late`. It does **not** avoid the initial Pair materialization.
Fully target-dead blocks take the reference composition path before being emptied:
directly reducing an empty Pandas frame can change dtype and subsequent concat
arithmetic. Arbitrary row callbacks are rejected by the early mode. Actual row
work is measured separately from legacy Mapping-count estimates.

The initial 64-target measurements show why a complex pre-Join index is deferred:

| Input | Compatibility-matched pairs | Empty intersections | Fraction |
| --- | ---: | ---: | ---: |
| GLU / NVDLA | 20,527 | 0 | 0% |
| MatMul chain / NVDLA | 4,790 | 0 | 0% |
| MobileNet / NVDLA | 2,310,624 | 1,504 | 0.0651% |
| GLU / TPU v4i | 4,302 | 24 | 0.5579% |
| Historical 64–128-byte Matmul case | 217 | 129 | 59.45% |

These count actual materialized compatible rows over a complete late-filter Join,
not hypothetical Cartesian products. In the small counterexample, early filtering
reduces rows entering Reservation composition from 217 to 88, but Join is only
about 20 ms and shows no meaningful speedup. The larger cases have little empty
intersection work to eliminate. All initial generated candidates have one
contiguous run of allowed sampled targets; this is evidence about a finite grid,
not a certificate for capacities between those targets.

K=16/64/256/1024 sweeps on GLU and the small counterexample still show one sampled
interval per generated row. The constructor microbenchmark at K=1024 improves
176.8 -> 2.95 ms and 36.64 -> 4.14 MiB peak traced allocation (synthetic 32,768 rows).
This is not RSS or whole-search memory. The warm full-search ablations show no
consistent speedup; MobileNet Join replay is slower with early filtering. The
default therefore remains late filtering. All 704 ablation selections re-evaluate.

**325 research/Streaming tests pass.** [Measurements, limitations and reproduction](results/membership_pushdown/).

### Packed target membership (finite targets, opt-in)

`AF_CAPACITY_MEMBERSHIP=bitset` replaces K exclusion-count objective columns with
`ceil(K/64)` uint64 words. Join intersects allowed-target bits. Within the same
FFM output boundary, a candidate can dominate another only if its allowed targets
are a superset and its numeric cost/resource components are no worse. Words never
enter scalar-min Pareto or floating-point cost arrays. Target membership and
physical capacity feasibility remain separate checks.

The reference `counts` mode remains the default. A `boolean` ablation clamps
positive exclusion counts to one but retains K scalar columns and the old Pareto
backend. This separates dropping irrelevant positive-count distinctions from the
packed representation and CPU kernel. Both new modes require zero tolerance.
Packed schemas carry their target labels; missing/mixed schemas fail, and the
scalar incremental/partitioned Streaming reducers fall back to membership-aware
Pareto. The resource-only breakpoint builder now rejects target-policy columns:
it cannot certify non-nested candidate membership at arbitrary capacities.

Three rotated warm repetitions per method, one local worker, fixed bandwidth:

| Case | Count search | Boolean search | Bitset search | Count / bitset |
| --- | ---: | ---: | ---: | ---: |
| NVDLA GLU, K=16 | 4.822 s | 5.207 s | 3.999 s | 1.21x |
| NVDLA GLU, K=64 | 6.058 s | 6.316 s | 4.084 s | 1.48x |
| TPU v4i GLU, K=64 | 23.554 s | 23.537 s | 18.983 s | 1.24x |

Every method already uses the Event enumerator; these are **additional shared-search
improvements**, not comparisons to per-architecture FFM. All 36 runs match the
Boolean-projected numerical frontier and every target's cost/resource frontier.
All 432 final selected mappings re-evaluate at their target capacities. TPU's raw
frontier has 10 rows in counts and 8 in Boolean/bitset; the count tables themselves
are not claimed identical. The 64-target membership array payload shrinks 32x;
this is not an RSS reduction claim. Tests cover 65/129-target multiword dominance,
bit 63, provenance, real Join/Streaming and a capacity/bandwidth grid.

At `3b1b09b4`, the enumerator still built an NxK exclusion matrix; the direct-output
follow-up above removes it for bitset mode. Target labels still occupy O(K) schema
space. This does not make the whole search independent of K, add
continuous parameter regions, fix the conservative Fusion filter, or impose a
global memory budget. The window skyline is CPU-only and quadratic in the worst
case. [Algorithm contract, raw measurements and reproduction](results/packed_membership/).

### Event audit: keep-rate fixes and repeated NVDLA Join measurements

The review of `326999a6` correctly identified a Pareto accounting error in both
enumerators: the remaining row count was used as the denominator, making the
reported keep rate 100%. Both now use the input row count, including the
no-objective case that reduces all rows to one. The numerical pruning masks are
unchanged. A 144-to-1 regression verifies the rate is 1/144, including the cached
reference path.

The same audit also found an actual exception in the reference enumerator: a first
objective with neither bound accessed an uninitialized `valid` mask. Constraint
accounting now uses rows-after / rows-before for the complete operation. This also
fixes deferred min-usage fallback being reported as dropping all candidates when
it had actually kept them. These are estimate/diagnostic corrections; the new
tests include candidate checks as well as rates. Historical keep-rate-derived
Mapping count estimates must not be used as measured search-work counts.

For NVDLA GLU 64,128,256, K=64, a new local single-worker comparison warms both
backends on the full case and then alternates their order over **five runs each**.
The baseline has the previous 8 MiB Pareto cache; events have no execution cache.
All rows below are medians, measured without profiling:

| Phase | Independent-target shared search | Event shared search |
| --- | ---: | ---: |
| Generation | 7.761 s | 4.247 s |
| Join after generation | 2.091 s | 2.026 s |
| Generation + Join | 9.898 s | 6.223 s |
| Join replay from fixed input | 1.995 s | 1.987 s |

The total ratio is **1.59x** in this experiment (not a fresh-process/server claim).
All ten generated Join inputs have the same fingerprint: 197 compatibility groups,
2,943 rows, schemas/dtypes, numeric row order, normalized template provenance,
indices, compatibility fields, estimates and Pandas block layouts. Replays use a
deep copy of each method's saved input; the copy consolidates 196 groups' Pandas
blocks, so the replay layout is recorded separately. Only layout changes on copy;
the replay inputs are identical across methods. Copying and fingerprints are
outside timers. The final 49-row numerical frontier equals `326999a6`, and all
64 selected mappings per method re-evaluate.

The old 4.49-second event Join was **not reproduced**. Its single-run record lacks
these input fingerprints, so the cause cannot be retrospectively identified as
noise alone. Separate diagnostic Join profiles execute 144 pair joins and 157
DataFrame Pareto calls for each input, with roughly 0.40 s in DataFrame Pareto.
Inclusive/exclusive timers are not a count of dominance comparisons.

Validation: **266 research/Streaming tests pass**. Differential tests now cover
three random seeds, shuffled target/symbol/constraint orders, duplicates and empty
targets; each ordered program is checked against its own oracle. Nine synthetic
cases also pass separately under each of `PYTHONHASHSEED=17` and `71`. Real-template
checks compare keep rates and count estimates in addition to Tile dtype, values
and target membership. This completed the finite-target P0 audit; the packed
membership follow-up is reported above. Continuous parameter regions and the
Fusion Copy Contract remain separate work. [Records and reproduction](results/event_join_audit/).

### Capacity-event shared Tile enumeration

`AF_TARGET_ENUMERATION=events` selects a new **finite-target shared enumerator**.
The default remains `independent` for the reference path. This backend advances
live partial Tile states jointly; it does not run each target to completion and
then cache or union its intermediate results. Existing prefix/Pareto request caches
are not used by the event backend.

At the same symbol/objective position, a cohort holds an ordered candidate array,
its dtype, the previous Pareto goal sets, and the target IDs it serves. The symbol
schedule and active objectives are common at that program position. The backend:

1. Expands the next Tile symbol once per cohort and checks fused-loop limits.
2. Evaluates the original FFM partial resource bound once. Sorted attained values
   identify capacity thresholds at which the keep mask changes. It materializes
   one mask per attained event represented among the requested targets.
3. Splits target IDs by these masks **before** subsequent min-usage constraints.
   Every fallback sees the complete surviving candidate set of its cohort, never
   a union of candidates from targets with different histories.
4. Applies the original goal/coalescing/Pareto rules. Equal ordered arrays may
   merge only if dtype and Pareto history also agree. Keeping history matters
   because the original enumerator may skip a later Pareto based on earlier goals.
5. Builds the final union and the same per-target exclusion columns as before.

The invariant is: projecting the live state onto any requested target gives the
same ordered partial assignments and pruning history as that target's plain
enumeration at the same program position. Expansion and target-independent
constraints preserve it; the capacity partition implements the same comparison;
each ordered fallback then receives the same full input. Identical-state merging
preserves future operations. This is a conditional equivalence argument relative
to FFM's existing rules for a **fixed input template**, not a proof of full Fusion
Mapspace completeness or of the original pruning rules themselves.

The fast event partition preserves NumPy scalar-promotion semantics, including
float32 threshold rounding. Unsupported/nonfinite comparison forms use direct
per-target masks; a deferred comparison for one target does not disable checks for
others. Imperfect tiling, nonzero Pareto tolerance, fixed templates without symbols,
the mapspace-counting mode, and heterogeneous capacity formulas use the independent
backend. Unsupported mode selection raises an error; unexpected search errors are
not silently caught and rerun.

An implementation regression exposed another numerical contract: when a target
has no candidates, the reference's empty float64 array still participates in final
concatenation and promotes the union's Tile dtype. Initially, removing empty cohorts
lost that promotion. On the 64/128-byte Matmul grid the Tile values and selected
EDPs matched, but generated/frontier rows changed from 49/11 to 43/12. The backend
now preserves empty-target dtype promotion; the full numerical frontier is again
identical. Tests compare dtype as well as per-template Tile values and membership.
This retains the reference's numerical behavior, not a new byte-exact resource model.

This is **not yet a continuous-parameter solver**: it serves the declared capacity
targets and does not certify intervals for unseen queries. Its default output
retains K membership columns; bitset mode now constructs words directly from the
final cohorts without the NxK output mask. It does not add a Fusion Copy Contract, relax the
conservative copy filter, or provide a global memory budget. All cohort states are
currently resident. In the worst case every target has a distinct state; no general
sublinear-in-K runtime guarantee is claimed.

The controlled three-variable, two-consecutive-fallback experiment fixes symbol
bounds and the capacity range, checks each target against the plain enumerator,
and directly instruments the executed helpers (three rotated repetitions):

| K | Expansion calls: per-target / events | Expanded rows: per-target / events | Padding calls: per-target / events |
| ---: | ---: | ---: | ---: |
| 2 | 4 / 3 | 228 / 204 | 14 / 10 |
| 4 | 10 / 4 | 622 / 346 | 34 / 16 |
| 8 | 22 / 6 | 1,326 / 546 | 74 / 28 |
| 16 | 46 / 10 | 2,742 / 954 | 154 / 53 |
| 32 | 92 / 16 | 5,504 / 1,569 | 308 / 90 |
| 64 | 186 / 24 | 11,102 / 2,358 | 622 / 142 |

Expansion counts match the earlier exact-prefix-cache experiment, but this backend
also shares the subsequent constraint processing. The old prefix cache did not do
that. These are batch calls, executed partial-row expansions and padding calls,
not unique full-mapping nodes. This small template does not invoke numerical Pareto;
the real GLU tests/searches exercise that path and full output membership instead.

Reproduce with `benchmark_target_scaling.py --output FILE.json`. For full-search
runs use `benchmark_generation_scaling.py --repo CHECKOUT --output-dir DIR
--target-mode events`; compare to `--target-mode independent --pareto-bytes 8388608`
to include the previous strongest execution optimization in the baseline.
`Job.target_enumeration_stats` records actual cohort work and target-weighted
equivalents separately. Legacy per-target evaluation counts are not actual shared
work counts; state-array byte counters exclude scratch, keys, model objects and
the final membership table.

Corrected end-to-end measurements compare two **shared searches**, using the
same current code: independent target enumeration with the previous 8 MiB exact
Pareto cache, versus events with both execution caches disabled. Both include
the normal symbolic/model preparation improvements. Local arm64, one worker,
one numerical thread, hash seed 0, no phase timers or profiler, no template count
limit, conservative Fusion filtering retained. Each method/case runs in a fresh
process after a tiny Matmul warmup. K=16 has one cold and two warm runs; K=64 has
one cold and **one warm run only**, so its timing is preliminary. Warm K=16 values
are means. Search time includes generation and Join, excluding final query
extraction and Mapping re-evaluation.

| Case | K | Independent-target warm | Events warm | Ratio | Cold: independent / events |
| --- | ---: | ---: | ---: | ---: | ---: |
| GLU 64,128,256 / NVDLA | 16 | 6.17 s | 5.25 s | 1.18x | 11.46 / 10.63 s |
| GLU 64,128,256 / NVDLA | 64 | 9.94 s | 9.85 s | 1.01x | 16.24 / 13.15 s |
| GLU 256,512,1024 / TPU v4i | 16 | 35.77 s | 19.78 s | 1.81x | 58.59 / 49.39 s |
| GLU 256,512,1024 / TPU v4i | 64 | 89.03 s | 35.95 s | 2.48x | 111.12 / 54.19 s |

NVDLA K=64 shows essentially no measured end-to-end benefit despite less expansion
work. TPU's actual expansion calls grow from **2,215 to 2,443** between K=16 and
K=64, versus **23,844 to 95,556** in the reference. At K=64 its expanded rows fall
from **18,165,483 to 703,993**. Counters separately record weighted per-target
equivalents and verify they match the reference. These are executed partial-row
expansions, not unique Mapping counts. Savings include reduced repeated setup,
constraint evaluation and diagnostics; times do not isolate just expansion.
The event path emits one template summary instead of per-target formula logs.

For all four case/K pairs, all repeats match the complete sorted numerical
frontier, and all **160** selected capacity mappings per method re-evaluate.
The 64/128-byte Matmul grid adds six capacity/bandwidth picks and matches the
reference's complete 11-row frontier after the dtype fix. These checks establish
equivalence in the tested conservative Mapspace, not full Fusion completeness.
They cannot be multiplied by the historical eight-worker DSE speedup ratios.
Corrected records supersede all measurements of the pre-dtype-fix event backend.

Validation: **255 research/Streaming tests pass**, including 28 new event tests
covering ordered fallbacks, all-target Tile/dtype/membership comparisons,
real templates, float thresholds, empty branches, history-sensitive state merging
and reference fallbacks. Records, source fingerprints, commands and the rejected
dtype-regression record: [results/target_enumeration/](results/target_enumeration/).

### Generation profile: model preparation and repeated numerical Pareto requests

Reference: **6a4f486d**, after the formula-text optimization below. The next profile
finds two separate costs: repeated symbolic model preparation, and K-dependent
Pareto calls inside Tile enumeration. Join is a small part of the TPU case. The
new optional `--phases` instrumentation separates these costs; inclusive times
nest, while exclusive times subtract instrumented children and still include
uninstrumented helpers. cProfile records are diagnostic, not speed measurements.

Normally enabled changes reuse immutable projection parsing, projection evaluators
and identical `BuffetStats` maxima. Caches are keyed by expression content, not
mutable workloads, mappings or evaluated Tile arrays. Fresh relevance containers
and current Tile/shape arguments preserve ownership and numeric behavior. Entry
limits are 1,024 / 512 / 4,096 respectively; these are not global byte budgets.

An opt-in **`AF_ENUMERATION_PARETO_BYTES=8388608`** cache, local to each template,
reuses the original Pareto backend's positional keep mask only for identical
numeric bytes, dtype, shape, row/column order and goals, with zero tolerance.
It does not cache candidates or target membership. Each target still performs its
own ordered constraints and min-usage fallbacks. Approximate, nonfinite, unsupported
or oversized requests use the original path. The default is **0 (disabled)**;
prefix reuse also remains disabled. LRU eviction and a 1,024-entry limit bound
retained key/mask payload, not Python overhead, temporary allocations, Frontier
storage or whole-process RSS. Template completion releases the cache.

Local single-worker, single numerical thread, hash seed 0, fresh processes for each
case/K/version. Capacities are log-spaced over 1/32--1/4 MiB for GLU 64,128,256 @
NVDLA and 1/4--4 MiB for GLU 256,512,1024 @ TPU v4i; bandwidth is fixed. These are
**shared-search versus shared-search** comparisons, not independent FFM speedups.
The K curve has phase timers enabled, one cold and one warm run per case:

| K | NVDLA reference / changed warm | TPU reference / changed warm |
| ---: | ---: | ---: |
| 2 | 5.94 / 4.56 s | 23.83 / 18.44 s |
| 4 | 6.05 / 4.71 s | 29.23 / 22.69 s |
| 8 | 6.49 / 5.27 s | 37.07 / 27.07 s |
| 16 | 7.32 / 6.12 s | 49.38 / 37.09 s |

Separate **unprofiled** K=16 ablations use one cold and two warm searches in each
fresh process. Warm values below are means of the two warm runs, including
generation and Join, excluding query extraction and re-evaluation:

| Case | Reference | Model preparation only (normal path) | Model + opt-in Pareto reuse | Combined speedup |
| --- | ---: | ---: | ---: | ---: |
| NVDLA | 7.53 s | 5.96 s | 5.66 s | 1.33x |
| TPU v4i | 50.64 s | 45.69 s | 33.12 s | 1.53x |

Cold reference/model/combined times are 12.76 / 11.43 / 10.87 s for NVDLA and
83.70 / 67.67 / 56.79 s for TPU. Pareto reuse contributes a further 1.05x / 1.38x
over model preparation alone in these cases. All three methods and all repeats
have identical numeric frontiers, and all 32 final capacity picks per method
re-evaluate. Combined whole-process peak RSS, including validation, is 0.334 GiB
for NVDLA and 0.430 GiB for TPU. These are initial local measurements, not a memory
reduction claim or a repeated-process/server scaling result. Model preparation
also benefits independent FFM, so these gains cannot be multiplied by historical
DSE speedup ratios.

At TPU K=16, warm reuse analysis falls 6.96 -> 3.42 s, numerical enumeration
Pareto 12.89 -> 2.94 s, and iteration/rank columns 1.24 -> 0.49 s. Actual
target-template Pareto computations fall **4,713 -> 1,010**, and rows passed to
those computations **1,356,632 -> 284,034**. The maximum retained payload in one
template is 107,854 bytes. NVDLA computations fall 160 -> 26 with a maximum
40,157-byte payload. These count requests and input rows, not distinct search-tree
nodes or dominance comparisons. Key construction and lookup costs are included in
the total timer, but outside the `enumeration_pareto` phase (the actual backend).

All eight K/case pairs preserve the complete sorted numerical frontier across
versions and repeats; all 60 selected capacity mappings per version re-evaluate at
their target. This verifies execution equivalence in the existing conservative
Fusion Mapspace, not complete original Fusion coverage. Those cache-only changes
do **not** implement event-driven enumeration: constraint processing still grows
with K. The finite-target backend above additionally shares this constraint work;
neither implementation establishes a general parametric-search complexity bound.

Validation: **226 research/Streaming tests pass**, including exact mask ties/order,
dtype and tolerance guards, byte-budget eviction, consecutive min-usage fallbacks,
real GLU template Tile/membership equality, and projection mutation/precision checks.
The Fusion audit now has an additional regression requiring identical Pareto
metrics on its conservative and restored paths; historical mixed-metrics results
are qualified below rather than treated as a newly measured filter-only effect.

Records and reproduction: [results/generation_scaling/](results/generation_scaling/).
`benchmark_generation_scaling.py --repo CHECKOUT --output-dir DIR --phases
--pareto-bytes 0|8388608` runs the K curve sequentially in fresh processes.
`summarize_generation_scaling.py --reference DIR --changed DIR --output FILE.json`
rejects mismatched numeric frontiers, failed Mapping validation and cProfile timings.

### Exact prefix reuse experiment and formula-log overhead

On top of `66e074e4`, tile expansion is isolated as a pure operation. The optional
`AF_ENUMERATION_PREFIX_BYTES` cache reuses it only for identical ordered prefix
arrays (including dtype), symbol order and next symbol, within one template.
Each capacity still runs its own constraints, ordered min-usage fallbacks and
Pareto history. Cached arrays are read-only; an LRU limits retained key/array
payload, with oversized entries bypassed. This is **not** a process memory bound
or a single parametric search. The default is **0 (disabled)**.

The experiment exposed a cheaper-to-fix bottleneck: a warm GLU/NVDLA profile spent
about 5.14 s of the tile enumerator's 7.65 s formatting symbolic formula diagnostics,
versus 0.026 s in actual prefix expansion. These are cumulative **profiled** times,
not ordinary wall-time measurements. `SymbolicText` now renders immutable formulas
once per template and reuses the text across capacities; mutable Goal values are
always formatted from their current state. Diagnostic content and search semantics
are retained, and the two text caches are bounded to 512 entries each and released
with the template. This optimization is enabled normally.

Unprofiled local arm64 measurements, one worker, numeric threads=1, hash seed=0,
separate processes, tiny Matmul warmup followed by three full searches. Warm time is
the mean of runs 2 and 3, including generation and Join, excluding validation:

| GLU 64,128,256 @ NVDLA experiment | Reference warm | Changed warm | Finding |
| --- | ---: | ---: | --- |
| 3 capacities x 4 latency factors, prefix reuse only | 8.79 s | 8.99 s | No measured speedup |
| Same grid, formula-text reuse only | 8.79 s | 7.40 s | Initial 1.19x improvement |
| 16 capacities, fixed bandwidth, text reuse in both paths | 7.25 s | 7.25 s | Prefix reuse does not improve end-to-end time here |

For the 16-capacity case, actual expansion calls drop **2,432 -> 192**, and expanded
rows **194,998 -> 25,508**. The 8 MiB cache budget retains at most 373,776 payload
bytes in any one template. Whole-process peak RSS is 0.330 / 0.329 GiB. All three
repetitions have identical complete numeric frontiers (49 rows); all 16 selected
mappings re-evaluate. The 12-point grid similarly preserves its 104-row numeric
frontier and all picks. These timings are preliminary shared-search measurements,
not speedups against independent FFM or the server's eight-worker experiments.

The controlled three-symbol, two-fallback K sweep checks every target against plain
enumeration. It has fixed bounds and log-spaced targets, including infeasible ones:

| K | Reference expansion calls | Reused calls | Reference expanded rows | Reused rows |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 4 | 3 | 228 | 204 |
| 4 | 10 | 4 | 622 | 346 |
| 8 | 22 | 6 | 1,326 | 546 |
| 16 | 46 | 10 | 2,742 | 954 |
| 32 | 92 | 16 | 5,504 | 1,569 |
| 64 | 186 | 24 | 11,102 | 2,358 |

These count batch expansions and the rows they actually produce, not every symbolic
analysis operation, distinct search-tree nodes, or the whole Mapper's work. Their
sublinear growth on this template is not a general complexity guarantee. Capacity
checks and pruning still repeat with K. Next work must address that remaining work;
the prefix experiment alone does not complete P1 or establish an algorithmic DSE
speedup.

199 research/Streaming regression tests pass, including target reordering, empty
targets, two consecutive fallbacks, eviction/bypass, dtype/order preservation, and
real GLU templates' complete Tile arrays and membership matrices against cache-off
enumeration. An additional uncovered bug is fixed: initial Tile Shape expansion
called nonexistent `SymbolRelations.get_stride`; it now uses `get_tile_shape`, and
initial symbols receive bounds through their associated stride. A regression checks
both initial choices and target membership; this does not establish general
imperfect-tiling coverage.

Records: [results/enumeration_prefix/](results/enumeration_prefix/).
Use `benchmark_symbolic_generation.py --prefix-bytes 0|8388608 --output FILE.json`
for full-search comparisons; `--factors 1 --caps ...` selects capacity-only searches.
Use `PYTHONPATH=. python research/tracking_audit/benchmark_prefix_scaling.py
--output FILE.json` for the controlled K sweep. Set `PYTHONHASHSEED=0`,
`OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, and `NUMBA_NUM_THREADS=1` in both cases.

### Symbolic preparation optimization

Generation was the main cost in the latest grid runs. This change reuses unchanged
symbolic expressions instead of reconstructing their `Max`/`Min` nodes, shallow-copies
only mutable Objective state, compiles each objective once per template (shared by
that template's capacity targets), and removes two unused compiled dictionaries.
An LRU capped at 512 entries reuses identical component-latency maxima across
templates. Compiled-function dictionaries are released after each template. Target
enumeration, capacity membership, Pareto tolerance and numeric precision are unchanged.

The reference is **7e60a804**, which first fixes a correctness issue: completing a
constraint used to clear the dictionary returned by cached `partition_formula`,
changing later objectives/runs. A regression test reproduces the mutation; completed
constraints now discard only their local reference. The candidate disk-cache version
is bumped so candidates from before this correction are not reused.

Local arm64 measurements, Python 3.12.14, NumPy 2.3.5, Pandas 3.1.0, SymPy 1.14.0,
one worker, `PYTHONHASHSEED=0`, numerical-library threads limited to one. Each version
runs in a separate process after a tiny MatMul warmup, then performs the same full
shared search three times. Cold means the first case-specific search; warm is the
mean of the following two. No profiler is active. Times include generation and Join,
excluding query extraction, serialization and Mapping validation.

| Case | Grid points | Cold before / after | Warm before / after | Warm speedup |
| --- | ---: | ---: | ---: | ---: |
| GLU 64,128,256 @ nvdla | 12 | 29.74 / 23.35 s | 14.71 / 8.72 s | 1.69x |
| GLU 256,512,1024 @ tpu_v4i | 16 | 163.87 / 130.96 s | 92.25 / 58.12 s | 1.59x |

Both versions and all three repetitions have identical complete numeric frontiers
(SHA-256 checked, 104 rows on NVDLA and 24 on TPU). All 28 selected grid mappings
re-evaluate successfully, with identical EDPs before/after. Whole-process peak RSS
is 0.309 / 0.312 GiB on NVDLA and 0.394 / 0.389 GiB on TPU; these peaks include
validation. These are initial local results for shared search itself, not new
speedups versus independent FFM or measurements of the server's eight-worker setup.
The complete audit/Streaming regression suite passes: 171 tests.

Reproduce using [benchmark_symbolic_generation.py](benchmark_symbolic_generation.py),
with `--repo` selecting a checkout of 7e60a804 for the reference; omit it for the
current checkout. Set `PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
NUMBA_NUM_THREADS=1` in both processes. Defaults reproduce NVDLA; TPU arguments are
`--arch tpu_v4i --params 256,512,1024 --caps 0.25,0.375,1,4`. Pass a separate
`--output FILE.json` to each run. Numeric frontiers, timings and re-evaluated picks:
[results/symbolic_preparation/](results/symbolic_preparation/).

### Speedup versus the number of capacities after the coverage fix, commit `238511ee`

`sweep_capacity_count.sh` as before (K nested log-spaced capacities, two repeats, eight
workers). Records: [results/sweepK_238511ee/](results/sweepK_238511ee/). All twelve
runs exit 0. Speedup of push (var) over per-capacity search:

| Case | K=2 | K=4 | K=6 | K=16 | push seconds K=2 -> 16 |
| --- | --- | --- | --- | --- | --- |
| glu 256,512,1024 @ tpu_v4i | 1.59x (1.43x) | 2.77x (2.45x) | 3.70x (3.48x) | 5.99x (5.29x) | 34.0 -> 74.7 |
| glu 64,128,256 @ nvdla | 1.82x (1.57x) | 3.55x (3.13x) | 4.80x (4.19x) | 9.74x (9.25x) | 7.1 -> 10.2 |
| matmuls 3,256,256 @ nvdla | 1.61x (1.23x) | 3.03x (2.49x) | 3.78x (3.25x) | 5.73x (5.25x) | 4.6 -> 9.2 |

**This supersedes the `70df4847` sweep below** (15-17x at K=16), which ran before the
min_usage coverage fix and therefore without the guarantee that every target's
candidates are covered. With per-target enumeration the shared search is no longer
constant in K: templates with min-usage constraints are enumerated once per target,
so generation grows with K (GLU@tpu_v4i push 34 s at K=2, 75 s at K=16). The speedup
still grows with K but sublinearly. Removing this per-target repetition is the next
algorithmic step. The tpu K=16 run started at 238511ee; the server checkout was
updated to d3f2fee9 (symbolic-preparation reuse, identical fronts) while it ran.

### Cost of the unrepresentable-template filter

The saved `unrepresentable_gain.py --metrics ru` experiment compared conservative
ENERGY | LATENCY with restored RESOURCE_USAGE, and re-evaluated every row of the
latter as the mapping it rebuilds into. **This changes both the template filter and
the Pareto metrics**, so it does not isolate the filter's quality or runtime effect.
The script now applies `--metrics` to both searches and records both objective sets;
the equal-metrics large experiment has not been rerun. Historical records:
[results/unrepresentable_gain/](results/unrepresentable_gain/).

| Case | Skipped / templates | Restored front rows | Scored differently | Do not fit | Best rebuilt vs default |
| --- | --- | --- | --- | --- | --- |
| glu 64,128,256 @ nvdla, 1/4 MiB | FFH 6/48 | 47 | 0 | 0 | equal |
| glu 256,512,1024 @ tpu_v4i, 1/4 MiB | none | 537 | 0 | 47 | equal |
| same, 3/8 MiB | FFH 12/132, FFU 8/41 | 674 | 4 | 71 | 0.17% worse |
| same, 4 MiB | FFG 8/41, FFU 8/41 | 1031 | 50 | 0 | **1.18% better** |
| matmuls 3,256,256 @ tpu_v4i / nvdla | 0 / Matmul1 6/24 | 93 / 26 | 0 | 0 | equal |
| mobilenet 1 @ nvdla, 1/16 MiB | Depthwise1 22/126, PiecewiseA1 6/24 | 167 | 0 | 0 | equal |

At 4 MiB the better mapping (EDP 1.56018e-8 against 1.57857e-8) is scored exactly as
it rebuilds (`matches: true`), fits, and has only the usual FFH reuse shortfalls
([results/unrepresentable_gain/glu_tpu_4_best_row.txt](results/unrepresentable_gain/glu_tpu_4_best_row.txt)):
this establishes the existence of a feasible mapping better than the recorded
default pick. The 1.18% difference cannot yet be attributed solely to template
filtering because the metrics also changed. At 3/8 MiB the restored search prunes
with some wrong scores, so the ablation is not a valid superset reference. The next
Fusion experiment must compare equal metrics, retain the winning template/copy
provenance, and verify whether a matching-copy boundary contract admits the better
mapping while rejecting the historical invalid combinations.

### Mapping identity is not stable across runs

Audits now record `mapping_id` (`common.mapping_identity`), `tied_optima` and
`optimal_mappings`, and `best_row` breaks final EDP ties by the smallest identity. On
`matmuls(2,4,8)@nvdla` (64/128 bytes x scales 1/32/256, two repeats) the picks at 128
bytes still differ between runs (identities e3a7c7, 0bb805, 9b2a24) with equal EDP and
a single tied row in each final front: different equal-cost mappings survive earlier
Pareto pruning depending on order. A count of distinct optimal mappings is therefore
not well defined when equal-cost mappings exist. A robust switch measure is to
re-evaluate each configuration's pick at the others and count where it stops being
optimal; this is not implemented yet.

### Capacity x bandwidth grid, commit `9be3f809`

`grid_audit.py`: one search per grid point (`indep`) against one shared search at the
largest capacity with GlobalBuffer kept variable, per-target capacity enumeration and
one latency objective per scale (`shared`). Two repeats in rotated order after a
warmup, eight workers, two cases at a time under `run_capped.sh 24 7200`. Records:
[results/grid_9be3f809/](results/grid_9be3f809/).

| Case | Capacities (MiB) x latency scales | Median s indep / shared | Speedup | Final front | Distinct best EDPs |
| --- | --- | --- | --- | --- | --- |
| glu 64,128,256 @ nvdla | 1/32, 1/16, 1/4 x 0.25, 1, 4, 16 | 94.4 / 11.8 | 8.03x | 101 | 6 of 12 points |
| glu 256,512,1024 @ tpu_v4i | 1/4, 3/8, 1, 4 x 0.25, 1, 4, 16 | 502.8 / 86.2 | 5.83x | 24 | 6 of 16 |
| matmuls 3,256,256 @ nvdla | 1/32, 1/16, 1/4 x 0.25, 1, 4, 16 | 48.2 / 13.3 | 3.63x | 245 | 9 of 12 |

All three exit 0: every pick re-evaluates exactly at its capacity and scale, repeats
agree, both variants have the same EDP at every point. "Distinct best EDPs" counts
different optimal costs, not different optimal mappings: one mapping's cost can
change with bandwidth, and different mappings can tie. Mapping identities were not
recorded; audits now store `mapping_id` per pick (`common.mapping_identity`, a
structural fingerprint) and `optimal_mappings` per variant. The shared search spends
84.3 s of 86.2 s generating on GLU@tpu_v4i: per-target enumeration repeats the
min-usage templates once per capacity. These runs predate `d7c86825`, which changes
only fixed (symbol-free) templates, absent here, and narrows the audit reference to
the same point; all picks were already best known at their own point.

### Fixed templates and capacity-local audit comparisons

Review of `9be3f809` found a new shared-search regression on
`matmuls(1,1,1)@nvdla`, GlobalBuffer 64/128 bytes. Independent search returned one
valid mapping at each capacity, but shared search raised "Einsum Matmul0 has no
pmappings". A template with no symbolic tiles was represented as zero choices; the
new capacity-membership arrays consequently made its DataFrame empty. It now has one
assignment of zero variables, with constant capacity and hard minimum constraints
checked explicitly. DataFrame construction uses the actual assignment count, so an
infeasible constant template cannot be resurrected by scalar broadcasting.

The audit also no longer assumes that a pick at a smaller capacity belongs to the
larger capacity's search. Physical capacity feasibility is monotone, but the
capacity-dependent `min_usage` fallback makes the enumerated Mapspaces non-nested.
Default quality comparisons now use the same target configuration only; callers may
explicitly use cross-capacity bounds after proving membership and cost invariance.
This changes the audit's reference set, not search pruning or numeric tolerance.

Validation: 167 audit/Streaming tests pass. The fixed-template case matches across
`indep`, `var` and `push` at both capacities (re-evaluated EDP 1.81812e-19), and the
`matmuls(2,4,8)@nvdla` 64/128-byte by 1/32/256 latency-scale grid matches independent
search at all six points with every pick valid. Local serial runs, one repeat,
without warmup; these are correctness checks, not speedup measurements. Structured
before/after records: [results/fixed_template_review/](results/fixed_template_review/).

### Capacity-dependent min_usage fallback: counterexample and fix

**Problem (found in review of `610a2b10`).** When a spatial `min_usage` is unreachable,
tile enumeration keeps the highest attainable usage *among the candidates that fit*.
That set depends on the capacity, so a search at the largest capacity can drop
candidates an independent search at a smaller capacity keeps. On
`matmuls(2,4,8)@nvdla` with GlobalBuffer 64/128 **bytes**, the shared search found
nothing fitting 64 bytes while independent search did (grid audit exit 2; records:
[results/review_grid_coverage.txt](results/review_grid_coverage.txt),
[results/review_grid_min_usage.json](results/review_grid_min_usage.json)). It affects
capacity-only reuse too.

**Rejected fixes.** (1) Applying the fallback per capacity group but keeping a whole
group while its usage formula was not yet enumerated: the min-usage objective is
removed once complete, so the fallback never ran and the shared search returned a
mapping outside the independent Mapspace (Matmul0 reuse_input 0.125 where 0.25 is
attainable; it looked *better* than independent search, exit 5). (2) Per-group
fallback with optimistic membership: two chained min-usage fallbacks were applied to
the union of the first one's survivors and lost candidates (independent {2} and {1},
shared {2}; found in review, now a test).

**Fix.** `AF_GENERATION_CAPACITY_FRACTIONS=GlobalBuffer:f1,...` (set by the audits for
`var`, `push` and the grid's `shared`) tells generation its target capacities as
fractions of the searched one. For templates with min-usage constraints, tile
enumeration runs once per target with the plain rules plus `GlobalBuffer usage <= f`
(`get_tile_shape_choices_for_targets`), so each target's candidates are by
construction those of an independent search at that capacity; the union is kept.
Each pmapping carries one summed objective per target,
`Total<SEP>capacity_excluded<SEP>GlobalBuffer<SEP>f`, 1 where it was not among that
target's candidates. A joined row is returned for a target only where the sum is 0
(`common.rows_for_capacity`), so a candidate kept for one target is never returned
for another whose own fallback removed it. As a minimized objective this is safe for
Pareto pruning: a row dominating one with sum 0 has sum 0 too.

**Validation** (temporary worktree on f6752402 plus this change; records:
[results/coverage_fix/](results/coverage_fix/)). 158 tests pass, including exact
per-target membership for single and chained fallbacks. The 64/128-byte case now
matches independent search at all six grid points and in the capacity audit (exit 0
for both). GLU 64,128,256@nvdla on a 3x4 grid gives the same EDPs as before the fix
(7.19x). Half-scale GLU@tpu_v4i, four capacities, one repeat: same EDPs, var 2.46x,
push 3.43x; generation per shared search rose from about 33 s to 41 s because
templates with min-usage constraints are enumerated once per target.

### Cache and audit fixes after 610a2b10

- Candidate-cache keys now include all six generation switches and Pareto tolerance.
  Previously changing bandwidth objectives, selective resource tracking or ablations
  could silently reuse a candidate set generated under different rules.
- Strict re-evaluation checks every returned Reservation for finite occupancy in
  [0, 1]. A single-Einsum evaluation can bypass pairwise capacity filtering: a real
  `matmuls(1,4,8)` mapping reevaluated at 1 byte returned GLB usage 128 and was formerly
  certified `ok=True`. It now fails; exact-capacity usage remains accepted.
- Grid warmup discards query frames as they arrive, and each capacity slice is reused
  across bandwidth factors. Previously warmup retained copies for the whole grid.
  Grid CONFIG uses the selected Case; the log table labels capacity and latency-scale
  keys separately.

Validation: 147 audit/Streaming tests passed, followed by the five min-usage tests
including the new coverage counterexample (148 distinct tests in total). This includes
disk-cache reuse/invalidation, real one-Einsum capacity rejection, and weak-reference
checks that warmup does not retain the grid's frames. All 868 saved picks with recorded
Reservations satisfy the new occupancy check; this checks those records, not a new
server run or a proof of their candidate coverage.

### Capacity re-validation after the reservation fixes, commit `52953a43`

71591f38 changed reservation accounting, so the five multi-workload cases below were
rerun unchanged (three repeats, two lanes, eight workers each). Records:
[results/multi_52953a43/](results/multi_52953a43/). All five exit 0 with every flag
true. Medians indep / var / push and speedups:

| Case | Median s | var | push |
| --- | --- | --- | --- |
| glu 256,512,1024 @ tpu_v4i | 130.1 / 38.1 / 33.5 | 3.41x | 3.88x |
| matmuls 3,256,256 @ tpu_v4i | 59.2 / 21.6 / 20.5 | 2.75x | 2.88x |
| glu 64,128,256 @ nvdla | 24.5 / 7.6 / 8.3 | 3.24x | 2.97x |
| matmuls 3,256,256 @ nvdla | 10.8 / 6.2 / 4.1 | 1.74x | 2.61x |
| mobilenet 1 @ nvdla | 138.3 / 79.9 / 51.0 | 1.73x | 2.71x |

The best valid EDPs differ from the `3e6a8502` run by at most 1.1e-7 relative, in both
directions. AccelForge evaluates costs in float32 (`util.NUMPY_FLOAT_TYPE`; relative
precision about 1.2e-7), so the two runs agree to the model's precision; the
reservation fixes did not change any conclusion here. Comparisons across commits should
use a tolerance of a few 1e-7, not the 1e-9 used within one run.

### Bandwidth reuse (`AF_LATENCY_SCALES`), validated before commit

One search carries one latency objective per GlobalBuffer latency scale f (f = 4 is a
quarter of the bandwidth); `bandwidth_audit.py` compares it with one search per scale.
Five scales 0.25, 1, 4, 16, 64; one repeat, no warmup, eight workers, run under
`run_capped.sh 24 3600` on 71591f38 plus the then-uncommitted bandwidth changes, which
are committed unchanged except that the summary now also reports
`all_min_usage_checks_completed`. Their CONFIG shows commit `48b3216e`, dirty: 71591f38
re-applied in a temporary worktree. Records: [results/bandwidth_review/](results/bandwidth_review/).

| Case | GB MiB | EDP at f = 0.25 / 1 / 4 / 16 / 64 (indep = shared) | indep s | shared s | Speedup | Final front indep / shared |
| --- | --- | --- | --- | --- | --- | --- |
| glu 64,128,256 @ nvdla | 0.25 | 1.674e-10 / 1.674e-10 / 1.838e-10 / 3.151e-10 / 8.403e-10 | 54.3 | 15.4 | 3.54x | 1 each / 1 |
| matmuls 3,256,256 @ nvdla | 0.25 | 3.470e-10 / 3.470e-10 / 5.783e-10 / 2.313e-09 / 9.254e-09 | 44.3 | 16.0 | 2.77x | 1 each / 1 |
| glu 64,128,256 @ tpu_v4i | 4 | 6.448e-11 / 6.448e-11 / 6.980e-11 / 7.541e-11 / 8.959e-11 | 156.3 | 62.9 | 2.48x | 1, 1, 13, 25, 22 / 50 |

Every pick re-evaluates exactly on the architecture with its scale and the shared pick
has the independent EDP at every scale, including the bandwidth-bound ones where EDP
grows up to 27x. The final front grows only on GLU@tpu_v4i (50 rows). The scaled
objectives do carry information beyond Total latency: per pmapping, latency(f=64) /
latency(f=1) ranges over 19.2-64 on nvdla FFG. An earlier run of the linear version
(scaling the component's total latency) gave the same EDPs; the committed version
scales action latencies before evaluating `total_latency` (see the bug-fix review).

Limits: one repeat, small shapes, one capacity per run; capacity and bandwidth are not
yet varied together; leak power must be zero.

### Speedup versus the number of capacities, commit `70df4847` (superseded: before the coverage fix)

`sweep_capacity_count.sh` with K = 2, 4, 6, 16 GlobalBuffer capacities spaced evenly in
log2 (nested sets; nvdla 1/32-1 MiB, tpu_v4i 1/4-4 MiB), two repeats each, eight
workers. Records: [results/sweepK_70df4847/](results/sweepK_70df4847/). Median search
seconds and speedup over per-capacity search:

| Case | K | indep s | var s | push s | var | push |
| --- | --- | --- | --- | --- | --- | --- |
| glu 256,512,1024 @ tpu_v4i | 2 | 61.0 | 38.3 | 30.7 | 1.59x | 1.99x |
| | 4 | 136.7 | 40.9 | 33.7 | 3.34x | 4.06x |
| | 6 | 195.1 | 42.1 | 35.3 | 4.64x | 5.52x |
| | 16 | 524.4 | 32.8 | 31.4 | 15.96x | 16.69x |
| glu 64,128,256 @ nvdla | 2 | 15.3 | 8.9 | 7.7 | 1.72x | 2.00x |
| | 4 | 29.1 | 8.0 | 6.7 | 3.63x | 4.33x |
| | 6 | 45.1 | 7.2 | 7.1 | 6.26x | 6.32x |
| | 16 | 114.9 | 7.8 | 7.9 | 14.80x | 14.48x |
| matmuls 3,256,256 @ nvdla | 2 | 9.2 | 6.2 | 4.7 | 1.48x | 1.96x |
| | 4 | 17.8 | 5.3 | 5.3 | 3.39x | 3.35x |
| | 6 | 24.2 | 5.1 | 4.5 | 4.76x | 5.34x |
| | 16 | 68.5 | 5.3 | 6.0 | 12.95x | 11.46x |

All twelve runs exit 0: every pick valid, repeats consistent, no variant below the best
known EDP. The shared search costs about one per-capacity search (GLU@tpu_v4i: 31-42 s
against 524.4/16 = 32.8 s per capacity), and selecting a capacity's pick from its
result is negligible, so the speedup grows about linearly with K. push is not reliably
faster than var at this scale; their difference is within the run-to-run noise.

### Multi-workload validation, commit `3e6a8502`

Five cases, each with indep/var/push, three repeats in rotated order after an untimed
warmup, eight workers, no template-count limit, fixed bandwidth. Two cases ran at a
time under `run_capped.sh 24 7200`. Records: [results/multi_3e6a8502/](results/multi_3e6a8502/).

| Case | GlobalBuffer MiB | Median s indep / var / push | var | push | Peak RSS |
| --- | --- | --- | --- | --- | --- |
| glu 256,512,1024 @ tpu_v4i | 0.25, 0.375, 1, 4 | 124.3 / 33.9 / 32.9 | 3.66x | 3.78x | 3.8 GB |
| matmuls 3,256,256 @ tpu_v4i | 0.0625, 0.25, 1 | 60.4 / 25.4 / 21.2 | 2.38x | 2.85x | 3.5 GB |
| glu 64,128,256 @ nvdla | 0.03125, 0.0625, 0.25 | 23.6 / 8.0 / 7.4 | 2.97x | 3.20x | 3.1 GB |
| matmuls 3,256,256 @ nvdla | 0.03125, 0.0625, 0.25 | 10.9 / 4.4 / 5.4 | 2.46x | 2.01x | 3.0 GB |
| mobilenet 1 @ nvdla | 0.03125, 0.0625, 0.25 | 183.0 / 69.3 / 49.8 | 2.64x | 3.67x | 4.6 GB |

In every case indep, var and push pick mappings with the same re-evaluated EDP at every
capacity in every repeat; every pick re-evaluates exactly at its capacity, no variant
is below the best known EDP, and every usage check completed. The GLU@tpu_v4i EDPs equal
the `d422ce05` baseline below. The server load average was 150-220 on 256 cores, so
absolute times are noisy; each case's variants share its run's conditions.

- matmuls@tpu_v4i exited 3 under the then-current rule: at 0.0625 MiB, FFM's *reported*
  energy was 5.26846525e-5 in two repeats and 5.26846488e-5 in one (7e-8 relative),
  while every pick re-evaluates to E=5.2684652544e-5. Commit `371fb0e6` judges
  consistency and optimality on the re-evaluated EDP; re-judging all five logs with it
  finds every case consistent and best known.
- min_usage shortfalls are reported for GLU and MobileNet on both architectures and
  are all at the attainable maximum: a spatial dimension can only unroll ranks
  irrelevant to its tensor, so e.g. GLU FFG reuse_output on nvdla is 128/192, MobileNet
  pointwise 24/192 and 24/32, depthwise reuse_output 9/192, and FFH/depthwise
  reuse_input 1/128 or 1/32 (no irrelevant rank).
- MobileNet needed two fixes. The tag1 copy of the workload
  (`research/workloads/mobilenet_28_tag1.yaml`) renames `shape` and aligns Depthwise1's
  window. Its depthwise layers then failed in unmodified tag 1.0 with
  `KeyError: 'Depthwise0<SEP>n_iterations<SEP>2'`: a backing holder lowered through a
  sliding-window loop had its reservation below that loop (Compatibility counted it as
  fused) but `label_fused_loops` did not label the loop fused. `3e6a8502` labels fused
  loops from the actual reservation positions.
- Not covered: mobilenet@tpu_v4i (indep alone exceeded the 40-minute probe limit),
  eyeriss (energy plugin incompatible with tag1), bandwidth variation, larger shapes.

### GLU baseline, commit `d422ce05`

Current baseline, commit `d422ce05` (min-usage fallback fix, suboptimal picks fail the
audit). Half-scale GLU (256,512,1024), GlobalBuffer 0.25/0.375/1/4 MiB, fixed bandwidth,
no template-count limit, eight workers, three repeats in rotated order after an
untimed warmup. Run under `run_capped.sh 24 5400`; exit 0. Records:
[results/capacity_d422ce05_r3.txt](results/capacity_d422ce05_r3.txt).

| Capacity (MiB) | EDP, identical for indep/var/push in all repeats |
| --- | --- |
| 0.25 | 1.844437720269433e-08 |
| 0.375 | 1.841359736486614e-08 |
| 1, 4 | 1.5785650060107967e-08 |

| Variant | Search seconds per repeat | Median | Speedup vs indep |
| --- | --- | --- | --- |
| indep | 129.3 / 134.4 / 132.8 | 132.8 | 1.00x |
| var | 38.6 / 39.0 / 35.5 | 38.6 | 3.44x |
| push | 34.1 / 31.6 / 32.9 | 32.9 | 4.03x |

All flags are true except `all_min_usage_satisfied`: `all_picks_valid`,
`all_repeats_consistent`, `all_picks_best_known`, `all_min_usage_checks_completed`.
Process-group peak RSS was 3.8 GB. The server load average was about 216 on 256 cores,
so absolute times are noisy; the variants share each run's conditions.

Every pick has the same two shortfalls: Einsum FFH on ArrayFanout `reuse_input` and
`reuse_output`, usage 1/128 against min_usage 1. FFH is elementwise (b,m,c are relevant
to both its input and output), so neither reuse dimension has a rank to unroll and
1/128 is the highest attainable usage, which is FFM's documented fallback. Earlier
runs had the same mapping but reported no shortfall because the old checker skipped
dimensions without an explicit spatial loop. The min-usage fallback fix did not change
any pick in this experiment; the EDPs equal those recorded before it.

Earlier measurements and the investigation are in [HISTORY.md](HISTORY.md). The small
(4,8,16) smoke run used for the review is in
[results/review_smoke.json](results/review_smoke.json).

Remaining limits:

- The default `has_copy_above_fused_loops` filter excludes **all** templates with
  a non-backing shared-tensor copy above a fused loop. This is a conservative
  restriction, not a complete compatibility fix: agreeing copies on both sides
  may be representable too. Thus "unlimited templates" does not mean the original
  FFM Mapspace is preserved. Coverage and full-space optimality remain unproved.
- `min_usage` shortfalls and checker errors are different. FFM permits highest
  attainable usage when its minimum is unreachable. A shortfall is reported but
  is not by itself proof of a mapper bug; the audit does not prove that the fallback
  is globally best. A checker exception now invalidates the audit.
- Shared capacity filtering uses FFM's normalized floating-point Reservations.
  This does not certify byte-exact boundaries at every capacity scale.
- Streaming bounds temporary Pair blocks, not the live Frontier or total process
  memory. `run_capped.sh` samples RSS every two seconds; it is not a hard cgroup
  limit. The watchdog now cleans up its process group on SIGTERM/SIGINT/SIGHUP,
  timeout, RSS exhaustion and monitoring errors. SIGKILL cannot be handled, and
  descendants that explicitly leave the group are outside this guarantee.
- Capacity-only reuse is supported experimentally. Cross-bandwidth reuse, full
  candidate coverage, and a global memory budget are still separate tasks.

## Files and responsibilities

| File | Purpose |
| --- | --- |
| `summarize_audit.py` | One table per audit log: EDP per capacity and variant with invalid/suboptimal/shortfall flags, medians and speedups. |
| `capacity_audit.py` | Validated CLI, timed experiment loop, summary, worker cleanup in `finally`. Importing it does not start an experiment. |
| `bandwidth_audit.py` | Same for GlobalBuffer bandwidth: one search per latency scale (`indep`) against one search with `AF_LATENCY_SCALES` (`shared`), each pick re-evaluated at its scale. |
| `sweep_capacity_count.sh` | Runs `capacity_audit.py` for K = given numbers of log-spaced capacities per case. |
| `common.py` | Spec/search setup, environment hygiene, float64 EDP selection, mapping re-evaluation, spatial-usage checks, quality accounting. |
| `test_audit_logic.py`, `test_capacity_audit.py` | Validation, failure propagation, numeric boundaries, CLI and cleanup regressions. |
| `test_min_usage.py` | Real tile-enumerator regression for unreachable min_usage and reachable/hard minima. |
| `trace_pick.py` | Investigate one row, per-Einsum reconstruction and final mapping; diagnostic output, not an acceptance gate. |
| `check_shared_resources.py` | Investigate reservation mismatches across joined groups. |
| `run_capped.sh`, `run_capped.py` | POSIX process-group watchdog; shell entry point delegates to a standard-library Python supervisor. |
| `legacy_p0/` | Older upstream GPU/profiling experiments; not the tag1 backend. |
| `HISTORY.md` | Chronological evidence and superseded hypotheses. |

The helpers clear inherited `AF_*` variables before each search. The configuration
record includes the revision and whether either library or research files are dirty.

## Running and interpreting an audit

From the repository root, in the existing tag1 environment:

```bash
export PYTHONPATH="$PWD"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
research/tracking_audit/run_capped.sh 16 3600 audit.log -- \
    ~/graph_dse/venv-tag1/bin/python research/tracking_audit/capacity_audit.py \
    256,512,1024 0.25,0.375,1,4 indep,var,push --jobs 8 --repeats 3
```

The positional list holds the workload's parameters. `--workload` and `--arch` select
another case from `common.WORKLOADS` and `common.ARCHES`:

| Workload | Parameters | Graph |
| --- | --- | --- |
| `glu` (default) | M,G,C | Z feeds FFG and FFU, which merge in elementwise FFH, then FFB |
| `matmuls` | N_EINSUMS,M,KN | chain of N matrix multiplications |
| `mobilenet` | BATCH_SIZE | MobileNet block: pointwise and 3x3 depthwise convolutions (`research/workloads/mobilenet_28_tag1.yaml`) |

Architectures: `tpu_v4i` (default) and `nvdla`. `eyeriss` is excluded because its
energy plugin is incompatible with the tag1 library. Summarize logs with
`python research/tracking_audit/summarize_audit.py audit.log ...`.

Compare only runs with identical jobs, case, constraints and cost models. Search time
excludes re-evaluation; total elapsed time includes validation. Each RUN is saved in
the log before the next variant. Archive the log and exact code revision together.

Every pick is reconstructed and re-evaluated at the target capacity. Energy and latency
must be finite, nonnegative and agree within relative 1e-6. Spatial checks cover every
dimension on the active compute path; an omitted spatial loop uses one instance.

The SUMMARY separates:

- `all_picks_valid`: all capacity/cost checks succeeded and the usage checker completed.
- `all_repeats_consistent`: each variant's EDP agrees across repeats (relative 1e-9).
- `all_min_usage_checks_completed` and `all_min_usage_satisfied`: successful checking
  versus actual attainment of the requested utilization.
- `quality.*.suboptimal` and `all_picks_best_known`: a valid pick has worse EDP than
  another known valid pick feasible at that capacity (relative 1e-6).

Exit codes, most severe first: 2 for invalid picks (including an incomplete usage check)
or arguments; 5 if any variant is suboptimal; 3 for inconsistent repeats; otherwise 0.
A min_usage shortfall alone is reported but does not fail the run. Unexpected search errors propagate as failures,
and the capacity-audit worker pool is cleaned up on both success and exceptions.

The watchdog preserves the child exit code. It returns 137 for an RSS/time limit,
4 for live group members left after the main command exits, 128+signal when the
supervisor is cancelled, and 125 on launch/monitoring failure. `NO_VLIMIT=1` disables
only the per-process virtual-address limit; sampled RSS and time limits still apply.

## Bug-fix review after a686597f

- After Reservation insertion, fused-loop labels now use the actual first/backing
  Reservation of every shared tensor, matching Compatibility. Inferring the boundary
  from a Storage's `_lower` flag mislabels both reservations stopped above a loop and
  reservations lowered through multiple relevant loops. Four of five focused cases
  failed before the fix; all pass afterwards. Template-stage labeling is unchanged.
- Utilization checking includes `usage_scale`, as the model does. CONFIG builds the
  selected Case rather than always inspecting the default GLU configuration.
- The watchdog eliminates the startup race between `setsid` and the first `ps`,
  selects PGID explicitly, cleans up on cancellation, and fails on monitoring errors.
  Real child/grandchild tests cover exit status, all three cancellation signals,
  timeout, orphan cleanup and RSS control with `NO_VLIMIT=1`.
- Log summarization tolerates truncated JSON and missing historical flags, showing
  them as incomplete/unknown. A new CONFIG resets state, so an appended failed run
  cannot inherit an earlier successful SUMMARY.

Validation: 101 focused audit/Streaming tests passed locally. The single-process
`matmuls(2,4,8)@nvdla` smoke test at 0.03125/0.125 MiB completed under the watchdog:
indep/push had identical EDP 9.449881321091679e-17, all four picks re-evaluated, and
all usage checks completed. Expected shortfalls on this small shape are reported.
This was one run without warmup, not a speedup benchmark. Structured log lines:
[results/bugfix_matmuls_smoke.txt](results/bugfix_matmuls_smoke.txt).

## Bug-fix review after 79ab1f61

- Reservation prefixes now accumulate in sorted lifetime order. Unordered set
  iteration placed persistent depth -1 after depth 0, or depth 8 before depth 1.
  A 100-bit memory incorrectly accepted 60 persistent + 60 temporary bits because
  the deepest Reservation reported only 60 bits. The focused regression now rejects it.
- `limit_capacity()` removes the requested finished level, rather than reusing the
  column name from the deepest-level capacity check. Deeper reservations are retained.
- The working-tree bandwidth feature now scales modeled action latencies before
  evaluating the component's `total_latency`, instead of scaling its final result.
  Fixed overheads, fixed latency floors, direct action counts and constant formulas
  do not scale linearly. Tests compare with a separately scaled architecture and
  check that scenario evaluation leaves the base architecture unchanged.
- Bandwidth CONFIG now records the selected Case, matching capacity CONFIG.

Validation: 130 audit/Streaming tests passed locally, with 62 existing Pandas
deprecation warnings. The five reservation tests failed before the fixes; four
latency-formula cases also exposed the incorrect scalar projection. A single-process
`matmuls(2,4,8)@nvdla` run at 0.125 MiB and latency factors 1/32/256 passed all six
pick re-evaluations. Independent and shared EDPs agree at every factor, including
the bandwidth-limited cases. The watchdog reported exit 0 and 0.288 GiB sampled
group RSS. This small, un-warmed run is a correctness smoke check, not a performance
claim or exhaustive coverage proof. Its CONFIG identifies the dirty working tree;
records: [results/review_bandwidth_pressure.txt](results/review_bandwidth_pressure.txt).

## Regression tests

```bash
PYTHONPATH="$PWD" OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    python -m pytest -q research/tracking_audit research/streaming_join
```

The captured-Join tests default to the trusted, checked-in
`streaming_join/fixtures/real_join_large_tag1.pkl`. `CAPTURE_FILE` may override it
with another trusted capture of the expected schema. The capture uses a Pandas
StringDtype pickle format that Pandas 2.2.3 cannot read; the review suite was run
with Python 3.12, Pandas 3.1.0, NumPy 2.3.5 and paretoset 1.2.5.
These tests are not a full DSE benchmark or an exhaustive search-space proof.

## Library switches

Memory lists are comma-separated and unknown memory names raise.

| Switch | Effect |
| --- | --- |
| `AF_VARIABLE_RESOURCES` | Join retains the listed resource tradeoffs; fixed resources are removed only after the sum-of-maxima capacity proof. |
| `AF_GENERATION_VARIABLE_RESOURCES` | With RESOURCE_USAGE, preserve listed variable memories during generation; fixed memories use the normal elimination rules. |
| `AF_GENERATION_CAPACITY_FRACTIONS` | `MEMORY:f1,f2,...` (0 < f <= 1, 1 implied): target capacities of a shared search as fractions of the searched one. Templates with min-usage constraints are enumerated once per target and the union is kept; each pmapping gets `Total<SEP>capacity_excluded<SEP>MEMORY<SEP>f`, 0 if it is among target f's candidates. Requires RESOURCE_USAGE. |
| `AF_ENUMERATION_PREFIX_BYTES` | Nonnegative per-template key/array payload budget for exact prefix reuse across capacity targets. Default 0: disabled. Target-specific fallback/pruning is unchanged. Not a total memory limit; work counters are in `Job.enumeration_stats`. |
| `AF_LATENCY_SCALES` | `COMPONENT:f1,f2,...`: during generation, add one objective `Total<SEP>latency_scaled<SEP>COMPONENT<SEP>f` per factor. Scale that component's action latencies before evaluating its `total_latency` formula. Summed in the join like `Total<SEP>latency`. Requires LATENCY and zero leak power; other architecture attributes, dynamic energy costs and candidate constraints must remain fixed. |
| `AF_ABL_SKIP_BIG_ENOUGH` | Exempt listed memories from the full-tensor-size upper-bound elimination. |
| `AF_ABL_SKIP_PMAPPING_ONLY` | Exempt listed memories from the below-all-backing-holders elimination. |
| `AF_ABL_BIG_ENOUGH_UNTRACK_ONLY` | Stop reservation tracking for listed "big enough" memories while retaining usage objectives. |
| `AF_ABL_ALLOW_UNREPRESENTABLE=1` | Diagnostic restoration of templates excluded by the conservative copy filter; may reproduce invalid reconstructions. |

The ablation switches are experiment controls, not validated production features.
