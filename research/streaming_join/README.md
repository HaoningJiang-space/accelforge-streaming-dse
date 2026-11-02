# FFM streaming-join experiment

The historical server baseline used AccelForge commit
`04cf894e3f33aae6ea9814104a852c160f4d9e25`, plus the standalone GLU YAML
in this branch. The prior server checkout also has an unrelated opt-in `AF_ABL`
patch. Its independent baseline did not enable that patch. Preserve the patch
in the original checkout; it is not part of this branch.

`baseline/exp2.jsonl` contains 15 independent searches. No shared-search result
was produced: the second part of `exp2_sweep.py` exhausted server memory. The
script is archived for provenance, **not safe to rerun unmodified**: it does not
limit workers, memory, or runtime. The earlier timing was a single run with
in-process caching on a shared machine; it is not a repeated benchmark.

`baseline/profile_small.out` is one cold, single-process, cProfile-instrumented
small-GLU observation on eex005. Profiling adds overhead. The experiment used
one FFM job, one numerical-library thread, an inherited 4 GiB RLIMIT_AS, a
120-second timeout, and a Python audit hook forbidding subprocess creation.
The systemd user scope was not a verified memory-controller limit. RSS is for
the Python process, not a process tree. The output reports 360224 KiB peak RSS,
35.08 s generation and 6.89 s profiled join. Times are not comparable to
the historical multithreaded 15-point sweep.

Do not launch the original shared search without a verified process-tree memory
limit; a per-process RLIMIT_AS does not limit multiple worker processes. The
shared server belongs to multiple users; never terminate unrelated processes.
