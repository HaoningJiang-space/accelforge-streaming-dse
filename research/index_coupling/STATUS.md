# Index coupling: current status (entry point)

**Current repository-wide assessment and priorities:**
[research/OVERVIEW.md](../OVERVIEW.md), reviewed through `2c8050c6` on 2026-11-10.
The bounded [loop-closure pilot](LOOP_CLOSURE_RESULTS.md) stopped without an M8
speedup; the latest [residency study](RESIDENCY_SHARING.md) rejects three simple
sharing structures. Consolidation takes priority over starting another solver.

The existing unit-M substitution now has complete native-witness timings:
[CONTRACTION_ORACLE.md §16a](CONTRACTION_ORACLE.md). Three fresh-process rounds
give 6.60×/6.70× on tiny FFN-4/attention-4 and 0.84×/0.97× on M8-1/M8-2,
including placeholder recovery. All 39 distinct root points agree and all
234 repeated executions replay exactly. This closes a measurement gap,
without a new optimization. Section 18 also corrects the interpretation of
the hindsight edge policy: its 35–42% DP savings are not a universal ceiling.

Bounded group-span diagnostic: [definition](FUSION_WIDTH_AUDIT.md), results
in [CONTRACTION_ORACLE.md §19](CONTRACTION_ORACLE.md). All 3,193 archived M>1
states reconstruct exactly without a size restriction. U_3 equality on
M8-2 is 2,038/2,211 overall but only 20/193 for spans longer than three ops,
covering 7.11% of that stratum's exclusive DP work. Nine framed control
executions confirm that a long common row loop can have only two child
activation cells. This completes an offline diagnosis, not a new solver.

Fixed-loop joint factorization: [proof/scope](LOOP_CONDITIONED_FACTORS.md),
[CONTRACTION_ORACLE.md §20](CONTRACTION_ORACLE.md). Conditioning on M-to-one
permits exact joint elimination of private weight choices and unit-M group
boundaries. All 36 fixed-branch frontier points match three methods, with
324 exact repeated replays. The direct capacity-sweep implementation makes
more local-factor queries than the existing cached forms: complete branch
generation is 0.52×/0.34× native on M8, and slower than forms. The bounded
pilot stops without changing the default solver or starting root integration.

This page is the index to the directory. README.md keeps the chronological record.
PROTOCOL.md holds every frozen prediction, unchanged after freezing.
Numbers below are copied from the linked result files. RESEARCH_PLAN.md and
older next-step statements record earlier stages; use the overview above for
current priorities. Historical counts are not a claim of a fresh whole-suite run.
Contract review and the existing order-completion theorem: PLAN_CONTRACT_REVIEW.md.

Remainder implementation: [REMAINDER_SEARCH_RESULTS.md](REMAINDER_SEARCH_RESULTS.md).
Exact ordered-remainder reuse (including rank restoration) and infeasible-group
pruning are now default-off core options. Exact matching rejects WL collisions;
79 tests pass, and all 64 local four-arm runs agree with 496 exact replays.
Precheck alone gives 1.31x/1.23x/1.11x median ratios on the tested forward FFN,
attention and training cases. Reuse reduces the ancestor control from 12,866
response entries to 81 and gives 4.08x, but slows the stack cases and increases
their memory. The current core hash changed; frozen archives remain intact.
Formal P19 timing subsequently completed on the DNN branch:
[pinned report](https://github.com/HaoningJiang-space/accelforge-streaming-dse/blob/5245c9cc/research/dnn_benchmarks/P19_SERVER_RESULTS.md).
All baseline/precheck attempts finish with 192 exact replays, but precheck is
15.7%/18.4% slower. All 12 remainder-containing attempts fail under the frozen
4-GiB limit. Separate profiling collection was still pending in that report.

Unified conditional search: [UNIFIED_SEARCH_RESULTS.md](UNIFIED_SEARCH_RESULTS.md).
All 24 arms of a three-switch factorial study use the same order-complete serial
grammar on a six-op partially symmetric graph with a downstream product join.
Every root frontier agrees; 1,018,272 optimized internal response records match
literal enumeration, with no missing contexts. A local scalar-shared-set and
interval-peak certificate handles non-Fork subgraphs containing F/Join and is
selected inside executed optimal whole-graph witnesses. The two nondegenerate
roots drop from 90,496/122,408 response entries to 40,472/55,462; sequential
controls give 4.74x/4.34x median time ratios. All 228 server replays are exact.
The skinny control has zero certificate hits. Memory rises slightly with the
current proof ledger; quotienting still enumerates global order representatives,
so this establishes a restricted joint method rather than general-DAG scaling.

Earlier synthesis: [RESEARCH_OVERVIEW.md](RESEARCH_OVERVIEW.md), separating exact
search reductions from capacity-dependent physical conflicts. Its proposed
next targets are historical; later closure and residency results are linked above.

Grammar v2 (opt-in `scalar_leaf='v2'`): [GRAMMAR_V2.md](GRAMMAR_V2.md),
[GRAMMAR_V2_RESULTS.md](GRAMMAR_V2_RESULTS.md). v1's mandatory multi-operator
scalar leaf breaks residency monotonicity (578 violations over about 81,000
census pairs). v2 lets all-scalar spans be partitioned, proves monotonicity
and finds 0 violations. All 291 v2 root points replay exactly, and v2 is never
worse than v1. v2 changes 19/48 root curves: every residual chain and
fork4_kkk. With X reads, residual plateaus move from 13 to 11 B. v1 stays the
default; frozen verdicts are v1 statements. Supporting analyses:
REMAINDER_LEMMAS.md, WORK_ATTRIBUTION.md and LIFT_RESULTS.md.

C2 lower-bound audit (v2, offline): [C2_BOUND_RESULTS.md](C2_BOUND_RESULTS.md).
All nine roots and six available old census counts match; 38,622 non-anchor
loop choices reconstruct exactly. The all-resident bound loses child capacity
conflicts: at the whole-root M loop of FFN-4, even the ideal incumbent can
exclude only 36/255 proper choices. Across that case the recorded-order shadow
projects 20.29% less DP work, or 20.31% with operand-slot clipping. On the
larger-extent two-layer FFN, slots skip 42.62% of choices but only 0.48% of DP
work because shared responses remain reachable. No online pruning or speedup
is claimed. The later operator bound, sandwich certificate and loop-closure
audits are summarized in [the current overview](../OVERVIEW.md#5-应停止扩展保留为边界证据的路线);
this earlier suggestion to derive another bound is no longer an active task.

Order-complete Fork symmetry: [FORK_QUOTIENT_RESULTS.md](FORK_QUOTIENT_RESULTS.md).
A separate exact quotient retains joint input/output residency profiles within
each role and reconstructs a consistent global order. Five complete reference
envelopes and 128 conditional queries agree; 685 first-study/ablation witnesses
execute exactly. The homogeneous six-consumer root drops from 106,604 reference
response entries to 6,092 quotient entries; sequential no-profile controls give
a 9.80x median time ratio. Mixed-eight and both labeled-six ablations time out
at 60 s and remain incomplete. A bound on the quotient's joint contexts is
polynomial in consumer multiplicities at fixed four-rank shape domains;
fixed-order defaults, frozen scores and general-graph claims remain unchanged.

Downstream branches: [BRANCH_SYMMETRY_RESULTS.md](BRANCH_SYMMETRY_RESULTS.md).
Whole-branch swaps survive dependent tails and a symmetric product join, but
separate residency/progress counts fail; the joint continuation types give
81→45 and 100→55 states. All 221 completed literal-order comparisons agree;
844 main executions, two component constructions and six recovery executions
are exact. An asymmetric completed prefix can leave a symmetric suffix, so
the conditional remaining graph admits more reuse than the original graph's
group. The three-branch join still times out at 60 s; exhaustive order-orbit
enumeration is not a scalable general-DAG solver. Shared multi-writer sums and
arbitrary last-use release are not covered by this pinned-input interface.

Width/stack study: [WIDTH_RESULTS.md](WIDTH_RESULTS.md). Of 34 bounded jobs,
29 complete with 146 exact replays and five time out. Fixed-width residuals
still grow superlinearly; forward stack obligation width is 2L, and valid FFN
training has cut width 5L. A separate single-op family has local obligation
width one but exactly 3^k solve keys (8/8 count predictions, 36 exact replays).
Local widths do not yet bound the number of ancestor-conditioned contexts.

P21f is complete: [P21F_RESULTS.md](P21F_RESULTS.md). All 140 arms are valid,
with 1,919 exact replays. Existence passes 32/32; the plateau prediction matches
31/32 and fails the frozen all-strata-perfect criterion. The sole counterexample
has 61/62 B plateaus; full peak reservations explain why the two-row sketch
misses it. The frozen protocol and score thresholds remain unchanged.

Complete joint residency-state census: [RESIDENCY_STATE_AUDIT.md](RESIDENCY_STATE_AUDIT.md).
Both tiny six-consumer forks have 106,604 states. The independent-solve
equivalence applies to only 4,350/58,884 states in the four dominant buckets;
X cannot become externally resident in either producer-containing whole-span
bucket. Count-profile merging outside that condition fails in 90/171 classes
(same/mixed). No optimizer or frozen P21f source is changed.

Follow-up: [SCALAR_BRIDGE_RESULTS.md](SCALAR_BRIDGE_RESULTS.md) proves an exact
one-point response for eligible coupled solve states when X is scalar but not
external. It matches 29,067 states per tiny six-consumer case; an opt-in prototype
reduces DP transitions 81.3% and cache entries 27.3%, with equal curves, 510
framed conditional executions and 56 benchmark frontier replays exact. Default
solver/P21f sources are unchanged; the outer mask enumeration remains.

Non-scalar extension: [STREAMED_BRIDGE_RESULTS.md](STREAMED_BRIDGE_RESULTS.md).
When every tensor missing an active X axis is already caller-resident, unit
streaming can lift the scalar response, subject to the original scalar-leaf
condition. All 565 eligible states in four new small censuses match, with 98
parent-frame and 69 root executions exact. Coverage is narrow: zero new hits
in either old six-consumer census and only 0.27–0.55% additional cache reduction
over Scalar-X Bridge in the new cases. This remains an opt-in fixed-order
prototype, not a solution for unresolved loop obligations.

One-obligation follow-up: [ONE_OBLIGATION_RESULTS.md](ONE_OBLIGATION_RESULTS.md).
The scalar free-retention certificate is exact: 150 matches per old census
are already covered, while ten small root cases add 276 matches and at most
0.40% cache savings over existing bridges. A separate two-live-tensor normal
form gives complete positive-traffic frontiers using retention, X blocking and
materialization/reordered loops. All 384 conditional comparisons match both
partition solvers; 720 framed executions are exact. Equal single-axis obligation
summaries can still differ once a third local tensor is present. Default solver
and frozen predictions remain unchanged.

Solver scaling implementation/results: [SOLVER_SCALING_RESULTS.md](SOLVER_SCALING_RESULTS.md).
Streaming audit exhausted 175,522 derivations on one tiny graph with no errors
and 12.4 MiB peak RSS. Cut DP gave an 8.6x median speedup on the 8-operator residual
control with equal curves; its P19 samples were incomplete at 180 s/arm.
These implementation checks do not change any frozen prediction verdict or
establish general execution-exactness.

Follow-up [SPAN_SCALING_RESULTS.md](SPAN_SCALING_RESULTS.md): conditional
independence and static cut-incidence reuse complete the two P19 samples in
240/243 seconds, equal to archived enumeration with all 32 witnesses exact.
A four-operator counterexample shows that the positions of resident private
inputs affect the frontier even at equal occupancy; resident counts alone are
not a sufficient cache key. Name canonicalization remains optional and has not
shown a consistent speed benefit. Recursive state growth remains unresolved.

## Question

Fix an operator graph, its tensor shapes and its MAC count. How much on-chip
buffer does a given DRAM-traffic budget need? How much of that is decided by the
**index relations between operators**, that is, which index each consumer of a
shared tensor contracts? The answer should not depend on a particular search
method.

Current thesis (FIRST_PRINCIPLES.md):

> 缓冲容量是在保留可复用输入与保留未完成累加之间分配；跨算子索引关系决定这些保留能否同时成立。

In English: buffer capacity is split between keeping reusable inputs and keeping
unfinished accumulations, and the index relations between operators decide
whether both can be kept at the same time.

## Prediction ledger

| ID | Claim (short) | Verdict | Evidence |
| --- | --- | --- | --- |
| P1, P2 | Same and cross reach the minimum traffic at the same plateau; plateau location | pass | README, `evaluate.py` |
| P3 / P3′ | Transfer law from same to cross | P3 fails at 1 of 5 points (T1); P3′ passes | README |
| P4 | Capacity where cross fusion starts to help, square shapes | pass | README |
| P5–P7 | FFN plateau reaches the minimum, lies in [R, 1.25R], keeps the predicted resident set | P5 passes; P6 misses by 1 B (F2); P7 only indirect | README |
| P8 / P8′ | Nest model plateau exact / within 2 B on held-out cases | 4/6 / 5/6 (F4: FFM 153, model 149) | `results/nest_scores.txt` |
| P9 / P9′ | F4 copy order explains the F4 gap | P9 fails (153→152); P9′ passes | README |
| P10 / P10′ | Attention-core plateaus | pass, exact | `results/attention_heldout.jsonl` |
| P11 | Write-through explains the coupling gaps vs FFM | passes at FFM's saved capacities; **withdrawn as an explanation**: 19 gaps remain on the union of breakpoints | PROTOCOL amendment |
| P12 | Write-through explains the FFN gaps | **fails** (no-write-through model still lower than FFM at 30 breakpoints) | `classify.py`, `results/classify_v2_small.jsonl` |
| P13 | Chain view makes square same and cross identical | pass | `results/classify_v2_small.jsonl` |
| P14 | An FFM-like restriction (a DRAM-backed tensor is fetched once per consumer) equals FFM on 14 coupling cases | 12/14; C1 fails | `results/p14_small.jsonl` |
| P14′ | Attention: FFM-like curve equals the graph curve | pass (attention gaps stay unexplained) | same |
| P14-FFN | Same restriction explains the FFN gaps | **fails**: union of all 8 subsets is never below FFM (0 breakpoints) but above it at 15; it ends at 384 = 256 + 4·32 because copy-wrapped inputs were read once per consumer | `results/ffn_parts/`, `graph/scoring.py ffn` |
| P14-FFN′ | Same, with copy-wrapped inputs shareable | **equality fails**: 8/8 subsets, lower/equal/higher at 26/8/1 breakpoints; weak rule passes only with the declared 147/148 B plateau exception | FFN_SHARED_INPUT_RESULTS.md |
| P15 / P15′ | max_q dS = I·min(L, I/2) on 31 held-out shapes | P15 fails (24/31 exact, needed 28); P15′ passes (31/31 within 5%) | `results/p15_p16_scores.txt` |
| P16 | Cross never needs >5% less capacity | 31/31 | same |
| P17 | spill_cost = 1 makes same and cross identical | 95/95; also proved | P17_RESULTS.md, ROLE_SYMMETRY_AND_SYSTEMS_CASE.md |
| P18a–e | 3- and 4-consumer forks: bounds, max gap, symmetry | all pass; **P18d only by equality** | `results/p18_scores.txt` |
| P19a–d | 6-consumer forks: max gap doubles at kkkiii (first-split knapsack) | **a, b, d pass; c fails**: max gap exact in 8/8 (a) and 16/16 (b), strictly above kkkkii in 6/6; bounds 24/24. Positive width is not ordered kkkkki < kkkkii < kkkiii in any shape (0/8): kkkkii is widest in 8/8 | `results/p19.jsonl`, `results/p19_scores.txt` |
| P21a | Unused X shifts H's capacity; fixed-boundary retain/spill composition | **pass**: 28/28 feasible interfaces exact; 4 empty controls excluded from evidence | P21_RESULTS.md, `results/p21/` |
| P21b | Capacity-only fails when H reads X; conditional residency/extents repair it | **pass**: coarse fails in 8/8 full graphs; 28/28 feasible interfaces repaired; 596/596 whole witnesses replay exactly across P21 | same |
| P21d | Frozen rank-change/last-use cuts recover unrestricted curves on 12 unseen residual cases | **fails on four valid cases**; 2 equal, 2 invalid from inherited duplicate final-write charges, 4 depth-12 cases incomplete at 600 s/arm. 158/160 saved witnesses replay exactly | P21D_RESULTS.md, `results/p21d/` |
| P21e | EH0 must leave EX's group iff L > K (row model) | **a pass 16/16; b fail 13/16; c fail 13/16**. Post-hoc plateau candidate L > K when EH0 reads X, L > 2K otherwise was subsequently tested and refuted by P21f | P21E_RESULTS.md, `results/p21e/` |
| P21f | Input-residency correction: read-X plateau gap for L>K; independent-input gap for L>2K, equality for K<L<2K | **plateau fails, existence passes**: independent-between 7/8; other three strata 8/8; existence 32/32. All 140 arms valid, 1,919 exact replays. Tile diagnostics remain separate | P21F_RESULTS.md, `results/p21f/score.json` |

P21 does not assert unrestricted whole-graph equality: all 16 free curves
differ from the fixed partition with H_last materialized. Granularity alone
does not distinguish resident X from DRAM X. P19 is scored; P22 is deferred.

## What is established, and how firmly

Scope: these statements are about the recursive loop-nest grammar of
`curve_model.py`. It covers serial execution, no recomputation, and the
historical halving tile domain (all divisors only when explicitly requested).
Its witnesses are executed cell by cell by
`simulate_nest.py` and reproduced exactly at all 216 FFM-comparison points.
**General execution-exactness is not established by finite replay tests.**
P21d exposed inherited duplicate final-write charges; the ownership repair and
subsequent audit/regression are recorded in OWNERSHIP_AND_CUT_DP.md (item 14
below). Existing replay successes establish the checked schedules' costs;
recurrence/cache equivalence remains distinct from a general physical-optimum
claim. P21d's original frozen failures and incomplete arms remain recorded.

1. **Curve model vs FFM.** Over 216 points the two agree at 206, the model is
   lower at 10 and higher at none (`results/curve_comparison.txt`). On FFN M8
   D4 F8 it is lower at 34 breakpoints (union of FFM's and the model's) and
   higher only at 147 B (the 1 B plateau offset).
2. **Sharing mechanisms and the FFM comparison.**
   - *Write-through* (one tensor feeds a consumer on chip and is also written
     to DRAM). Source lines are in REVIEW_NOTES_2.md.
   - *Shared on-chip fetch of a DRAM-backed tensor.* This is the P14 hypothesis;
     the restricted view matches 12/14 held-out coupling cases. Its completed
     FFN union is not FFM-equivalent: always separating shared graph inputs
     excludes the known 256 B plateau and creates a 384 B compulsory floor.
     See FFN_SHARING_RESULTS.md before making a causal attribution. The amended
     shared-input control restores the 256 B floor but still differs at 26 lower
     points and the known 1 B plateau offset (FFN_SHARED_INPUT_RESULTS.md).
   - *Unexplained.* The attention gaps and C1.
3. **Role symmetry (proved).** Exchanging I and K and flipping every
   consumer's role preserves the curve. With spill_cost = 1, every role mix of
   the same consumer count gives the same curve (P17, P18e). So in this grammar
   the coupling cost comes entirely from the read/write asymmetry of partial
   sums.
4. **Bounds (empirical; proof incomplete).** -b·IL ≤ dS ≤ b·KL held on all 287
   two-consumer shapes and on every P18 shape. The closure step of the proof is
   still missing (FIRST_PRINCIPLES.md §6).
5. **Mechanism of the maximum gap (witnesses; heuristic).** See
   FIRST_PRINCIPLES.md §7 and `results/fork_witness/`.
   - A pure fork can split an axis that no consumer contracts.
   - In a mixed fork every axis of X is some consumer's contraction axis, so a
     split leaves b partial sums unfinished. Each must be kept (s = nL) or
     spilled (2s).
   - A first-split knapsack then gives max dS = n·min(ceil(b/2)·L, n/2). This
     fits P15/P18 and explains why P18d held only by equality. P19 is its first
     test outside the data it was read from.
6. **Extent of the penalty (exploratory).** More minority consumers widen the
   range of traffic budgets with a positive gap, without raising its peak:
   12/12 shapes on signed area and positive-domain length
   (P18_PROFILE_RESULTS.md). Order completion removes one local
   fixed-order artifact at (16,4,16,4), but the coupling gap remains.
7. **Constructive side (Codex).** These results are proved, but each holds only
   within its own construction family, and none recovers the full curve
   (HELDOUT_RESULTS.md: the frozen quality gate fails).
   - Scalar retention: (r+1)h+1 with h = J+2L.
   - Strip-width elimination.
   - Loop normal form.
8. **Common-buffer execution evidence.** Replayed established examples at
   37/137/529 B show 11.1%/11.1%/14.8% crossed traffic premiums. The actual
   input reads and partial-sum stores/reloads explain the difference. After
   cache projection, all 212 P18 small-curve witnesses and 15 focused plans
   independently execute correctly. These are workload contrasts and regression
   checks, not an optimizer speedup; the 1,004 B wider-tile witness is retained
   alongside the 1,041 B restricted threshold. See BUDGET_EFFECT_RESULTS.md.
9. **FFN fixed-witness sharing effect.** At 80 B, an independently executed
   schedule uses 448 B traffic. Keeping its schedule/reservations fixed while
   separating X and dY consumer reads raises traffic to 576 B; 3 model and 5
   ablation executions pass. A fresh upstream run reproduces all 27 archived
   frontier rows. Original source reconstruction fails on incompatible copy
   loops; reordering the four independent input copies enables 4/24 orders
   for each of two sources, all reproducing native 76 B / 576 B and 147 B /
   256 B under detailed evaluation. At the 80 B budget, native and graph
   schedules have the same 128 B partial-sum overhead; extra input reads are
   192 versus 64 B. Native already shares X/dY and rereads W1/W2. This explains
   these schedules' transaction difference, not whether FFM excludes or prunes
   the graph schedule. See FFN_EXECUTION_AUDIT.md and FFN_NATIVE_ATTRIBUTION.md.
10. **Span-legal ranks (theorem) and P21 attribution (exploratory).** Whole-span
   loops in an unconditioned span are legal only over ranks R(S) that every op and internal tensor carry;
   the tensors lacking each rank, weighted by role, reproduce the fork
   obligations of §7 and the 448 B FFN witness (F row at two trips). Chaining I
   loops above P21's fixed boundary leave substantial cut-placement effects.
   The controlled sequence starting from frozen H_last materialization has
   423 → 402 → 268 → 7 → 0 wrong capacities as freedoms are added. The last
   family was selected after inspecting misses; these are order-dependent
   attributions, not independent causal shares. See P21_CUT_ANALYSIS.md.
11. **Whole-curve ranking is budget-dependent.** Reanalysis of all 32 P19
   curves finds b=2/b=3 crossings in 8/8 shapes. At (16,4,16,4), total traffic
   1344 B needs 201/265 B capacity (b=2/b=3), but 2624 B needs 69/55 B.
   Signed gap area increases with b in 8/8 shapes, while the relative mean
   increases from b=2 to b=3 in only 2/8. These are post-hoc interval measures;
   P19c remains failed. The first-layer FFN M/F tables also tie, while native
   inner weight refetch adds 128 B. See FIRST_PRINCIPLES.md §9 and
   `results/p19_profile.{json,png,pdf}`.
12. **P21 conditional value and release time (exploratory).** When H reads X,
   the 2s threshold gains V_X(c)=Q_H(c|DRAM)-Q_H(c|resident). All 212 finite
   eligible capacity checks match. Four chosen cut families recover 12/16 full
   curves; adding a streamed-tail family selected from the misses recovers
   16/16, with 560 exact new witness replays. This is seen-data attribution,
   not a general five-family theorem. A tail counterexample distinguishes
   entry mode and last-use release from full-span pinning. See P21_CUT_ANALYSIS.md.
13. **P21d structural cuts (frozen; failed).** All selected cuts are generated
   before search. The frozen whole-prefix/suffix rule excludes EX's exit;
   at (8,2,4), depth 4, capacity 4 this gives 336 versus 328, with both plans
   independently exact. Isolating EH0 changes local loop order and weight
   reuse. This refutes that cut generator, not the sufficiency of lifecycle
   labels. Separately, nested parent/child final-X-store charges invalidate
   two cases. A unique-owner ledger matches all 160 saved executions, but is
   only a post-hoc repricing, not a repaired solver or new equality score.
14. **Final-write ownership and an exact cut DP.** Nested partitions charged
   one final write twice; fixed in `39ca741e`. An all-plan audit finds 0 wrong
   prices after the fix (about 150,000 before, all +4 B) over 1.03 M executed
   plans; 495 archived curves plus 16 P19 n=16 curves regress with no frontier
   or frozen verdict changed except the two invalid P21d arms, which now equal
   their unrestricted curves. The cut DP (`partitions='dp'`) equals enumeration
   on every completed comparison and solves the 14-operator P21d graphs in
   seconds (enumeration: >1800 s); forks gain only 2x because their loop layer
   dominates. See OWNERSHIP_AND_CUT_DP.md.

## Withdrawn or corrected claims

- "Write-through explains every coupling gap." This was scored only at FFM's
  saved capacities; 19 gaps remain on the union of breakpoints.
- The chain view at first charged X's write twice (448 vs 432). This was fixed
  with `written`; the v1 chain columns in `classify_small.jsonl` are
  superseded by `classify_v2_small.jsonl`.
- Several obligation rules were corrected after Codex's review
  (FIRST_PRINCIPLES.md §6):
  - "Accumulator-free loops outermost" is not a pruning rule.
  - Charging partial sums twice is not a lower bound.
  - Partial sums are not kept first; retention is a knapsack.
  - The 95/96 rule is a heuristic.
- "I≠K shapes are confounded by size": false. They are fair role-only
  controls (P17 proof).

## Open

- P21f is closed with a failed plateau prediction. Any replacement theorem
  must compare complete conditional peak reservations, not silently change
  the frozen threshold or count the tile diagnostic as primary evidence.
- Extend the proved order-complete Fork quotient to decorated boundaries with
  partial symmetries/downstream dependencies only after establishing a
  cost-preserving action. Its joint-context bound covers this fixed-rank Fork
  family, not arbitrary graphs or linear Transformer stacks. See
  FORK_QUOTIENT.md, WIDTH_RESULTS.md and the conditional-state census.
- Complete a general proof of the repaired final-write charge ownership
  across nested partitions before a new lifecycle-sufficiency theorem.
  Keep P21d's failed, invalid and timed-out cases distinct; do not add cuts
  post hoc or claim a physical optimum from replayed frontiers alone.
- P19 is complete; its maximum-gap conjecture still needs a proof. Explain
  the whole-curve crossings without substituting a new metric for failed P19c.
- Complete the FFN comparison beyond the two replayed native sources. Distinguish
  mapspace exclusions from search pruning and explain the 147/148 B offset.
- The C1 and attention gaps vs FFM.
- The closure proof of the bound.
- An integer-tile retest of dS; the power-of-two grid is a known artifact
  source (CONSTRUCTIVE_RESULTS.md).
- Other graph structures (GLU, residual joins).
- Skeleton enumeration plus analytic tile sizing (FIRST_PRINCIPLES.md §4,
  HANDOFF.md).
- Literature check before any novelty claim (FIRST_PRINCIPLES.md §5).

## Code map

The graph models live in the `graph/` package (module path
`research.index_coupling.graph.<name>`):

| Module | Content |
| --- | --- |
| `model.py` | `Graph` (accesses, sizes, output/consumers/produced) and the graphs: `coupling`, `fork`, `ffn`, `attention` |
| `plateau.py` | Zero-extra-traffic plateau (nest model), `show` |
| `curve.py` | Capacity-traffic curve; cache keys projected per subproblem since `7b891c7c` |
| `views.py` | Chain view and FFM-like view (`chain_curve`, `ffm_like_curve`, `ffm_like_part`) |
| `context.py` | Span-legal ranks R(S) and loop-chain composition above any bottom curve (`span_ranks`, `lifted_curve`) |
| `structural_cuts.py` | Frozen P21d topology-only rank-change/last-crossing-use event generator |
| `analysis.py` | Q(C) `traffic_at`, S(q) `capacity_for`, `delta`, `gap_steps`, `compare_to_reference` |
| `references.py` | Archived FFM frontiers (`cases`, `ffn_case`) |
| `experiments.py` | One command line for every runner: `plateau`, `compare`, `classify`, `ffm-like`, `ffn-part`, `sweep`, `p17`, `p18`, `p19`, `witness` |
| `scoring.py` | `sweep`, `p15`, `p18`, `p19`, `ffn` |

Example: `python -m research.index_coupling.graph.experiments p19 3`, then
`python -m research.index_coupling.graph.scoring p19 p19.jsonl`.

The old top-level modules (`nest_model`, `curve_model`, `chain_view`, `ffm_like`,
`compare_curves`, `classify`, `sweep_analysis`, `coupling_sweep`, `run_p17/18/19`,
`ffn_parts`, `fork_witness`, `score_*`) are forwarding stubs. Commands frozen in
PROTOCOL.md and Codex's scripts still run unchanged. New code should import
from `graph/`.

Other files at the top level:

| Role | Files |
| --- | --- |
| Independent checks | `simulate_nest.py` (cell-level execution of witnesses), `verify_projection.py` (archived curves, 0 mismatches), `upstream_probe.py` |
| FFM side (needs AccelForge) | `run.py`, `evaluate.py`, `*.yaml` |
| Follow-up analyses (Codex) | `analyze_p18_profile.py`, `run_fork_order_check.py`, `replay_budget_effects.py` |
| Constructive families (Codex) | `constructive_fork.py`, `tiled_fork.py`, `scalar_retention.py`, `loop_normal_form.py`; runners `run_constructive_fork.py`, `run_tiled_fork.py`, `run_scalar_retention.py`, `run_loop_normal_form.py`, `validate_constructive.py`; summaries `summarize_*.py`, `inspect_heldout_miss.py`, `test_validate_constructive.py` |
| Diagnostics | `probe_curve_memory.py` (cache-growth diagnosis; Linux only), `real_scale.py` |

## Results map

| Files | Content |
| --- | --- |
| `results/{n4,n8,n16,T1,T2,T3,C1,C2}_{same,cross}.json`, `upstream_*.jsonl`, `attention_heldout.jsonl` | FFM frontiers (reference) |
| `curve_comparison*.txt`, `ffn_simulated.txt`, `nest_scores.txt` | Model vs FFM; simulator checks |
| `classify_v2_small.jsonl` (`classify_small.jsonl` is superseded), `p14_small.jsonl` | P11–P14 |
| `ffn_parts/` | FFN graph, no-write-through and FFM-like subset curves |
| `ffn_shared_input_replay/` | Executed FFN witnesses, fixed-schedule sharing ablation, native merge trace, copy-order replays and per-tensor attribution |
| `coupling_sweep.jsonl` (256), `coupling_sweep_heldout.jsonl` (31), `p15_p16_scores.txt` | Two-consumer gap law |
| `p17/`, `p18.jsonl`, `p18_scores.txt`, `p18_profile/`, `fork_witness/` | Role symmetry, multi-consumer forks, witnesses |
| `tiled_fork/`, `constructive_fork/`, `constructive_heldout/`, `scalar_retention/`, `loop_normal_form/` | Codex constructive work |
| `memory_probe/`, `verify_projection.txt` | Cache diagnosis and its exact fix |
| `projected_effect_replay/` | 227 independent executions, common-buffer effects and figures |
| `p21/` | 16 residual graphs, 64 conditional interfaces (56 feasible), 596 witness replays, full error/choice intervals, static comparison figure |
| `p21_attribution/` | Exploratory: fixed vs I-chain-lifted vs unrestricted curves for the 16 P21 graphs (`attribute_p21.py`) |
| `p21_cuts/` | Exploratory cut families, 560 executable witnesses, conditional residency value, and tail entry/release counterexample |
| `p21d/` | Frozen 12-case audit, 24 bounded arm records, four clean inequality cases, two accounting-invalid cases, four incomplete cases, per-tensor diagnosis and figure |
| `p19_profile.{json,png,pdf}` | Post-hoc interval integration, budget-dependent b=2/b=3 crossings, and a full-curve comparison; no new search |

Heavy runs go to the experiment server with memory and time caps, one process
per curve for FFN. Local runs are limited to checks that take seconds.
