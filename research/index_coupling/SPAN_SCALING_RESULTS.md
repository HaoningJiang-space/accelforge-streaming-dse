# Recursive-state scaling: results and a positional counterexample

Two representative P19 curves now complete in about four minutes with exact
agreement to the archived enumeration results. Name reuse and conditional
independence still do not eliminate the fork's dominant recursive state family,
and both remain opt-in. The implementation and equivalence arguments
are in [SPAN_CANONICALIZATION.md](SPAN_CANONICALIZATION.md); raw records are in
[results/span_scaling/](results/span_scaling/).

## First comparison: name reuse and conditional independence

At 0c7e2128, all arms used DP, projected ownership, witnesses, no profiling,
fresh Python 3.10.12 processes, 6 GiB address-space caps and 300 seconds per job
including replay. At most four benchmark jobs ran concurrently. These were
single runs without fixed CPU affinity or hash seed; small timing differences
are not a reliable ranking. No protocol or archived prediction was rescored.

| Six-consumer fork | Baseline DP | Independent operators | Independent + name reuse |
| --- | ---: | ---: | ---: |
| (4,2,4,2), kkkkkk | 123.0 s | 157.6 s | 149.6 s |
| (4,2,4,2), kkkiii | 102.1 s | 91.4 s | 98.6 s |
| (8,4,8,2), kkkkkk | Timeout | 285.0 s | Timeout |
| (8,4,8,2), kkkiii | Timeout | Timeout | Timeout |

The six completed medium-graph runs have equal curves within each shape/role
case, and all eight witnesses per run execute exactly. The completed large
all-k run has sixteen exact witnesses and matches **both** completed archived
DP and enumeration curves in `results/ownership/cut_dp_bench.jsonl`. Seven of
twelve jobs completed, with 64 successful witness replays; five are incomplete.
This experiment establishes a completed P19 sample, not a general speedup.

## Why simple name reuse reaches only a small part of the state space

A separate complete diagnostic uses fork(2,2,2,2,kkkkkk), with witnesses and
profiling. Counts include both completed solve and group cache entries:

| Variant | Cache entries | Loop choices | DP transitions |
| --- | ---: | ---: | ---: |
| Baseline | 106,604 | 141,027 | 1,659,790 |
| Name reuse | 93,833 | 119,727 | 1,584,642 |
| Independent operators | 106,477 | 132,835 | 1,394,975 |
| Both | 93,706 | 111,535 | 1,345,489 |

All four curves are checked for equality and their frontier witnesses are
replayed. Name reuse reduces cache entries by about 12%; independent splitting
reduces DP transitions by about 16%, while removing only 127 cache entries.
These are different improvements and should not be conflated.

The four largest baseline cache-miss buckets are:

| Entry/span | Misses |
| --- | ---: |
| solve, all six consumers | 16,897 |
| solve, producer and all consumers | 16,641 |
| group, producer and all consumers | 16,640 |
| group, all six consumers | 8,706 |

Together these comprise about 55% of completed cache entries. The three largest
buckets are identical under all four variants. Typical high-count contexts
retain three or four private outputs as well as other tensors. Most of these
are distinct residency patterns **inside one long ordered span**, not duplicate
names of shorter spans. Ordinary cut width is still just one.

## A four-operator counterexample to count-only residency summaries

Consider fork(2,2,2,2,kkk): EX produces X; E0/E1/E2 each consume X and their own
input C0/C1/C2. Compare two conditional solve interfaces with exactly two
resident private inputs, each of size four. All other boundary conditions agree.

| Resident inputs | Q at available capacity 3 | Full frontier (C,Q) |
| --- | ---: | --- |
| C1, C2 | 52 | (3,52), (4,32), (7,24) |
| C0, C2 | 56 | (3,56), (4,32), (7,24) |

The occupancy charged by the caller is eight in both cases. Tensor types,
resident counts, sizes and consumer counts match; **positions along the ordered
consumer sequence differ**. Sorting per-consumer residency profiles would merge
unequal subproblems. Enumeration and DP reproduce both curves, with and without
the new reductions; this is now a regression test.

The exploratory sweep found this after 18 conditional queries and stopped at
the first mismatch. It is a counterexample to the proposed invariance, not an
exhaustive classification of all residency patterns. It shows that counts alone
are insufficient; it does not prove that every subset requires a distinct state
or establish an exponential lower bound on the smallest sufficient interface.

## Profiling and static cut-incidence caching

A complete cProfile run on the same tiny dense fork recorded 31.19 seconds
under profiling. `cut_dp` accounts for 10.05 seconds of self time; staircase
merging accounts for 2.93 seconds and Pareto pruning for 1.83 seconds of self
time. Tensor-size computation accounts for about 2.06 seconds inclusive.
These profiled proportions identify candidates for engineering work; they are
not production timing estimates.

The follow-up at 49a45850 caches per-span first/last/writer positions, crossing
sets, candidate group tensor sets and reader sets. These depend on graph
incidence, not extents or reservations. Each call filters the static crossing
sets by its current external tensors. Transition charges and the search space
are unchanged. The same revision includes a concurrent `tile_domain` extension;
all measurements retain its historical `halving` default. Therefore timing
changes are not attributed solely to cut metadata caching: that revision also
caches the default tile enumeration.

Three unprofiled fresh-process timing pairs on the tiny dense fork alternate
before/after revisions on the same allowed logical CPU. Both enable independent
splitting and witnesses, with name reuse disabled:

| Source | Search times, seconds | Median |
| --- | --- | ---: |
| 0c7e2128 | 12.607, 12.688, 12.412 | 12.607 s |
| 49a45850 | 10.624, 10.632, 10.547 | 10.624 s |

The ratio of medians is 1.19x, or about 15.7% less search time. All six curves
are equal and all eighteen witnesses replay exactly. Peak RSS is approximately
179 MiB in both versions. This is a constant-cost improvement, not a reduction
in the number of recursive states or an asymptotic complexity improvement.

The post-hoc large P19 jobs use the latter source, independent splitting, no
name reuse, witnesses, no profiling and a **600-second** budget per job. Their
larger budget is intentionally separate from the original 300-second matrix.

| P19 shape/roles | Search time | Peak RSS | Replay | Archived curves |
| --- | ---: | ---: | --- | --- |
| (8,4,8,2), kkkkkk | 240.24 s | 2.44 GiB | 16/16 exact | Equals both DP and enumeration |
| (8,4,8,2), kkkiii | 242.95 s | 2.52 GiB | 16/16 exact | Equals both DP and enumeration |

Both returned within the earlier 300-second window despite the increased cap.
These are individual completion measurements, not a universal speed guarantee.
Including the first matrix, diagnostic curves, timing controls and these two
jobs, 19 of 24 curve jobs completed and all 126 returned frontier witnesses
replayed exactly. Five earlier timeouts remain explicitly incomplete. The
independent cProfile run is a separate timing diagnostic, not another replay
job in that total.

## Validation and scope

The first frozen implementation passed 22 tests locally and remotely. The
positional counterexample adds one test; 49a45850 passed all 23 locally, with
the frozen source also checked on the experiment server. Source hashes accompany
every curve record. The diagnostic runner is archived as `profile_driver.py`.

The useful structural result is conditional independence under fixed external
reservations. The important limitation is that residency **positions**, not
merely counts or graph cut width, affect the conditional frontier. Further
compression needs a proved relation between ordered residency patterns or
valid bounds for pruning them. The experiments do not justify reordering
consumers, merging equal-count patterns, or enabling name reuse by default.

Current use for this P19 configuration is:

```python
points = curve(graph, partitions='dp', independent_ops=True, witness=True)
```

Static cut metadata caching is automatic in DP mode. To reproduce the final
bounded runs from the repository root at 49a45850:

```sh
python3 -m research.index_coupling.bench_solver_scaling \
  --out p19 --revision 49a45850 --cases p19_same p19_mixed \
  --variants dp_projected --independent-ops --no-profile \
  --seconds 600 --mem-gib 6 --workers 2
```

The source label is supplied by the caller; the runner independently hashes
its source files. All archived hashes have been checked against the recorded
commits. The experiments here cover at most seven operators in a fork. State
growth and static-metadata storage should be profiled again before moving to
much longer graphs; no 16-to-128-operator scaling claim follows from this batch.
