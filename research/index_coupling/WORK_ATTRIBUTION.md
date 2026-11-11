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

## 5. Attempt: share conditional partition prefixes (protocol before measurement)

The requested implementation attempt targets an intermediate response that the
current cache does not expose: the cut-DP prefix. Keep the original ordered
parent span S and the terminal cut p in its key. At that cut, preserve each
crossing tensor's keep/DRAM decision. Project extents, external residency and
owned writes onto the operators/tensors of S[:p], using the existing projection
rule. Do not merge different complete-state responses or consumer orders.

Claim: for fixed S, p and cut decisions, the prefix frontier and a valid prefix
witness depend only on this projected interface. Every transition in a partition
ending at p touches tensors of S[:p]. Its carried reservations also touch that
prefix; tensors used only later have no prefix allocation or traffic charged
here. Caller allocations remain caller-owned. Induction on p preserves the
transition costs, child group interfaces and Pareto envelope. The full span in
the key preserves crossing incidence, global writer roles and the special v2
whole-span hold branch. A backward memoized prefix recurrence can therefore
share work across otherwise distinct complete Residency/extent contexts.

This is a demand-driven implementation of joint conditional evaluation. It
does not eagerly tabulate all masks, require equality of the complete curves,
or recover witnesses by rerunning native search. The default solver is unchanged;
an opt-in AST adapter replaces only cut_dp, reusing the original group recursion,
costs and witness format. Initial scope: single-writer ordered graphs, grammar
v2, exact frontiers, no root constraints or optional canonicalization. Both tile
domains, solve/group entry, external residency and owned writes remain explicit.

Before running performance comparisons, freeze these controls:

- Native forward cut DP; backward prefix DP without context projection; backward
  prefix DP with projection. The middle arm isolates recurrence-order overhead
  from actual cross-context reuse. Also compare the existing unit-M substitution
  with full witness expansion, and its combination with the same prefix adapter.
- M8 FFN-1 and M8 FFN-2 are primary; tiny FFN-4 and mixed-role fork kki are
  controls. Do not enlarge cases after a negative result to rescue the headline.
- Complete root frontiers must agree. Replay every emitted root witness, including
  unit-form expansion. Compare with literal partition enumeration on small chains,
  forks, residuals and a branching control; exercise both entries and boundary
  contexts. A failure blocks performance claims.
- Report original solve/group misses, prefix cache entries/hits, actual partition
  transitions and Pareto candidates separately. Prefix caching need not reduce
  original whole-state misses. Count construction, queries and native-format
  witness generation together; expansion belongs inside generation for unit forms.
- Five fresh-process rounds, alternating arm order, fixed hash seed, 60 seconds
  per arm. Report median complete generation and RSS, with adapter installation
  separately. Instrumented work counts are separate from timed runs. No native
  result or archived witness is input to the new search.
- A useful primary result requires exactness and lower complete-generation time
  on both M8 cases, with construction/replay costs visible. A win only over the
  unprojected prototype is not a win over native. Freeze implementation before
  these rounds; retain all measurements and do not start another algorithm if
  the experiment fails.

Implementation note before timed rounds: both backward arms cache the cut
transition skeleton by parent span, cut, shared-tensor residency and terminal
bits. Tensor incidence determines that skeleton; extents, private-weight
residency and ownership remain inputs to numeric prefix/group evaluation.
This hoists repeated decision-dictionary construction out of numeric states.
The projection-off control includes this same structural cache. Small oracle,
boundary-contract and replay checks precede the frozen timing run; their work
counters are not speedup measurements.

### Completed result: modest positive full-root M8 acceleration

Protocol `e116c2a3`, implementation frozen at `e7dc2720`. The default
`graph/curve.py` is unchanged. `response/prefix.py` installs the opt-in
recurrence; `response/bench_prefix.py` runs the frozen five arms. Artifacts:
[results/prefix_sharing/](results/prefix_sharing/), including 100 uninstrumented
timing records, 20 separate work records, source hashes and a recomputable summary.
All executions are sequential fresh Python 3.10.12 processes on the same Linux
server, with hash seed 0, alternating arm order, 60-second/6-GiB limits per arm.
No arm times out. No implementation change follows the timing freeze.

The 38 distinct complete root frontier points agree across all five methods.
**1,140/1,140** root witnesses replay with exact traffic, peak and numerical
execution. The prefix-only arms emit native notes directly: no placeholders,
recovery solver or archived witness is used. The two unit-form arms include
their usual native expansion in generation. Six targeted test methods cover
literal partition enumeration, solve/group entry, external/internal residency,
ownership, skipped-live-interval gaps, both tile domains, bounded capacity,
spill options, unsupported guards, and unit-form composition. The local run
also passed the seven existing unified-search tests; the six targeted methods
passed again on the execution server before benchmarking.

Five-round median **complete root mapping generation**, milliseconds:

| Case | Native | Prefix, projection off | Prefix, projection on | On / native speedup | Existing unit forms | Unit + prefix |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| M8 FFN-1 | 64.67 | 51.63 | **46.96** | **1.38×** | 80.56 | 67.26 |
| M8 FFN-2 | 312.35 | 248.77 | **197.71** | **1.58×** | 320.71 | 238.03 |
| Tiny FFN-4 | 3,989.49 | 3,012.93 | 1,071.12 | 3.72× | **562.92** | **559.35** |
| Mixed fork kki | 92.88 | 67.90 | **50.88** | **1.83×** | 95.89 | 53.89 |

Installation and independent replay are separate from generation, as frozen.
Prefix adapter installation costs about 13 ms. **Including installation**, the
two M8 comparisons are 64.67→59.88 ms (**1.08×**) and 312.35→210.30 ms
(**1.49×**). Installation-inclusive control speedups are 3.68× and 1.46×.
Replaying every root point takes another 124–128 ms for M8-1 and 261–277 ms
for M8-2 across the three native/prefix arms; it is validation, not free work
included in the claimed generation ratios. Raw ranges are retained: native /
shared generation is 63.85–70.33 / 46.05–47.30 ms for M8-1, and
311.16–314.45 / 196.06–199.61 ms for M8-2.

The gains have two sources, and must not all be assigned to projection.
Backward evaluation, one final union prune per prefix, and cached structural
transitions give 1.25× on both M8 cases **without** cross-context projection.
Turning projection on gives a further **1.10× / 1.26×** over that control.
The frozen combined implementation, rather than projection alone, achieves
the 1.38× / 1.58× comparison with native.

| Work counter | M8-1 native → shared | M8-2 native → shared |
| --- | ---: | ---: |
| Complete solve/group misses | 2,108 → **2,108** | 6,176 → **6,176** |
| Loop choices | 5,578 → **5,578** | 15,636 → **15,636** |
| Partition transitions | 3,770 → **2,582** (−31.51%) | 22,124 → **12,952** (−41.46%) |
| Pareto candidates | 30,687 → **19,922** (−35.08%) | 218,960 → **106,845** (−51.20%) |
| New cached prefix entries, projection off → on | 2,034 → 1,326 | 8,430 → 4,418 |

The original complete responses still differ and are still constructed. What
is shared is a sufficient intermediate response in their construction. This
answers the earlier all-parent problem without removing one parent's edge:
every caller of a projected prefix uses the same cached result. It is not a
new equality between entire Residency curves, nor a reduction in original
loop-choice count. The prefix cache is **additional** retained state; its
entries must not be presented as a smaller replacement for the native cache.

That extra storage is visible. Native→shared peak pre-replay RSS is
20.25→22.91 MiB (M8-1), 27.19→35.82 MiB (M8-2), 40.12→77.12 MiB (tiny), and
20.06→23.06 MiB (fork). Projection-off tiny reaches 149.06 MiB. Existing unit
forms remain much faster and smaller on the tiny control. Combining reductions
is not automatically beneficial: unit+prefix still loses to native on M8-1.
No default dispatcher or automatic portfolio rule is inferred from these cases.

For fixed parent span S and cut p, the new key keeps the full S and boundary
bits but only prefix-used extents and resident/owned identities. Consequently,
changes confined to future private weights or future-only rank extents do not
multiply prefix construction. Full-span responses can still require all their
distinct masks: there is **no polynomial-in-graph-size bound** or general-DNN
scaling result here. The result is an executable, measured instance of sharing
construction across different conditional responses, with a memory tradeoff.

The predeclared primary criterion is met. Keep this as an opt-in result and
retain the previous failed fixed-loop, closure and curve-shift experiments;
this experiment does not reclassify them or justify expanding the search grammar.

```sh
python3 -m unittest research.index_coupling.test_prefix_sharing -v
python3 -m research.index_coupling.response.bench_prefix run NEW_DIRECTORY --revision YOUR_SOURCE_COMMIT
```

For a single native-format query:

```python
from research.index_coupling.response.prefix import make_kernel
solver, _ = make_kernel(projection=True)
points = solver(graph, witness=True, partitions='dp', scalar_leaf='v2')
```

## 6. Continuation: quotient parent frames (protocol before measurement)

The user requests further improvement of the successful prefix-sharing route.
This continuation changes only which parent frames can share a prefix. Let
P=S[:p]. Replace the complete parent-span identity in the prefix cache by:

    (P, B_exit, later_writers, whole_parent)

Here B_exit is the original parent cut's crossing tensor set (including caller
residents, whose decisions are subsequently projected), later_writers records
which tensors touched by P have their writer later in S, and whole_parent
distinguishes p=len(S) from a proper prefix. Numeric extents, Residency,
Ownership and terminal keep/DRAM bits keep their existing projected semantics.

Sufficiency argument: for any earlier cut j, the original crossing set is
exactly tensors(P[:j]) intersect (tensors(P[j:]) union B_exit). First-use and
within-prefix writer positions follow from P. A writer later than p can affect
read/write classification but cannot fall inside any prefix group; its identity
flag suffices. Global produced/consumed roles stay fixed in the graph closure.
The whole_parent bit preserves v2's whole-span scalar-hold versus proper-group
entry. Thus all prefix transitions, capacities, traffic and native notes agree
for equal frames. Intern one representative parent per frame and reuse the
existing implementation; do not equate full graph responses or change loops.

The implementation must keep the old projected-prefix method as a control and
remain opt-in. No timing-based dispatcher or default-core change is authorized
by this experiment. Prove/test the frame conditions, including differing exit
sets and the scalar-entry bit, before freezing code and measuring performance.

Frozen measurements for this continuation:

- Same four established cases, plus two specified holdouts: FFN-2 at M=16,
  d=4,f=8 and FFN-3 at M=8,d=4,f=8. These separately increase row extent and
  chain length; no post-result replacement or enlargement of cases.
- Five arms: native, previous projected-prefix, frame-quotiented prefix,
  existing unit forms, unit forms plus frame-quotiented prefix.
- Five fresh-process rounds, alternating order, fixed hash seed; one separate
  instrumented round; 60 seconds and 6 GiB per worker. Every complete root
  witness is replayed. Failures/timeouts remain results, never passes.
- Report complete generation, installation, replay, RSS, original state and
  loop counts, partition work, numeric prefix-cache size and frame aliases.
  The new method must beat the previous prefix control on both established
  M8 cases to establish an incremental performance win; holdouts are reported
  even if negative. Memory reduction is a prediction to check, not an assumption.
- No native/archived answer enters the new recurrence. Keep all old frozen
  results intact. Stop at this bounded continuation rather than widening its
  frame signature or changing test cases after timing results.

### Completed result: useful on longer spans; negligible on one-layer M8

Protocol `10e5b381`, implementation frozen at `02867737` before performance
measurement. [results/prefix_frames/](results/prefix_frames/) contains 150
uninstrumented timing records, 30 separate instrumented work records, the
manifest and a recomputable summary. All six cases and five arms complete
under the frozen limits on the same Linux/Python 3.10.12 server as section 5.
All 11 manifest source hashes match the frozen commit. No implementation or
case change follows measurement. The nine targeted tests cover the earlier
contracts plus parent aliases, distinct exit sets, scalar-entry distinction,
future-writer classification, and composition with unit forms. The artificial
non-topological writer test compares grammar costs only; it is not claimed as
an executable DAG example.

**All 73 distinct complete root frontier points agree; 2,190/2,190 repeated
root witnesses replay exactly.** Prefix arms return native witnesses directly,
with no recovery search. Unit-form arms include expansion. Five-round median
complete mapping generation, milliseconds:

| Case | Native | Previous prefix | Parent-frame prefix | New / native speedup | Previous / new speedup | Unit forms | Unit + frames |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M8 FFN-1 | 64.53 | 46.64 | 46.25 | 1.40× | 1.008× | 81.12 | 67.81 |
| M8 FFN-2 | 312.97 | 197.38 | 188.37 | 1.66× | 1.048× | 320.26 | 229.12 |
| Tiny FFN-4 | 3,990.76 | 1,070.25 | 732.94 | 5.44× | 1.460× | 561.62 | 557.74 |
| Mixed fork kki | 92.44 | 50.86 | 51.04 | 1.81× | 0.996× | 94.69 | 54.18 |
| Holdout M16 FFN-2 | 441.02 | 286.39 | 262.32 | 1.68× | 1.092× | 476.89 | 329.48 |
| Holdout M8 FFN-3 | 2,526.74 | 1,153.81 | 954.09 | 2.65× | 1.209× | 2,257.52 | 1,077.40 |

Both established M8 medians beat the previous-prefix control, meeting the
literal predeclared criterion, but **M8-1 does not establish a robust additional
speedup**: previous/new ranges are 46.25–46.86 / 45.77–48.31 ms. Its 0.8%
median difference is smaller than run variability. M8-2 ranges do separate:
196.65–198.65 / 185.92–189.55 ms. The two holdouts also separate:
283.88–287.61 / 260.53–263.38 ms and 1,147.34–1,161.60 /
945.69–970.10 ms. Fork slightly regresses; it is retained as a negative
incremental result. Existing unit forms remain better on tiny FFN-4. These
observations do not define an automatic dispatcher.

Adapter installation remains separately timed, about 13 ms. Including it,
new generation is 59.52 / 201.74 ms on M8-1/2 (**1.08× / 1.55×** native),
275.67 ms on M16-2 (**1.60×**), and 967.02 ms on M8-3 (**2.61×**).
Independent executor validation is excluded from generation: its medians for
the new arm are 126.2 / 260.8 / 643.5 / 418.7 ms on those four cases. Raw
records report it separately; neither witness generation nor AST installation
is being mistaken for replay.

| Construction work | Native | Previous prefix | Parent-frame prefix |
| --- | ---: | ---: | ---: |
| M8-1 partition transitions | 3,770 | 2,582 | 2,486 |
| M8-2 partition transitions | 22,124 | 12,952 | 11,416 |
| M8-2 Pareto candidates | 218,960 | 106,845 | 98,097 |
| M16-2 partition transitions | 29,184 | 17,028 | 14,988 |
| M16-2 Pareto candidates | 329,879 | 164,535 | 151,622 |
| M8-3 partition transitions | 204,350 | 84,030 | 62,802 |
| M8-3 Pareto candidates | 2,650,082 | 857,954 | 696,812 |

Original solve/group misses and loop choices remain identical across the
native and two prefix-only arms in every case. For M8-1/2, M16-2, M8-3,
the counts are respectively 2,108/5,578; 6,176/15,636; 8,015/23,881; and
14,336/40,829. The result shares intermediate construction across parents,
not whole conditional responses, and does not remove loop enumeration.

| Case | Numeric prefix entries, previous → new | Proper parent keys → frame classes | Peak RSS MiB, native / previous / new |
| --- | ---: | ---: | ---: |
| M8 FFN-1 | 1,326 → 1,230 | 4 → 3 | 20.25 / 23.08 / 22.89 |
| M8 FFN-2 | 4,418 → 3,818 | 35 → 15 | 27.19 / 36.12 / 34.91 |
| Tiny FFN-4 | 14,706 → 8,918 | 286 → 66 | 40.31 / 77.24 / 60.33 |
| Mixed fork kki | 1,778 → 1,703 | 10 → 6 | 20.25 / 23.14 / 23.02 |
| Holdout M16 FFN-2 | 5,766 → 4,974 | 35 → 15 | 30.56 / 42.25 / 40.26 |
| Holdout M8 FFN-3 | 13,606 → 9,994 | 120 → 36 | 48.75 / 83.26 / 72.91 |

The memory prediction holds in these measurements relative to the previous
prefix implementation; memory still exceeds native. Numeric prefix entries
are additional to the original response caches. Frame aliases are counts of
structural parent keys merged, not removed complete solver states.

There is a simple structural explanation for the chain-length trend. In an
adjacent-activation chain with private weights and topological order, a proper
prefix [i,j) of parent [i,k) has the same exit tensor for every k>j, and no
future writer. Thus its parent-frame class depends on (i,j), not k. Across
all contiguous spans, the number of potential proper parent/cut keys is
binomial(n+1,3), while the number of frame classes is binomial(n,2). The
observed counts for 3, 6, 9 and 12 operators are exactly 4→3, 35→15,
120→36 and 286→66. This is a bound on the **structural frame dimension
only**. Extents, resident/owned identities, boundary decisions and Pareto
frontier size still multiply numeric work; no polynomial bound for complete
mapping search follows. It explains why longer spans expose more reusable
construction without assuming their complete responses are equal.

Keep the implementation opt-in (`make_kernel(projection=True, frames=True)`),
preserve the old control, and stop this bounded continuation here. The default
core and mapping grammar remain unchanged. The holdouts provide evidence of
benefit beyond the original two M8 cases, not general-DNN or hardware speedup.

```sh
python3 -m unittest research.index_coupling.test_prefix_sharing -v
python3 -m research.index_coupling.response.bench_prefix_frames run NEW_DIRECTORY --revision YOUR_SOURCE_COMMIT
```
