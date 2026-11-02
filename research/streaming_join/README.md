# FFM streaming-join experiment, AccelForge tag 1.0

This branch starts at upstream tag `1.0`, commit
`241f3cdab1418caef20d3a95506817f0a0e69ed8` (2026-02-02). It is the newest
upstream tag by commit date. The previous server baseline was on a substantially
newer untagged upstream commit (`04cf894e3f33aae6ea9814104a852c160f4d9e25`,
2026-11-01). API, mapper and hardware definitions differ. Historical results
under `baseline/`, including the 173-second sweep, are provenance only and
cannot be treated as the tag 1.0 baseline. `glu_tag1.yaml` expresses the same
four contractions in the older workload syntax, but the two versions' full
mapping and performance semantics have not been shown equivalent.

The archived `baseline/exp2_sweep.py` exhausted a shared server's RAM and is
**not safe to run unmodified**: it lacks worker, memory, and time limits.
`baseline/profile_small.out` was measured on the newer commit, not tag 1.0.
It used a single process and an inherited 4 GiB RLIMIT_AS. The server's user
systemd scope was not verified to enforce a process-tree memory limit. Never
launch the failed multiworker workload without such a verified limit. The
machine is shared; do not stop unrelated processes.

## Initial results

With shape M=32, G=64, C=128, one mapping template per Einsum, a single
worker, and a 4 GiB virtual-address limit, paired tests produced:

| Metrics | Maximum pairs per block | Baseline Join | Streaming Join | Outcome |
| --- | ---: | ---: | ---: | --- |
| Energy, latency | 64 | 1.51 s | 1.08 s | 6 objective rows match |
| Energy, latency, resource usage | 4,096 | 3.43 s | 22.75 s | 1,076 objective/reservation rows match |
| Energy, latency, resource usage | 65,536 | 3.44 s | 4.74 s | 1,081 objective/reservation rows match |

These are single paired observations; the baseline always ran first and results
are sensitive to JIT/cache warming, hash order and shared-server load. They do
not establish speedup. The reported peak RSS is cumulative within the process
and cannot separate the two implementations. Each individual test compares its
own original and streaming outputs with rtol=1e-12 and atol=1e-20; different
processes produced slightly different frontier sizes. The exact-comparison
code and JSON summaries are included. Separate-process measurements are needed
for a memory comparison.

The current implementation is experimental and opt-in through
`AF_STREAMING_JOIN_PAIRS`. It bounds the product in each join block, but the
accumulated Pareto frontier and other phases are not bounded. It falls back to
the original code for custom row filters and rejects nonzero Pareto tolerance.
The evidence does not cover arbitrary workloads, all join cases, or the original
large failing search. Do not enable it by default or claim production readiness.

The tag required two small compatibility fixes: scalar objective handling in
candidate generation, and keeping tracked memories when RESOURCE_USAGE is an
objective. The second follows the behavior of the newer upstream code but still
needs broader validation. The isolated server dependency directory uses
`numpy==2.2.6`, `scipy==1.15.3`, and `paretoset==1.2.5` with the existing
`graph-dse` Python environment; `ACCELFORGE_CONFIG_PATH` points into the
experiment directory.

A separate-process test with M=64, G=128, C=256, one template per Einsum,
RESOURCE_USAGE, pair limit 65,536, fixed `PYTHONHASHSEED=0`, one thread, and the
same 4 GiB address-space limit returned 222 equal objective/reservation rows
(rtol=1e-12, atol=1e-20) and equal best EDP of 4.112123481360056e-11 J s.
The original Join took 3.73 s and peaked at 403,748 KiB RSS; streaming took
25.11 s and peaked at 385,504 KiB. Each process includes candidate generation
in its peak. This single run gives no robust speed or memory estimate: the
streaming version is substantially slower here and has not yet met the goal.
The separate JSON files include the entire compared numeric frontiers.

Batching up to eight local frontiers (and at most 65,536 buffered rows) reduced
the same seeded medium streaming test from 25.11 s to 16.28 s in a single
run; it still took more than four times the original Join's 3.73 s. The full
222-row numeric frontier and best EDP matched the separate baseline under the
same tolerances. Instrumentation measured 669 chunks and 87 frontier merges,
with 13.11 s in chunk joins and 1.62 s in frontier merges. Streaming peak RSS
was 384,568 KiB. These are exploratory measurements, not a statistical claim.

## Captured join

`fixtures/real_join_tag1.pkl` contains one real tag 1.0 FFM compatibility-group
input (capture commit `3dfe1472`, M=64/G=128/C=256, one template per Einsum,
RESOURCE_USAGE). Its SHA-256 is
`d4f2d5196d622c254682f0408cfbed2ef2e6c832802718c3e10d919e5366908a`.
Pickle can execute code on loading: replay only trusted, verified captures.
The fixture holds 37 left and 534 right rows, with 19,758 logical possible
pairs. Replay at a 4,096 pair limit retained 19,730 states, with numeric
objectives, reservation, fused-loop and live-tensor columns matching the
original (rtol=1e-12, atol=1e-20). The original was run first in the replay;
its 3.49 s versus 0.41 s streaming is confounded by first-use JIT compilation
and must not be treated as a speedup. This one group cannot explain the earlier
full-workload OOM. Output IDs and the final mapping still require end-to-end
validation beyond this group.

A full-size M=512/G=1024/C=2048 trial at 8 MiB GlobalBuffer and two templates
per Einsum reached the second Join under a 4 GiB single-process address-space
limit but hit its 120-second timeout. A one-template trial at 0.5 MiB produced
no valid FFH candidates. Neither run proves the full mapping space or previous
OOM is handled; both used tag 1.0 rather than the newer historical baseline.

A second fixture, `fixtures/real_join_large_tag1.pkl`, contains 19,730 left
rows and 48 right rows (SHA-256
`707e82d33955fb2aa47fbde8541a42abf42924695394c8182c946d3b61eaa150`).
Although their product is 947,040, grouping by the actual FFM inner-join keys
shows only 19,730 matching pairs across 48 keys. Therefore the original
`pd.merge` does not materialize the full product. The replay, warmup followed
by three alternating trials, found a 0.131 s median for original Join and 2.684 s
for naive streaming. Their resulting 19,730 states matched on the relevant
objective, key, reservation and live-tensor columns. These are two execution
strategies on one group; no general performance claim follows.

An opt-in keyed fast path counts matching pairs without materializing them,
then calls the original Join only when their count is within the pair limit.
It conservatively falls back for null keys, mismatched key dtypes, duplicate
key columns or unsupported cases. For the same fixture, three alternating
warmed trials yielded medians of 0.129 s original and 0.144 s streaming, with
the same 19,730 states. End-to-end on the separately measured medium GLU, this
reduced streaming Join from 16.28 s to 6.23 s versus 3.73 s original; 222
objective/reservation rows and best EDP matched. Different timing runs are
sensitive to shared-server load and are not statistical estimates.

Five targeted tests cover count, nulls, incompatible types, no matches, and
nonzero Pareto tolerance. Neither a global multi-worker memory budget nor GPU
execution, architecture masks, or cross-architecture search reuse is
implemented. For custom row filters the original unbounded join is used.

The subsequent key-group scheduler collects only matching keys and tiles each
set to stay within the matched-pair limit; unsupported key cases use the generic
streaming fallback. On the 947,040-product capture, with a 4,096 matching-pair
limit, warmed medians were 0.132 s original and 0.615 s streaming, with 19,730
matching boundary/resource/objective rows; the largest materialized matching
block was 3,995. On the independent medium GLU run with limit 65,536, streamed
Join was 3.95 s with 383,472 KiB peak RSS versus original 3.73 s with 403,748
KiB. All 222 compared frontier rows and best EDP matched. Both measurements are
single-workload evidence, and the separate-process medium timing was not
repeated. The saved JSON includes full numeric frontiers for replay.

For the large captured group and a 4,096-pair budget, separate-process
instrumentation measured the largest materialized candidate DataFrame at
10,654,332 bytes (original) and 2,157,432 bytes (streaming). Both retained
19,730 rows, approximately 6,076,972 DataFrame bytes, in the final frontier.
The input DataFrames totaled 5,773,580 bytes. Process peak RSS was 315,044 KiB
and 321,340 KiB respectively; smaller candidate tables did not reduce total
RSS in this case. DataFrame deep-byte estimates do not measure all temporary
arrays, fragmentation, shared memory, or simultaneous allocations, so they do
not establish a global memory budget or explain the original OOM.

At the original M=512/G=1024/C=2048 tensor dimensions, 8 MiB GlobalBuffer,
RESOURCE_USAGE, and **two templates per Einsum**, separate single-process runs
on commit `35dd2ec2` produced 1,650 equal numeric frontier rows and the same
best EDP, 3.4053741543105104e-7 J s. The original Join took 150.16 s with
2,951,796 KiB peak RSS; the streaming Join took 135.18 s with 759,596 KiB peak
RSS. These are one-off observations with a constrained Mapspace and an older
tag, not the full original search, 15-configuration DSE, or a stable speedup.
The process peak includes generation. The complete numeric frontiers are saved.

An opt-in selective-resource experiment at M=64/G=128/C=256, one template,
protecting GlobalBuffer and dropping fixed memories only after the existing
sum-of-maxima proof, reduced the sampled shared result from 222 to 18 rows.
All five tested capacity-filtered EDP values matched the full RESOURCE_USAGE
shared search. However, at 0.03125 MiB, the independently searched EDP was
4.112123481360056e-11 versus 4.7251909016893453e-11 for either shared search.
The other four sampled capacities matched. This is a correctness discrepancy,
not a validated cross-architecture reuse result. The initial script printed
this mismatch without a failing exit code; a later revision fails on it. The
cause is being investigated and the policy remains experimental and off by
default. See `results/tag1_resource_selection.json`.

The first prepared-JoinPlan revision was compared against the pre-change
`383dcb84` on a real group: both unblocked and blocked paths agreed across
19,730 rows and 21 join-relevant fields. Its complete medium GLU numeric
frontier also matched the earlier reference (222 rows); a single streaming
Join was 4.02 s versus 3.95 s before preparing the plan. This does not yet
establish a speed improvement or a numeric/CUDA backend.
