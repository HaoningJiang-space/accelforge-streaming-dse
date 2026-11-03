# Direct membership construction and Join sparsity audit

This follow-up to `3b1b09b4` measures whether target membership can eliminate real
Join work, removes the final dense membership matrix in bitset generation, and
implements an opt-in early filter. It does not implement a membership Join index,
continuous-capacity regions, or a Fusion Copy Contract.

## Direct output contract

`build_target_membership()` consumes final cohort row positions and target IDs.
For every row r and target h, its bit is set iff some supplied cohort contains
both r and h. Wordwise OR therefore gives exactly the complement of the old
Boolean exclusion matrix. It supports repeated rows, overlapping cohorts and
unsorted/duplicate target IDs. The Event enumerator still preserves its original
ordered partial arrays, Pareto history, fallback sequence and empty-target dtype
promotion. The independent path still runs each target's complete program.

`get_tile_shape_choices_for_targets(..., membership_format='packed')` explicitly
returns `PackedMembership`; its default remains the existing Boolean interface.
Production bitset mode requests packed output, including when Event enumeration
falls back to the independent backend. `pack_exclusions()` attaches canonical
sorted target labels; original-order bits are permuted if necessary. Sorted labels
use views of the constructed word array. No NxK Boolean output matrix is built in
this path; masks inside enumeration and cohort/state/index storage still exist.
The output needs N*ceil(K/64) uint64 values, and label metadata remains O(K).

## Early filtering contract and the empty-block trap

If M(p) intersect M(q) is empty, intersecting it with any future membership cannot
make it nonempty. Such a pair cannot be returned at any declared target, regardless
of its numeric costs. This rule does not add any resource-bound approximation and
does not depend on treating Membership words as scalar Pareto costs.

`AF_MEMBERSHIP_JOIN=early` computes this intersection immediately after `pd.merge`,
before cost/Reservation composition, and removes dead rows. Default remains `late`.
The initial matched pairs are still materialized. Later stages may materialize
fewer pairs because dead states no longer propagate, but no pre-Join index is
implemented. Legacy Mapping-count estimates retain their compatibility-based
meaning; actual work is counted separately at `adjust_reservations()` entry.

A real-fixture regression caught a dtype hazard: reducing an empty Pandas frame
can create float64 resource columns where the reference path used int64. Empty
Streaming chunks can then change concat promotion and subsequent arithmetic.
For a fully target-dead block, the implementation conservatively performs the
reference composition and Pareto, then returns its empty typed result. Mixed
live/dead blocks avoid dead-row composition. The diagnostic records expose this
fallback's cost; it must not be counted as avoided resource work. Arbitrary row
callbacks are rejected in early mode because they may inspect the complete table.

## Measurement design

The initial five `*-structure.json` records use production code at `3b1b09b4`.
An observer counts the actual rows returned by Pandas matching joins and computes
their membership intersections. Those diagnostic times are instrumented, not
performance baselines. `rho_zero` is the ratio of summed dead pairs to summed
matched pairs, not the mean of per-group percentages.

All subsequent ablations use the changed source pinned in `source_sha256.json`.
They run locally with one worker and one numeric thread, hash seed 0, fixed
bandwidth, unlimited template count under the conservative Fusion filter.
Each method is warmed on the full case, then three measured repetitions rotate
method order in one process. The three full-search methods are:

- `dense_late`: explicit Boolean-output API, then packing, then old Join placement.
- `direct_late`: packed-output API and old Join placement.
- `direct_early`: packed-output API and early filtering.

All use Event enumeration and bitset Pareto. This isolates final output construction
and Join placement, not the older count-column versus bitset kernel comparison.
The dense baseline uses the current shared constructor in Boolean mode; it is not
a fresh execution of the entire old commit. Generated inputs must have identical
fingerprints covering numeric values/order/dtypes, normalized template provenance,
compatibility, count estimates, indices and Pandas block layout.

MobileNet is a separate **Join-only replay**: generate once, copy the frozen input
outside the timer, warm both Join modes, then alternate three repeats. Its make_s=0
does not mean generation is free. Deep copying may consolidate Pandas blocks;
the recorded fingerprints describe those identical replay inputs, not the layout
immediately after generation. Diagnostic replays of every case are separate
from timed runs and count exact rows entering Reservation composition, including
fully dead blocks that use the schema-preserving fallback.

Frontier comparisons include every target's numeric cost/Reservation frontier.
The complete numerical-frontier check first removes zero-membership rows in both
paths; such rows intentionally disappear under early filtering and have no target
query semantics. Final selected mappings are rebuilt and evaluated at every
capacity. These checks retain existing model precision and fallback rules, not
complete physical Mapping-space optimality.

The construction microbenchmark uses 32,768 synthetic rows and fixed overlapping
cohorts, with K=64/256/1024. Five alternating samples time construction plus schema
labeling. A separate tracemalloc run records peak allocation for that operation,
including NumPy buffers; prebuilt cohort inputs are excluded. It is neither RSS
nor a whole-search memory bound. Packed words are compared exactly before timing.

Interval statistics count contiguous runs of ones in the **sampled ordered target
list**. They do not certify membership between sampled capacities. The larger K
records are generation-only diagnostics, not new full-search correctness or timing
claims. K=64 uses the initial structure profile; other K values use the direct
output code. The ablations establish equality between both constructions at K=64.

## Recorded results

The initial late-path profiles count:

| Case (K=64) | Matched pairs | No common target | Fraction |
| --- | ---: | ---: | ---: |
| NVDLA GLU | 20,527 | 0 | 0% |
| NVDLA Matmul chain | 4,790 | 0 | 0% |
| NVDLA MobileNet | 2,310,624 | 1,504 | 0.0651% |
| TPU v4i GLU | 4,302 | 24 | 0.5579% |
| 64–128-byte Matmul counterexample | 217 | 129 | 59.45% |

Every initial generated row has one sampled interval. The late counterexample's
final frontier includes two zero-membership rows; early filtering removes those.

| Current-code warm median | Dense output, late | Direct output, late | Direct output, early |
| --- | ---: | ---: | ---: |
| NVDLA GLU search | 4.490 s | 4.366 s | 4.685 s |
| TPU v4i GLU search | 19.672 s | 19.773 s | 19.786 s |
| Counterexample search | 0.861 s | 0.895 s | 0.847 s |
| MobileNet Join-only replay | — | 4.694 s | 5.044 s |

There is **no consistent end-to-end speedup** in these three-sample experiments.
The counterexample's Join medians are 19.60 / 19.41 / 19.92 ms. A high empty-pair
fraction is insufficient when absolute work is small. MobileNet's replay also
shows overhead exceeding the benefit of its sparse deletions. Early filtering
remains optional; this evidence does not justify a complicated membership index.

Actual rows entering Reservation composition (late -> early): GLU 20,527 -> 20,527;
TPU 4,302 -> 4,278; counterexample 217 -> 88; MobileNet 2,310,624 -> 2,309,120.
TPU materializes 4,300 rather than 4,302 pairs under early filtering, a small
downstream effect. Other measured totals remain unchanged. No measured case has
a fully target-dead block; the schema-preserving fallback is tested by regressions.
The 44 ablation runs including warmups have equal live numerical/per-target
frontiers. All **704 final ablation picks** re-evaluate; the initial profiles add
320 successful checks. These are repeated selections, not 1,024 unique mappings.

The isolated constructor is a different result:

| Targets (32,768 synthetic rows) | Dense + pack | Direct pack | Dense peak traced | Direct peak traced |
| ---: | ---: | ---: | ---: | ---: |
| 64 | 8.176 ms | 0.470 ms | 2.788 MiB | 0.317 MiB |
| 256 | 31.830 ms | 0.964 ms | 9.554 MiB | 1.068 MiB |
| 1024 | 176.815 ms | 2.949 ms | 36.641 MiB | 4.141 MiB |

At K=1024 this operation is about 60x faster with about 8.85x lower traced peak
allocation. Both methods return exactly the same 4 MiB word payload. It is a
local construction improvement, not a full-search speedup or RSS claim.

| Sampled K | GLU rows / distinct masks / max runs | Counterexample rows / distinct masks / max runs |
| ---: | ---: | ---: |
| 16 | 2,943 / 5 / 1 | 69 / 12 / 1 |
| 64 | 2,943 / 9 / 1 | 75 / 13 / 1 |
| 256 | 2,943 / 13 / 1 | 75 / 13 / 1 |
| 1024 | 2,943 / 15 / 1 | 75 / 13 / 1 |

Existing Event expansion calls in GLU are 192, 211, 233, 252; in the counterexample
they are 174, 180, 180, 180. Direct output does not change this enumeration algorithm.
The sampled masks make finite-target interval encoding worth investigating, but
do not prove an interval theorem for all templates, all intermediate cohorts or
unseen capacities. These are policy-membership intervals, not optimal-Mapping
regions. Fusion legality/completeness remains a separate unresolved problem.

## Tests and reproduction

`regression.txt`: **325 research/Streaming tests pass**. The 26 new cases cover
direct output at 1/63/64/65/129/1024 targets, zero rows, original-order bits and
label permutations, duplicate/empty targets, consecutive min-usage fallback,
explicit independent fallback, sparse real-fixture joins, fully dead blocks,
Streaming/numeric execution, provenance and exact dtypes. The historical
64/128-byte grid includes three latency factors and re-evaluated selections.

The raw files retain all samples, input hashes, frontiers and per-target picks.
Flat scalar arrays are compacted without changing decoded JSON. Environment and
file hashes are archived. The parent commit field records the pre-commit parent;
the source manifest identifies the modified implementation used for ablations.
Final ownership review added a deep copy for fully dead empty outputs so they do
not retain backing arrays. That branch is absent from the measured cases, as
their diagnostic counts show. Both benchmark-time and final source hashes are
recorded, and the complete regression was rerun on final source.

```sh
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
python research/tracking_audit/benchmark_membership_pushdown.py --case glu --output /tmp/glu.json
python research/tracking_audit/benchmark_membership_pushdown.py --case tpu --output /tmp/tpu.json
python research/tracking_audit/benchmark_membership_pushdown.py --case counter --output /tmp/counter.json
python research/tracking_audit/benchmark_membership_pushdown.py --case mobile --join-only --output /tmp/mobile.json
python research/tracking_audit/benchmark_membership_construction.py --output /tmp/construction.json
python research/tracking_audit/audit_membership_structure.py --count 1024 --generation-only --output /tmp/intervals.json
python -m pytest research/tracking_audit research/streaming_join -q --disable-warnings
```

For complete structure profiles, omit `--generation-only`. The default is GLU
(64,128,256) / NVDLA at 1/32..1/4 MiB; use `--workload matmuls --params 3,64,128`
for the chain, `--workload mobilenet --params 1` for MobileNet,
`--arch tpu_v4i --params 256,512,1024 --low .25 --high 4` for TPU, and
`--workload matmuls --params 2,4,8 --low .00006103515625 --high .0001220703125`
for the historical capacity counterexample. Run each process sequentially when
reproducing timings.
