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
