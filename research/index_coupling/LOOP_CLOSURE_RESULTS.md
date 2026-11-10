# Factorized loop closure: exact, but the bounded pilot stops

The frozen continuation gate failed. Full loop closure preserves every tested
root frontier and directly produces executable native witnesses, but makes
both M8 workloads slower. Small Pareto label sets per state pair are not
enough: this representation retains many destination-specific summaries,
enumerates the same loop actions, and adds label construction costs.

The [protocol](LOOP_CLOSURE_PROTOCOL.md) was committed and pushed as
`23095cc9` before measurement. No default solver was changed. The experiment
ends here under its predeclared rule; larger shapes, deeper windows or extra
optimizations were not added to rescue the result.

## 1. Exact factorization with proper partitions

Define P(s) as the response of stopping the pure-loop prefix at s:

- proper partitions, which call the **group** interface for each child;
- the scalar leaf and whole-scalar-hold alternatives permitted by v2;
- no non-scalar whole-span group, since that would continue the loop prefix.

For a non-scalar group state s,

    G(s)(C) = min over reachable t and (A,D) in L[s,t]
                 D + R[s,t] P(t)(C-A).

For solve entry, include P(s) as well as G(s). Scalar group entry redirects
to solve, whose response is already P(s). The multiplier telescopes with
extent ratios and the prefix label set is Pareto(A,D).

To prove equivalence, cut an original plan at its first non-loop choice.
Its prefix is represented by a label and its first proper partition or leaf
belongs to P(t). Conversely, a legal prefix followed by P(t) is a legal plan.
Dominating labels can be removed because suffix responses are nonnegative
and capacity-monotone. Loops strictly shrink extents, so this decomposition
terminates. Crucially, stopping at every intermediate P(t) preserves choices
to partition before the entire nest becomes scalar.

[loop_closure_pilot.py](loop_closure_pilot.py) adapts `graph/curve.py` in
memory. It copies the existing partition recurrence, removes only the
non-scalar whole-span transition from P, and uses the original ownership,
reservation and group-entry semantics for all proper partitions. Structural
label summaries and resource responses have separate caches and counters.
The pilot rejects options outside the frozen grammar.

Only surviving suffix labels are composed. The implementation never expands
all raw loop paths. Each retained label has one representative native prefix;
it is concatenated with a native P witness. There is no baseline-solver call
to recover a placeholder witness.

## 2. A: label growth is small per pair, but there are many pairs

| Case | Depth | State pairs | Retained labels | Maximum labels per pair | Raw paths, counted by DAG DP |
| --- | --- | ---: | ---: | ---: | ---: |
| M8 FFN-1 | 2 | 14,842 | 14,842 | 1 | 27,730 |
| | 3 | 18,781 | 19,825 | 5 | 91,156 |
| | 4 | 18,781 | 20,587 | 5 | 221,508 |
| | full | 18,781 | 20,631 | 6 | 740,960 |
| M8 FFN-2 | 2 | 38,298 | 38,298 | 1 | 72,373 |
| | 3 | 47,244 | 49,702 | 5 | 224,828 |
| | 4 | 47,244 | 51,290 | 5 | 526,475 |
| | full | 47,244 | 51,378 | 6 | 1,681,173 |
| FFN training | full | 34,332 | 34,332 | 1 | 49,272 |
| Mixed-role Fork | full | 4,463 | 4,463 | 1 | 7,457 |

Depth 2 reproduces every previous census pair/label/path count. Training and
Fork also ran at depths 2, 3 and 4; their retained sets stabilize at depth 3.
Full closure recovers both incomparable labels `(5,0)` and `(3,4)` in the
`(M,D,F)=(4,1,4)` control.

These label maxima are observations on the bounded sample, not a size bound
for general graphs. Raw path counts describe the represented set; neither
the old solver nor this prototype explicitly enumerates all those paths.

Full all-start closure construction takes about 0.040/0.096 seconds for the
two M8 cases, excluding action recovery and archive loading. Full closure can
be cheaper than depth-4 closure here: the bounded implementation caches
`(state, remaining depth)`, whereas full closure caches each structural state
once. This difference is included in the construction counters. Census peak
RSS includes the loaded call archive and should not be confused with online
solver RSS below.

## 3. B: correctness and complete native witness generation

All five cases have the same root frontier as baseline. The factorized
kernel's **49/49 distinct case/frontier points** replay exactly:

- M8 FFN-1: 14;
- M8 FFN-2: 15;
- FFN training: 13;
- mixed-role Fork: 4;
- incomparable-prefix control: 3.

Benchmark witness runs repeat these checks, without counting repetitions as
new independent cases. Native witnesses are generated during the search;
replay is validation outside the generation timer. This pilot therefore
measures both frontier-only search and witness-bearing mapping generation.
It does not retroactively change the earlier unit-M 6.81x result, whose
published timing excludes native witness recovery.

The completed run contains 17 census jobs, 10 validation jobs and 48 timing
jobs. All 75 complete within the 120-second/2-GiB per-process limits. Each
timing is a fresh process, with fixed hash seed, three repetitions and
alternating baseline/factorized order. Kernel installation is recorded
separately; import, installation and executor replay are outside the reported
search/generation time. These are local CPU feasibility measurements, not
hardware execution latency or a statistical performance study.

| Case | Frontier search, baseline → closure | Native mapping generation, baseline → closure | Mapping-generation speedup |
| --- | --- | --- | ---: |
| M8 FFN-1 | 0.0526 → 0.0924 s | 0.0617 → 0.1006 s | 0.613x |
| M8 FFN-2 | 0.2577 → 0.3682 s | 0.3019 → 0.4153 s | 0.727x |
| FFN training | 4.0201 → 4.1226 s | 4.5164 → 4.4626 s | 1.012x |
| Mixed-role Fork | 0.0831 → 0.0889 s | 0.0916 → 0.0943 s | 0.972x |

Values are medians. The tiny training difference is not a convincing speedup
from three runs. Witness-bearing peak RSS increases from 22.1 to 31.8 MiB
and from 30.0 to 49.8 MiB for the M8 cases. Memory stays within the frozen
2x ratio gate; the required 20% time reduction fails on both M8 cases and in
both timing modes.

## 4. Work removed, work retained, and work added

These are measured online counters in frontier-only mode:

| Case | DP transitions, baseline → closure | Loop choices | Ordinary Pareto candidates, baseline → closure | Added label candidates |
| --- | --- | ---: | --- | ---: |
| M8 FFN-1 | 3,770 → 2,801 | 5,578, unchanged | 30,687 → 22,532 | 64,474 |
| M8 FFN-2 | 22,124 → 19,275 | 15,636, unchanged | 218,960 → 198,028 | 157,888 |
| FFN training | 576,984 → 569,081 | 20,881, unchanged | 1,982,551 → 1,966,021 | 48,052 |
| Mixed-role Fork | 10,700 → 9,785 | 2,487, unchanged | 31,084 → 28,972 | 6,641 |

The prototype genuinely removes some original partition and response work.
It does not remove the original set of loop choices. Added label candidates
are separately reported rather than silently omitted from the work ledger.
A label operation and an ordinary frontier operation need not cost the same;
adding these counters is not an exact runtime model.

Cache accounting must likewise include the new representation:

| Case | Old F/G response misses | New F/G/P response misses | Additional structural closure rows | Retained labels across those rows |
| --- | ---: | ---: | ---: | ---: |
| M8 FFN-1 | 2,108 | 989 | 980 | 20,631 |
| M8 FFN-2 | 6,176 | 3,568 | 2,907 | 51,378 |
| FFN training | 17,225 | 16,961 | 8,506 | 34,332 |
| Mixed-role Fork | 2,237 | 1,935 | 945 | 4,463 |

For example, M8 FFN-2's new response misses comprise 126 F, 1,653 G and
1,789 P entries. Reporting only the fall from 3,144 old solve misses to 126
new solve misses would hide both the new P responses and 2,907 label rows.
These cache types represent different functions; their counts alone are
not a measure of computational savings.

## 5. Why compact labels do not produce a win here

The old response F(s)(C) already minimizes across destinations. A structural
closure retains separate information for each `(s,t)` until P(t) is known.
Thus it postpones some comparisons the ordinary conditional Pareto recurrence
has already performed. Here the new dimension is mostly the number of state
pairs, not an explosion in the number of labels within a pair.

This interpretation is supported by the unchanged action count, thousands of
extra summary rows, tens of thousands of retained labels, and measured
slowdowns. It is not a proof that all factorized representations must be
slower. In particular, this pilot retains a complete endpoint census in its
structural summaries and discards known-empty P endpoints only when composing
responses; other implementations could remove that overhead earlier. The
frozen result describes this implementation and scope, not a complexity
lower bound. Such follow-up tuning was not used to change the verdict.

The pilot stops under its protocol. The next theoretical opportunity remains
a representation that shares work across **different residency contexts**,
rather than only different paths to the same context. Any proposed
`F_{S,e,W}(C;R)` representation must specify which transition computations
can be shared symbolically, preserve identity/ownership and boundary
contracts, and charge construction of the symbolic representation itself.
Numerically equal archived curves are not a sufficient equivalence proof.
No parametric solver or new workload expansion was started in this pilot.

## Artifacts and provenance

- [run2/score.json](results/loop_closure/run2/score.json): medians, counters,
  correctness checks and the failed continuation gate.
- [run2/jobs.jsonl](results/loop_closure/run2/jobs.jsonl): all individual jobs,
  label histograms, cache statistics, resource outcomes and timing samples.
- [run2/manifest.json](results/loop_closure/run2/manifest.json): source hashes,
  Python version, hash seed and resource limits.
- Run 1 retains a control-fixture error: fresh in-memory tuple extents were
  compared to JSON-style lists. The two comparisons were normalized; no
  search or measurement rule changed. Benchmarking was correctly withheld
  until the repaired control passed in run 2.

During this work, main also incorporated the independent response-package
consolidation at `2cfca1b9`. Every source in the completed run's manifest
still matches the working tree, and the tested `graph/curve.py` hash equals
its `362e6fb9` version. The pilot does not import the renamed response modules.

```sh
python -m research.index_coupling.run_loop_closure_pilot --out NEW_DIRECTORY
```

The runner keeps every failure and partial output, fixes PYTHONHASHSEED=0,
and enforces the frozen per-job limits. Source files and historical results
outside this experiment were not rewritten.
