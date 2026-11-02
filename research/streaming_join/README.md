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
