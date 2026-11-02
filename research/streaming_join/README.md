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
