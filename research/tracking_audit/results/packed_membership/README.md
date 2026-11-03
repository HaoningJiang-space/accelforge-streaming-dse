# Finite-target membership compression

This follows the event-enumerator audit at `0a424673`. All three methods here
already use `AF_TARGET_ENUMERATION=events`, selective resource tracking during
generation and Join, and normal symbolic/model caches. The experiment isolates
membership semantics/representation and CPU Pareto, not Tile enumeration sharing.

## Contract and implementation

The old `counts` mode gives target h one exclusion-count objective e_h. Generation
sets it to 0 or 1, Join adds counts, and querying h requires e_h=0. With nonnegative
counts, only zero vs positive matters for every future Join: e_h(p)+e_h(r)=0 iff
both terms are zero. Distinguishing 1 from 2 can retain unnecessary tradeoffs.

`boolean` clamps these counts to 0/1 before the existing scalar Pareto. `bitset`
packs allowed-target bits into uint64 words and uses a CPU window skyline. These
two implement the same stronger membership partial order. For equal FFM output
boundaries, p may dominate q only if A(p) includes A(q) and all relevant numeric
cost/resource components of p are no worse. Join uses A(p Join r)=A(p) intersect
A(r). Superset inclusion survives this intersection. Conditional on FFM's existing
resource/cost substitution rules, replacing q by p therefore cannot remove a
feasible declared-target extension. This does not prove the sufficiency of FFM's
Fusion boundaries or completeness of its original search space.

Membership is separate from physical feasibility; all Reservation checks remain.
The packed fields never enter a float array or scalar-min comparison. Words keep
canonical target labels in their column names; Pandas operations need no attrs.
Every word is native uint64, with unused bits zero. Schema mismatches, missing
target labels, mixed count/packed data, nonzero tolerance, explicit scalar grouping
of a packed word and lossy mixed-integer cost promotion are rejected. Equal numeric
points with equal membership retain the first source. Stable selection is relative
to the current ordered input, not a global canonical Mapping tie-breaker.

Generation emits packed columns directly from the enumerator's mask. DataFrame
Join intersects words, concat requires a common membership schema, and Pareto
compares superset inclusion within the original output boundaries. The existing
scalar incremental and persistent-boundary reducers fall back to the general
membership-aware Pareto path. This is correctness coverage for Streaming, not a
new optimized incremental bitset reducer. Numba compiles the CPU skyline without
fastmath; absence of Numba selects the equivalent Python function. The kernel
uses O(n) window indices rather than an n-by-n comparison matrix, but worst-case
time is still quadratic. No GPU implementation is added.

The resource-only breakpoint API now rejects both packed and count membership
columns. A resource staircase cannot infer a non-nested candidate policy at an
undeclared capacity. Use `rows_for_capacity()` for declared targets and retain the
source frontier for Mapping reconstruction.

## Measurements

Local Darwin arm64, one worker, one numeric thread, hash seed 0. Each case runs in
one process, warms all three methods on the full case, then rotates method order
over three measured repetitions. Warmups are retained as repeat=-1 but excluded
from medians. Bandwidth is fixed. Template counts are unlimited under the current
conservative Fusion filter. NVDLA uses GLU (64,128,256), log-spaced capacities
1/32..1/4 MiB; TPU v4i uses GLU (256,512,1024), 1/4..4 MiB. All capacity values are
saved in the JSON records.

| Case | Method | Generation median | Join median | Search median |
| --- | --- | ---: | ---: | ---: |
| NVDLA K=16 | counts | 3.700 s | 1.122 s | 4.822 s |
| | boolean | 3.863 s | 1.143 s | 5.207 s |
| | bitset | 3.217 s | 0.783 s | 3.999 s |
| NVDLA K=64 | counts | 4.030 s | 2.033 s | 6.058 s |
| | boolean | 4.212 s | 2.020 s | 6.316 s |
| | bitset | 3.406 s | 0.674 s | 4.084 s |
| TPU v4i K=64 | counts | 21.208 s | 2.346 s | 23.554 s |
| | boolean | 21.075 s | 2.392 s | 23.537 s |
| | bitset | 18.232 s | 0.751 s | 18.983 s |

Count/bitset search ratios are **1.21x, 1.48x, 1.24x**; the two K=64 Join ratios
are **3.02x and 3.12x**. Search is measured generation plus Join; medians of phases
need not sum to the median total. Query diagnostics, fingerprints and Mapping
re-evaluation are outside timers. These are warm local search times, not total
application/cold/server timings, and not independent-per-architecture FFM ratios.
Only three measured samples per mode are available; the raw samples are retained.

Boolean mode alone provides no consistent time reduction. Packed mode combines
smaller DataFrames, fewer comparison fields and a different CPU skyline kernel;
these measurements do not attribute its entire improvement to any one of them.
Actual Event expansions are unchanged across methods: 192 / 25,508 expanded rows
for NVDLA K=16, 211 / 34,106 for NVDLA K=64, and 2,443 / 703,993 for TPU K=64.
This is an execution/state-representation gain, not another reduction in symbolic
enumeration work.

| Join input payload | Rows | Count membership bytes | Packed bytes | Ratio |
| --- | ---: | ---: | ---: | ---: |
| NVDLA K=16 | 2,943 | 188,352 | 23,544 | 8x |
| NVDLA K=64 | 2,943 | 753,408 | 23,544 | 32x |
| TPU v4i K=64 | 7,673 | 1,964,288 | 61,384 | 32x |

These are membership array payload bytes only, excluding indices, schema strings,
Mapping provenance and scratch. The JSON peak RSS spans all methods in a process
and cannot provide a per-method RSS comparison. K label metadata and the Tile
enumerator's NxK Boolean matrix remain. Persistent output payload is O(n ceil(K/64)),
not independent of K. No global process/Frontier memory bound is claimed.

## Equality and validation

All 36 runs, including warmups, agree on the complete **Boolean-projected**
numerical frontier and on every target's cost/Reservation Pareto frontier. The
comparison includes numeric column names/dtypes and values. The count result is
clamped and Pareto-reduced for this semantic comparison: its raw table is not
claimed identical to the bitset table. In TPU, counts retain 10 final rows while
Boolean and bitset retain 8; both NVDLA cases retain 49 in all modes.

The final run of each method is checked at every target, giving 432 re-evaluated
selected mappings. All reproduce costs and satisfy capacity checks within the
existing model precision. Min-usage shortfalls permitted by FFM fallback remain
reported explicitly. These checks cover selected outputs, not every intermediate
Mapping or the full physical Fusion space.

`test_capacity_membership.py` adds 32 cases: 1/63/64/65/128/129-target round trips;
three-seed multiword differential Pareto checks against Boolean scalar objectives;
output boundaries, equal-point provenance and duplicate DataFrame indices; bit 63;
exact large integer costs; malformed/missing schemas; actual Join intersection in
batch and Streaming/numeric modes; and the historical 64/128-byte Matmul grid
with latency factors 1/32/256. The grid checks 18 re-evaluated picks and exact
per-target cost frontiers. A cache regression separates representation modes. The final full research/Streaming
regression passes **299 tests**, recorded in `regression.txt`.

## Files and reproduction

The raw `commit` field names the pre-experiment parent `0a424673`, because the
implementation was uncommitted while measuring. `source_sha256.json` records both
benchmark-time and final file hashes. After timing, final API review added only a
guard rejecting packed words in `split_by_cols`, plus extra invalid-input tests;
none of the benchmark calls uses that argument. The final regression log belongs
to that guarded source. Raw JSON is losslessly reformatted (flat scalar arrays
stay on one line); its decoded content was checked against the original files.

`summary.json` gives ratios/equality checks; the three case JSON files retain all
times, numerical frontiers and picks. `environment.json` pins dependencies.

```sh
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
python research/tracking_audit/benchmark_membership.py --arch nvdla --count 16 --repeats 3 --output /tmp/nvdla-k16.json
python research/tracking_audit/benchmark_membership.py --arch nvdla --count 64 --repeats 3 --output /tmp/nvdla-k64.json
python research/tracking_audit/benchmark_membership.py --arch tpu_v4i --count 64 --repeats 3 --output /tmp/tpu_v4i-k64.json
python -m pytest research/tracking_audit research/streaming_join -q --disable-warnings
```

For library use, set `AF_CAPACITY_MEMBERSHIP=bitset` during generation and Join,
alongside the declared `AF_GENERATION_CAPACITY_FRACTIONS` and resource tracking
settings. Packed DataFrames dispatch by schema even after the environment is
cleared. Default mode remains `counts`. This work does not implement continuous
regions, cross-topology costs, a Fusion Copy Contract or global memory control.
