# Solver scaling results

The first implementation batch fixes the audit's eager materialization and
provides a useful DP path for residual chains. It does **not** resolve the P19
six-consumer bottleneck. Enumeration remains the default; DP is explicitly
selected with `partitions='dp'`.

Implementation and equivalence arguments are in [SOLVER_SCALING.md](SOLVER_SCALING.md).
Raw records and their source hashes are in [results/solver_scaling/](results/solver_scaling/).
No P21d protocol, candidate cut rule, or frozen scientific verdict was changed.

## What changed

- Cache keys now project `owned` to tensors with a writer inside the subproblem.
  Removing other ownership bits preserves every charge in the current grammar.
- Exact staircase merging uses a linear sweep; tensor axes and loop legality
  metadata are reused. The earlier merger already avoided Cartesian products.
- Optional counters expose cache growth, partition/loop/DP choices, frontier
  sizes and witness rope allocations. Witnesses already shared rope nodes;
  this work does not claim to have introduced witness sharing.
- Cut DP handles restricted-cut boundary zero safely, falls back to enumeration
  for multiwriter spans, and rejects approximate grid pruning.
- The all-plan audit generates and executes one derivation at a time. Plan,
  expansion-node, wall-time and memory limits now act during generation.
- The ownership regression passes timeout/lazy settings through worker
  initialization and returns a nonzero incomplete status for unfinished work.

## Curve comparisons

The initial five-case matrix was specified before measuring it, at c38b2fa1.
Each arm used witnesses, profiling, a fresh Python 3.10.12 process, a 180-second
budget including replay, and a 6 GiB address-space cap. At most four jobs ran
concurrently. "Baseline" in filenames means the previous ownership **cache key**;
both variants use the corrected final-write pricing.

The table compares the projected ownership variants. Timings in this table
include profiling overhead. A timeout means search did not return a curve.

| Graph | Operators | Enumeration | Cut DP | Evidence |
| --- | ---: | ---: | ---: | --- |
| fork(2,2,2,2,kki) | 4 | 0.127 s | 0.125 s | Equal curves; 4/4 witnesses exact in each arm |
| residual(2,2,2,depth3,readX) | 5 | 0.0467 s | 0.0323 s | Equal curves; 5/5 witnesses exact in each arm |
| P19 fork(8,4,8,2,kkkkkk) | 7 | Timeout | Timeout | No equality or speedup conclusion |
| P19 fork(8,4,8,2,kkkiii) | 7 | Timeout | Timeout | No equality or speedup conclusion |
| residual(8,2,4,depth12,readX) | 14 | Timeout | 3.80 s | DP 9/9 witnesses exact; enumeration equality unverified |

The complete initial matrix contains 10 completed and 10 timed-out arms. All
completed variants for a given graph have equal curves. For the depth-12 case,
that comparison is **between the two DP ownership-key variants**, not between
DP and enumeration. Its projected DP run peaked at 32.1 MiB RSS; enumeration
reached about 2.0 GiB before its timeout. These are observed resource records,
not an estimate of enumeration's eventual completion cost.

### Additional medium residual control

After observing the timeouts, we added residual(8,2,4,depth6,readX), with eight
operators, to obtain a completed comparison at an intermediate size. This is
an exploratory implementation/performance control, not a held-out prediction.

The profiled comparison at c38b2fa1 took 5.356 s for enumeration and 0.501 s for
DP, with the same nine curve points and all 18 witnesses executing exactly.
The two raw records preserve the actual graph arguments, revision and hash.
The control was then made a named runner case in 347f0029, which also added
`--no-profile`. No solver code changed between these measurements.

Three fresh-process repetitions with profiling disabled gave:

| Mode | Search times, seconds | Median |
| --- | --- | ---: |
| Enumeration | 3.581, 3.597, 3.548 | 3.581 s |
| Cut DP | 0.412, 0.415, 0.420 | 0.415 s |

The ratio of medians is **8.64x**. Every run retained witnesses, returned the
same curve, and replayed all nine witnesses correctly. This is evidence for
this residual graph, not a general speedup claim. Including the initial matrix
and both controls, 18 of 28 curve jobs completed; their 126 frontier witnesses
all replayed exactly. The remaining ten jobs are explicitly incomplete.

## Ownership projection and remaining state growth

Completed runs allow a meaningful comparison of cached state counts:

| Graph/mode | Previous key | Projected key | Reduction |
| --- | ---: | ---: | ---: |
| Small kki fork, either mode | 2,463 | 2,147 | 12.8% |
| Small residual, either mode | 807 | 662 | 18.0% |
| Depth-12 residual, DP | 10,107 | 8,677 | 14.1% |

Counts sum the completed `solve` and `group` cache entries. This optimization
reduces redundant states but does not remove exponential retention choices.

In the timed-out all-k P19 projected DP run, maximum ordinary cut width was 1,
yet the search accumulated 675,828 cached states and attempted about 9.27 million
DP transitions and 6.69 million loop choices. Its largest recorded Pareto
frontier had only 19 points. The mixed-role sample had 656,349 cached states
and maximum frontier size 21 when interrupted. Thus the bottleneck in these
observed prefixes includes the number of recursive contexts, even with narrow
individual frontiers. A graph cut crossing only X omits outer-loop reservations
of multiple unfinished outputs.

Traversal order and partial progress differ between algorithms. Cache counts
and RSS **at equal timeouts must not be interpreted as equal amounts of completed
work**, nor as evidence that either algorithm is faster or uses less memory to
finish P19. Python hash seeds and CPU affinity were not fixed; wall-time-limited
prefix counts are observations, not reproducible coverage targets.

The next justified investigation is a cache-miss breakdown by span, extents,
external reservations and ownership, followed by proved equivalence reductions
of those contexts. Tensor-name normalization would have to preserve global
input/output roles, consumer multiplicity, ownership and witness renaming.
Pruning retention subsets needs a valid dominance or lower-bound argument.
Neither reduction has been implemented or claimed sufficient here. Larger
worker counts, a native implementation and work stealing remain possible
engineering improvements after that diagnosis.

## Streaming all-plan audit

These runs used c38b2fa1, a 2 GiB address-space cap and GNU time for peak RSS.
Counts are **derivations including duplicate witnesses**, not unique schedules.
Memory contains the active recursion and current execution, without a growing
set of previously seen witnesses or an eagerly materialized plan space.

| Graph | Checked | Budget/result | Peak RSS | Failed checks |
| --- | ---: | --- | ---: | ---: |
| coupling_same_2222 | 81,726 | 60 s, timeout / partial | 12.9 MiB | 0 |
| fork_kki_2222 | 66,780 | 60 s, timeout / partial | 12.9 MiB | 0 |
| coupling_same_2222 | 175,522 | Exhausted in 117.9 s / complete | 12.4 MiB | 0 |

The complete run allowed 180 seconds, one million plans and 20 million expansion
nodes; the generator exhausted before those limits. Its process exited 0.
The two limited runs exited 2, correctly reporting incomplete coverage. The
complete coupling run contains the earlier coupling prefix; their counts must
not be added as distinct coverage. The kki graph's full space remains unaudited.
One exhaustive tiny graph does not prove all-graph execution correctness.

## Validation and reproduction

At 347f0029, 17 unit tests passed both locally and in the Linux experiment
environment. They include 480 DP/enumeration comparisons over 120 deterministic
random DAGs, conditional interfaces, multiwriter fallback, merger checks, and
full lazy/eager derivation-multiset comparisons on four deliberately tiny graphs.

Run from the repository root. Resource-capped commands require Linux. The full
initial matrix can be reproduced from c38b2fa1 with:

```sh
python3 -m research.index_coupling.bench_solver_scaling \
  --out results_scaling --revision c38b2fa1 --seconds 180 --mem-gib 6 --workers 4
```

At 347f0029 or later, reproduce the unprofiled control with the following command,
using three different output directories for independent repetitions. Reusing a
completed output directory resumes it and does not create a fresh measurement.

```sh
python3 -m research.index_coupling.bench_solver_scaling \
  --out timing_0 --revision 347f0029 --cases residual_medium \
  --variants enumerate_projected dp_projected --no-profile \
  --seconds 30 --mem-gib 6 --workers 2
python3 -m research.index_coupling.audit_all_plans \
  --only coupling_same_2222 --limit 1000000 --nodes 20000000 --seconds 180 --mem-gib 2
python3 -m unittest research.index_coupling.test_solver_scaling \
  research.index_coupling.test_p21d research.index_coupling.test_p21 \
  research.index_coupling.test_validate_constructive -q
```

The archived manifests identify the actual measured revisions; `--revision` is
a supplied provenance label, while the runner independently hashes its source.
Raw audit source-file hashes are recorded separately in `audits/provenance.json`.
