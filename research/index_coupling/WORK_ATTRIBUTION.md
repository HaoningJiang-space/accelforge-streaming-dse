# Where the exact solver's work goes, by graph family

State counts (REDUNDANCY_RESULTS.md) do not show where the time goes. This
study attributes each cache miss's **exclusive** work (its own DP transitions,
loop choices, Pareto candidates and time, minus those of child misses) to its
response stratum. It also counts every group query, hit or miss, that returns
an empty frontier.

Source `attribute_work.py` (`6700107a`) and `live_profile.py` (`72f83342`).
Records are in [results/work_attribution/](results/work_attribution/). All 49
cases are complete: the 47 census cases plus re-runs of same6/mixed6. Fresh
Linux processes, hash seed 0, exact cut DP, halving tiles, and no optional
reductions. Each case had at most 600 s, 6 GiB (RLIMIT_AS) and four workers.
Instrumentation slows the runs, so the times are relative only.

Strata, exactly one per miss:

- `empty`: no frontier point.
- `zero_at_d`: the single point (d, 0), with d the per-operator operand bound.
- `zero_above_d`: a single point (c, 0) with c > d. Extra traffic is zero, but
  the capacity is not at the operand bound.
- `rest`: everything else.

`repeat` additionally flags misses whose remainder-graph label
(`sufficient_stat`, residual_domain) was already seen. It approximates what an
isomorphism-keyed cache would reuse. A WL label is a proxy here, not a key.

## 1. Results

Share of exclusive DP transitions plus loop choices:

| Case | total | empty | zero_at_d | zero_above_d | rest | repeat | empty group calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fork 6, same role | 1,800,817 | 0 | 0.2% | **93.0%** | 6.8% | 6.5% | 15% |
| fork 6, kkkiii | 1,800,817 | 0 | 0.2% | **93.0%** | 6.8% | 2.4% | 15% |
| fork kkk, extents 4 | 74,023 | 0 | 0.7% | 30.3% | 69.1% | 10.3% | 4% |
| FFN forward 4 layers | 598,854 | 0 | 0 | 0.5% | **99.5%** | 4.3% | **53%** |
| attention forward 4 layers | 598,854 | 0 | 0 | 0.5% | **99.5%** | 4.3% | **53%** |
| FFN training 1 layer | 593,181 | 0 | 4.2% | 11.6% | **84.3%** | 2.4% | 35% |
| residual depth 24 | 832,369 | 0 | 4.4% | 4.8% | **90.8%** | **42.1%** | 3% |
| residual (4,4,8) depth 8 | 66,590 | 0 | 0 | 10.9% | 89.1% | 18.6% | 4% |
| ancestor k=8 | 41,297 | 0 | 0 | 7.4% | 92.6% | **99.3%** | 0 |

Two more observations:

- **What the work is.** In FFN-4, the 5,158 `rest` misses carry 590,626 DP
  transitions but only 5,531 loop choices. The cost there is cut-DP work over
  long spans, repeated across many (extents, residency) contexts.
- **How many tensors are live.** Among `rest` states, the share with at least
  three locally live nonscalar tensors is 93% (fork6), 97% (FFN-4), 91%
  (training), 99.5% (residual depth 24) and 100% (ancestor). The two-live
  normal form (ONE_OBLIGATION_RESULTS.md §3) covers k ≤ 2 only.

## 2. Reading

1. **Empty and lower-bound states cost almost nothing themselves.** They stop
   at a leaf or have no loop candidates. What they cost is the callers'
   transitions into empty groups: 53% of all DP transitions in the 4-layer
   stacks, 35% in training, 15% in the forks. Lemma 2 can skip these before
   the call. Each such transition is cheap (a cached lookup), so the time
   saved must be measured, not inferred from counts.
2. **The dominant mechanism depends on the graph family.**
   - *Forks*: 93% of the work is in zero-traffic states above the operand
     bound. These are the scalar-X zone, where the original scalar leaf counts
     every live scalar. A zero-traffic certificate (Scalar-X Bridge, which
     already removes 81% of transitions there) is the right tool.
   - *Repeated rank variables* (the residual chain, the ancestor control):
     isomorphism reuse covers 42% to 99%.
   - *Layered stacks with distinct rank variables* (FFN, attention, training):
     neither applies. Over 99% of the work is in nontrivial states, mostly
     with three or more live nonscalar tensors, and only 2-4% repeats a
     remainder.
3. **Analytic responses for the stacks need multi-tensor theory.** No
   certificate proved so far reaches the states that dominate the stacks'
   work. Two-live covers k ≤ 2, and the three-tensor counterexample already
   shows that single-axis obligation counts are insufficient.

## 3. Limits

- Exclusive counters attribute a transition to the state performing it, not
  to the child it queries.
- A WL `repeat` can over-merge non-isomorphic remainders. It is used here only
  as an estimate.
- Instrumented timings are relative only.
- Same grammar scope as REMAINDER_LEMMAS.md.

## 4. Root-wide conditional families after the fixed-loop stopping decision

This continuation uses the existing **v2** C2 call archives for M8 FFN-1,
M8 FFN-2, tiny FFN-4 and FFN training-1. It is a retrospective attribution,
not a frozen prediction, new solver or continuation of M-to-one optimization.
Do not pool its counts with the earlier 49-case study above. Source:
`response/root_work.py`; artifacts: `results/root_work/final/` and
`results/root_work/provider_cost/`.

Every node keeps its full (entry, ordered span, extents, external residency,
ownership, constrained) interface. For reporting only, nodes are bucketed by
(entry, span length, extent of the named M rank, chain-recognizer result).
Those buckets do **not** imply state equivalence. Each archive's node work
must sum exactly to its original four counters; all nodes must be reachable.
All incoming edges are classified as a rank/tile loop, whole/proper partition,
or scalar group-to-solve redirect, retaining both distinct edges and call counts.

For a proposed whole-state replacement set T, compute reachability while
treating every member of T as a terminal. The old work removed comprises
the reached terminals' own work plus descendants made unreachable. Incoming
paths to the same complete state all use that replacement. This differs from
deleting just one parent's call to a child that remains needed elsewhere.
Replacement construction and witness work are **not** included in that old
work and cannot be assumed free in a speedup claim. The archives have work
counters, not calibrated exclusive wall time for each current state family.

### What remains after the existing unit-M solve guard

The first control replaces all states accepted by the current unit-M chain
solve guard at zero cost. This is an attribution reference; measured online
unit-M construction/recovery is already reported in §16a of
CONTRACTION_ORACLE.md and is not free.

| Case | Original DP work removed by free unit-M replacement | Multi-op M>1 solve share of remaining DP | Same share of remaining Pareto candidates | Singleton group share of remaining loop choices |
| --- | ---: | ---: | ---: | ---: |
| M8 FFN-1 | 29.12% | **82.37%** | 56.82% | **66.49%** |
| M8 FFN-2 | 31.54% | **92.99%** | 79.82% | **52.67%** |
| Tiny FFN-4 | 99.84% | 86.65% | 33.45% | 9.39% |

Tiny's percentages describe its small residual, not its original work.
M8 has two different hotspots: multi-operator solve states perform most
remaining partition/Pareto work, while singleton groups perform many loop
choices. A single percentage cannot combine their operation costs.

For M8-1, three-op solve states at M=2 and M=4 each account for 25.30% of
residual DP transitions. There are 52 complete states in each family;
52/52 and 48/52 respectively have multiple parents. The M=2 family receives
117 distinct M:4->2 edges, 52 M:8->2 edges and 156 F0-loop edges. These
are conditional states shared across row and feature-loop paths.

For M8-2, the analogous three-op families each contribute 14.42% of residual
DP work, with 168 complete states each. All 168 M=2 states have multiple
parents, receiving 378 M:4->2 edges, 168 M:8->2 edges and 396 feature-loop
edges. The five-op families at M=2/4 each contribute another 8.66% of
residual DP work; their different source structure is retained in the records.
This identifies the expensive interfaces; it supplies no cheap constructor
for their complete responses.

Training is an important control: the **current chain recognizer** accepts
no unit-M chain states in this graph. Five-or-more-op solve spans at named
M=1 carry 81.75% of its DP work. Thus the difficult interface is not defined
by M>1 alone. Shared weights, dependencies and the recognizer's whole-graph
row-rank/private-weight requirements matter. This result is not a proof that
every training subspan lacks an analytic representation.

### Existing response providers: coverage and construction are separate

The audit also recognizes singleton dense contractions with three pairwise
tensor ranks, preserving input/output roles and resident identities. Their
solve/group responses coincide and can use the existing keep-level model.
This is different from the multi-operator segment macros corrected in §21.

| Case | Free unit-M + singleton replacement: original DP removed | Original loop choices removed | DP increase beyond unit-M alone |
| --- | ---: | ---: | ---: |
| M8 FFN-1 | 40.50% | 69.13% | 11.38 percentage points |
| M8 FFN-2 | 35.96% | 57.29% | 4.42 percentage points |
| Tiny FFN-4 | 99.86% | 18.07% | 0.02 percentage points |
| FFN training-1 | 0.037% | 3.25% | 0.037 percentage points |

These are hypothetical zero-cost terminal substitutions, not time savings.
They neither certify a new multi-op M>1 response nor revive per-edge pruning.
The top three residual families for each of the four work counters also get
free-terminal what-if records, clearly marked hypothetical. Different
families' eliminated-work percentages cannot be added because descendants
can overlap. Complete top-state interfaces and all parent IDs are archived.

To test whether the available singleton provider is actually cheap, a fresh
process constructs each distinct key requested at the boundary of the
unit-M/singleton replacement set once, using unmodified `keep_level.curve_of`.
Each generated frontier is checked against every matching archived singleton
state, preserving roles and both entries. Each case has a 30-second process
limit; all four finish. A native full-root witness-generating run in the same
process provides a diagnostic time reference and matches the archived curve.

| Case | Distinct requested singleton keys | Numeric response construction | Native full-root generation | Matched archived states |
| --- | ---: | ---: | ---: | ---: |
| M8 FFN-1 | 120 | **1.933 s** | 0.051 s | 464 |
| M8 FFN-2 | 220 | **2.298 s** | 0.251 s | 1,360 |
| Tiny FFN-4 | 12 | 0.00492 s | 3.311 s | 174 |
| FFN training-1 | 64 | 0.00760 s | 3.647 s | 656 |

These are one-run construction diagnostics, not repeated speedup benchmarks.
The provider times exclude import, recognition, comparison and witness cost;
the native time includes its emitted witness but excludes replay. No new
witness recovery is implemented, so its cost is recorded as unknown, not zero.
The singleton constructor already costs more than the M8 roots before
recovery. Its keep-level implementation enumerates keep orders/tile states
and scans capacity; a mathematical model need not be a cheap constructor.
This rejects the current implementation as a direct whole-family substitution,
not all possible singleton algorithms. Tiny has little incremental work to
remove, and the cheap training singleton provider covers little of its work.

Current applicability ledger:

- Unit-M solve forms: existing guarded provider and measured implementation;
  already explains the tiny positive result, but misses the dominant M8 family.
- Singleton keep-level response: broad loop-work coverage in M8, with an
  existing constructor that fails the measured cost check above.
- Multi-op M>1 complete responses: expensive and shared; no established cheap
  full-interface provider is identified by this audit.
- Fork permutation quotient: its all-order, exchangeable-consumer premise
  does not license merging fixed-order chain states.
- Native resource-effect summaries: a different representation/grammar;
  no demonstrated adapter makes them complete responses for these interfaces.

### Decision and the separate FFM baseline

This completes root-wide prioritization without introducing another symbolic
solver. No examined family combines large remaining work coverage with a
demonstrated cheap complete response and executable witness construction.
Do not infer impossibility from that absence, but do not open another solver
project on the basis of zero-cost coverage either.

Demand-driven native candidate generation is a separate practical candidate
for the next **audit**, not an implementation started here. Its baselines
must include the existing [Event/cache audit](../tracking_audit/results/event_join_audit/README.md)
and [finite-domain generation](../joint_search/results/stage02/README.md).
Those historical records use native FFM, not this graph grammar, and include
real reuse; they are not fresh performance evidence for the current checkout.
The Stage 0-2 gate already reduces preparation while increasing expansion
and Join work relative to Events. Simply introducing another shared generator
would not establish demand-driven reduction.

An upstream demand filter must preserve the declared target policy's candidate
coverage, integer resource accounting, compatibility and ordered fallback/
prefix-Pareto behavior. Equal final frontiers alone missed the historical
68-byte coverage regression. Require per-template policy Tile coverage or a
proved continuation-preserving deletion, plus construction, Join and complete
mapping costs against the strong baseline. No new performance claim or hardware
validation follows from this root-work audit.

```sh
python -m research.index_coupling.response.root_work NEW_DIRECTORY
python -m research.index_coupling.response.root_work providers NEW_PROVIDER_DIRECTORY
```

### Interpretation: minimizing contexts is different from serving contexts

For a fixed parent loop, let `x` denote its new retention decisions. Its
extra-traffic response is

    F_parent(C) = min_x [d_parent(x) + r_parent F_child(x)(C-a_parent(x))].

The fixed-row-loop joint DP exactly reorganizes this minimization. It need
not construct every `F_child(x)`: it can return the parent's envelope and
the winning choices. That is useful, but this envelope does not in general
determine the individual conditional responses. Taking a minimum loses
alternatives that another parent, with different reservations, trip count,
or admissible contexts, may need. Replacing all those child queries therefore
requires a response representation that preserves their complete interfaces,
or a separate proof that the discarded alternatives cannot help any remaining
caller. The branch proof alone supplies neither. This is also why a direct
witness constructor, while necessary to remove recovery search, would not
by itself invalidate the zero-unreachable-M8-states branch experiment.

Three distinctions prevent the diagnosis from becoming an impossibility claim:

- Different curves do not imply that their construction cannot share work.
  The failed shift/additivity tests exclude those representations, not every
  conditional representation or exact algorithm.
- The archived call DAG belongs to the current recurrence implementation.
  Reachability after removing edges measures that intervention, not work that
  every future algorithm must perform. Memoization already serves a complete
  state once; deleting another route to it is not a second cache-miss saving.
- M>1 is a useful label for these forward-chain hotspots, not a universal
  hardness criterion. The training control's costly M=1 states already
  preclude that inference. The M8 native full roots
  here take about 0.05/0.25 seconds in the one-run diagnostic; their failure to
  benefit from a replacement is not a measured large-DNN scaling law.

There is no unexploited quadratic sibling-frontier merge in the current core:
`graph/curve.py::merge_staircases` already combines serial peak-capacity/summed-
traffic responses in linear time in the two frontier lengths. More general
candidate construction and pruning still cost work, but this particular
algebraic shortcut is already present.

Thus the outstanding concrete target is the complete multi-op conditional
`solve` response shared by M=2/4 and feature-loop parents, with executable
witness decisions produced during construction. The required net comparison
is old work actually removed versus **construction + all remaining queries +
witness construction**, alongside any changed caller work. Counters locate
that target; they do not establish that a cheap exact constructor exists.
This interpretation introduces no new solver, experiment, or speedup claim.
