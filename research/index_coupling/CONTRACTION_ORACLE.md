# One dense contraction: schedule optimum vs the loop grammar

This is the first step of the positive-traffic lower-bound programme
(CHAIN_THRESHOLD.md §6).

The model is a single contraction y_j += x_i W[i, j], i < a, j < b, with W
resident. Execution is serial, with C cells for x and y elements and no
recomputation.

- Extra traffic counts one transfer for each repeated x load.
- It counts two transfers for each spill of an unfinished partial sum y_j
  (write plus read-back).
- `contraction_oracle.oracle` computes the exact optimum over **all**
  schedules by Dijkstra over (completed pairs, on-chip set).
- `grammar` is the `curve()` optimum of the same contraction, under both tile
  domains.

Records are in [results/contraction_oracle/](results/contraction_oracle/).

**Code location (2026-11-10).** The modules named in §6-18
(`chain2_closed_form`, `elementwise_chain`, `matmul_keep`, `op_projection`,
`closed_form_work`, `exact_search`, `sandwich`) were merged into
[response/](response/). The commands quoted below are those of the commits
that produced each record. [response/README.md](response/README.md) maps
every old module and command to its new place. All frozen predictions and
recorded outputs were reproduced identically after the move. Run
`python -m research.index_coupling.response.experiments verify` to re-check
the frozen predictions.

## 1. Theorem for C = 2

**Theorem.** With two cells, the least extra traffic is (a − 1)(b − 1).

**Proof.**

- Call each maximal on-chip interval of an element a *visit*. x has a + R
  visits and y has b + S visits, so the extra traffic is R + 2S.
- Every pair (i, j) needs an x_i visit and a y_j visit that overlap. Distinct
  pairs need distinct visit pairs.
- Two visits overlap exactly when the later one starts while the earlier one
  is on chip. With two cells, a starting visit overlaps at most one other
  visit, and the first visit overlaps none.
- Hence ab ≤ a + R + b + S − 1, so R + S ≥ (a − 1)(b − 1), and
  R + 2S ≥ (a − 1)(b − 1).
- A serpentine sweep attains the bound: hold one y, sweep x, then turn and
  keep the last x for the next y. ∎

## 2. Conjectures and data

**Serpentine conjecture (refuted).** This conjecture holds u = C − 1 elements
of one side, sweeps the other side and reuses one element at each turn. It
matches all 14 cases up to 3×3 but fails at a = b = C = 4: the oracle gives 2,
the formula gives 3.

**Blocked serpentine (repaired after the 4×4 counterexample).**

- Hold one side in blocks u_1, u_2, ..., each at most C − 1, and sweep the
  other side (size n) back and forth.
- At the turn between blocks u_k and u_{k+1}, C − max(u_k, u_{k+1})
  streamed elements can stay on chip.
- That turn therefore costs w · max(0, n − C + max(u_k, u_{k+1})), with
  w = 1 for streamed inputs and 2 for spilled partial sums.
- Minimise by a DP over block sequences and over which side is held.

Smaller blocks leave room to carry more of the swept side across turns. This
is why a = b = C = 4 attains 2, with two blocks of 2.

| Set | Cases | Blocked = oracle |
| --- | ---: | ---: |
| Seen, a ≤ 4, b ≤ 5 (used for the repair) | 37 | 37 |
| Held out: predictions frozen in `609d5c3a` before the runs | 20 | **20** |
| Held out: 5×4 | — | incomplete (12 GiB memory cap) |

Most held-out cases are weak tests. They either fall under the proved C = 2
theorem or have C > min(a, b), where the answer is 0. **Only two held-out
points test the repair nontrivially:** 3×6 and 5×3 at C = 3, where the
prediction is 4 and the oracle gives 4. The formula therefore remains a
conjecture for C ≥ 3.

## 3. The loop grammar is not schedule-optimal

| Case | Oracle | Grammar (all divisors) |
| --- | ---: | ---: |
| 3×3, C = 3 | 2 | 6 |
| 3×5, C = 3 | 4 | 12 |
| 5×3, C = 3 | 4 | 10 |
| 2×8, C = 2 | 7 | 14 |
| 4×4, C = 4 | 2 | 4 |

In 29 of the 57 complete cases the grammar is above the schedule optimum,
by up to a factor of 3. There are two causes:

- **Fixed loop direction.** Every iteration of a loop nest repeats the same
  order, so nothing streamed can be carried across a block turn. A serpentine
  order would allow it.
- **Divisibility.** Blocks must divide the extent, even under the
  all-divisors domain.

**Where this matters.**

- Per turn, the grammar pays about n and the schedule pays
  n − C + u.
- For n ≫ C the ratio tends to 1, so in deep tiling regimes the gap is
  negligible.
- It is large when the streamed side is comparable to C, which is the region
  just below the zero-traffic plateau.

Every "exact" curve in this project, and the FFM comparisons, are exact with
respect to loop nests, not to physical schedules. Most practical mappers
also use loop nests, so the grammar remains the relevant search space. Its
distance from the schedule optimum near the plateau is now quantified for
one contraction.

## 4. Consequences for the lower-bound programme

There are two different targets, and they must be kept apart:

1. **Schedule-level bounds** answer the physical question. They are valid for
   pruning grammar search, because the grammar's optimum is at least the
   schedule optimum. Near the plateau, however, they are loose by exactly the
   grammar's suboptimality shown above.
2. **Grammar-level exact responses** (for example Codex's two-live normal
   form) are what tight pruning of grammar search needs.

The chain threshold L (CHAIN_THRESHOLD.md) is schedule-level. In the tiny
stacks it coincides with the grammar plateau because the grammar attains it
there.

## 5. Open

- **Prove the blocked formula for C ≥ 3.** The C = 2 counting must be
  strengthened. Each turn forces the swept side out except for the carried
  elements, and at most C − max(u_k, u_{k+1}) can be carried.
- **Faster oracle.** Symmetry reduction over i and j would reach 5×4 and
  beyond, giving more nontrivial held-out tests.
- The grammar-level counterpart is now derived (§6).

## 6. The grammar's single-contraction curve in closed form

Let R_dom(n) be the tiles reachable from extent n by a chain of recursive
tilings in the tile domain (n itself included). `loop_nest` predicts

    f(a, b, C) = min( min over u in R(b), u <= C-1 of  a (b/u - 1),
                      min over t in R(a), t <= C-1 of 2b (a/t - 1) )

for C >= 2. The first term holds a y tile and re-reads all of x per F tile.
The second holds an x tile and spills y per D tile. u = b or t = a gives the
zero-traffic plateau min(a, b) + 1.

**Derivation.** It assumes the grammar's per-loop semantics: a tensor not
indexed by the loop is either held whole across the loop's iterations or
re-fetched in every iteration, and traffic multiplies by trip count. Induct on
the nest.

- Let the outermost loop be over F with tile u, so there are b/u iterations.
  - If x is held, the capacity is at least a + 1, and t = a gives f = 0.
  - Otherwise the extra traffic is a (b/u − 1) + (b/u) f(a, u, C).
- Substitute the inductive form of f(a, u, C):
  - an inner y tile u' gives a (b/u − 1) + (b/u) a (u/u' − 1) = a (b/u' − 1),
    which is the one-level term for u' in R(b);
  - an inner x tile t gives a (b/u − 1) + 2b (a/t − 1) ≥ 2b (a/t − 1);
  - an inner zero needs C ≥ u + 1 or C ≥ a + 1, and both are one-level terms.
- An outermost D loop is symmetric, with weight 2.

So deeper nests and mixed orders never beat one level. The minimum depends
on C only through which tiles fit, which makes it a staircase set by the
divisor structure.

**Test.**

- **Archived rows.** `grammar_halving` and `grammar_divisors` in all 57
  oracle rows: 94 of 94 comparisons agree. These were seen while deriving.
- **Held out.** Predictions for 7 composite shapes × all C × both domains
  were frozen in `7972bf82` (`nest_predictions.json`) before `grammar` was
  run (`nest_check.jsonl`).
  - Result: **112 of 112 agree**. 84 of them have C > 2 and positive traffic.
  - In 18 shape/C points the two domains differ, so the test also checks the
    reachable-tile sets.

**Against the blocked serpentine** (conjectural for C ≥ 3), divisors domain:

| C | 12×18 grammar | 12×18 blocked | 18×12 grammar | 18×12 blocked |
| ---: | ---: | ---: | ---: | ---: |
| 4 | 60 | 55 | 54 | 51 |
| 6 | 60 | 32 | 36 | 32 |
| 9 | 24 | 18 | 18 | 15 |
| 12 | 12 | 9 | 18 | 12 |

At these sizes the gap is up to about 1.9×. It comes mostly from the
staircase: the grammar only gains capacity at reachable tiles. The
carry-over term (n − C + u instead of n per turn) is the smaller part.

**Use for C2.** For one dense contraction with resident weight, f is exact
and costs O(|divisors|). It is a grammar-level response, so a C2 bound built
from it is tight for this operator. Whether it composes over chains is open:
in a chain, the held tile of one contraction is the streamed side of the
next.

## 7. Literature check (traversal order and divisibility)

The search was brief, not a survey.

- **Divisibility is known.**
  - Ruby (Horeni et al., ISPASS 2022; Timeloop v3) adds imperfect
    factorization to accelerator mapspaces and reports EDP gains of up to
    about 50%.
  - Peemen et al. pad non-divisor tiles.
  - GOMA (arXiv 2603.07962) requires strict divisibility.
- **Inter-tile reuse under a fixed order is known.** Peemen, Mesman and
  Corporaal ("Inter-tile reuse optimization applied to bandwidth constrained
  embedded accelerators") model the overlap of consecutive tiles in a strip,
  for a fixed loop direction.
- **Reversing loop direction (serpentine or boustrophedon order)** was not
  found in these accelerator-mapping papers. It appears in GPU rasterization
  patents, and it is folklore in cache-blocking practice. The novelty of §3's
  traversal-direction gap is therefore unestablished. It should be claimed
  only as a measurement against a schedule oracle, not as a new technique.
- **Pebbling with partial sums.** Sobczyk (arXiv 2410.22237, IPL) shows that
  red-blue pebbling with fast memory below the in-degree is NP-complete, even
  for one level with two red pebbles. The complete bipartite case of §1 is a
  tractable special case with a closed form. Papp, Sobczyk and Yzelman
  (arXiv 2506.10854) add partial-computation steps, which is this document's
  spill model. Their results have not yet been read in detail.

## 8. Two-contraction chain: closed-form grammar response

The chain is x[a] → E0 → h[b] → E1 → z[c], with both weights resident and
grammar v2. f is §6's single-contraction form. The grammar's cost rules, read
from `curve.py`, admit only these choices:

- **A, h via DRAM.** Extra traffic 2b + f(a, b, C) + f(b, c, C). The
  operators become two independent single contractions.
- **Fused F loop with tile u ∈ R(b), trips t = b/u.** F is the only rank
  common to E0 and E1. x and z lack F, so each is kept or re-fetched per
  trip. The inner h tile of size u is kept across the split:

  | x | z | Cells | Extra |
  | --- | --- | --- | --- |
  | re-fetched | spilled | u + 1 | (t − 1)(a + 2c) |
  | re-fetched | kept | c + u + 1 | (t − 1) a |
  | kept | spilled | a + u + 1 | 2 (t − 1) c |
  | kept | kept | a + c + u | 0 |

  u = b (t = 1) is h held whole: zero traffic at b + 1 cells.
- **Nested F loops whose keep choices differ by level.** Each is dominated by
  one level: an inner kept tensor costs the same cells, and the outer level
  only adds re-fetch terms.

`chain2_closed_form.predict` is the minimum over these options.

**Held-out test.**

- Predictions were frozen in `ed8c8b4f` (`chain2_predictions.json`) before
  any chain curve was computed (`chain2_check.jsonl`).
- Coverage: 10 shapes, C from 2 to b + 2, both tile domains.
- **Result: 140 of 140 agree.** 94 of them have positive traffic.
- Every option is the unique minimiser somewhere:
  - fused with both re-fetched: 46;
  - h via DRAM: 27;
  - fused with z kept: 3;
  - fused with x kept: 2;
  - ties: 16.

**Structural consequence for longer chains.** Dense contractions with
distinct contracted ranks share a rank only pairwise:
E0 ∩ E1 = {F}, but E0 ∩ E1 ∩ E2 = ∅. A grammar group of three or more such
contractions therefore has no loop, and can only be partitioned.

The grammar response of any unit-M chain of dense contractions, with no
elementwise operators, should therefore reduce to a DP over boundaries:

- each segment holds one or two contractions, with the closed forms above;
- each boundary vector is either kept, adding its size to the cells of the
  segments it spans, or sent via DRAM, adding 2 × its size;
- the segment forms are also needed with a resident input or output.

§9 derives the resident-boundary forms and tests the DP. Elementwise
operators, which share all their ranks, remain open.

## 9. Pure contraction chains: boundary DP

The chain is V_0 → c_0 → V_1 → ... → V_m, with unit M, resident weights and
grammar v2. K is the number of cells a segment receives after subtracting
its kept boundary vectors.

**Segment forms.** These come from the same cost rules. A resident (kept)
boundary is external inside the segment.

- **Single contraction p → q.**
  - Both ends resident: 0 at K ≥ 0.
  - One end resident: 0 at K ≥ 1. The other end streams through one cell.
  - Neither resident: f(p, q, K) of §6.
- **Pair a → b → c, fused under F with tile u ∈ R(b), trips t = b/u.** Each
  entry is (cells, extra):
  - both ends streamed: the four rows of §8;
  - input resident: (u + 1, 2(t − 1)c), (c + u, 0);
  - output resident: (u + 1, (t − 1)a), (a + u, 0);
  - both resident: (u, 0).

**DP.**

- Segments have one or two contractions. Three dense contractions share no
  rank, so no larger grammar group can loop.
- Each interior boundary V_j is either kept, which subtracts n_j from the K of
  both neighbouring segments, or sent via DRAM, which adds 2 n_j.
- The capacity constraint is a max over groups, so at fixed C the segments
  are independent given the boundary choices.
- Implemented as `chain2_closed_form.chain_predict`. At m = 2 it reproduces
  §8 exactly.

**Held-out test.**

- Predictions were frozen in `36bd1736` (`chain_predictions.json`) before
  any chain curve was computed (`chain_check.jsonl`).
- Coverage: 10 chains of 3 to 5 contractions, with mixed sizes up to 8; C
  from 1 to 2 max n + 2; both tile domains.
- **Result: 268 of 268 agree.**
  - 92 have positive traffic, with 33 distinct positive values.
  - 156 are zero.
  - 20 are infeasible.

**Ablation.** This is in-sample and diagnostic only.

- Removing pair segments raises the prediction in 69 rows.
- Removing kept boundaries raises it in 161 rows.

Both mechanisms are therefore needed.

**Meaning.**

- For pure unit-M contraction chains, the grammar's exact response is no
  longer a search result. It is a DP with O(m) states and O(|R(n)|) work per
  segment.
- The whole curve is piecewise constant in C, with breakpoints at the sums
  of kept vector sizes and reachable tiles. That gives an exact, cheap child
  response for C2-style pruning in this family.
- **Limits.**
  - The archived FFN and attention stacks contain elementwise operators.
    These share every rank with their neighbours, so groups can be larger
    and loop over more ranks.
  - Their M > 1 parents add an outer row loop.
  - Neither is covered yet.

## 10. Chains with elementwise operators (FFN and attention at unit M)

An elementwise op keeps its rank (H[F] → Z[F]). A run of ops is a loopable
grammar group only if its ops share a rank. In an FFN or attention layer
X[d] →c→ H[f] →e→ Z[f] →c→ X'[d], the loopable runs are:

- the singletons c and e;
- ce and ec, which share F;
- cec, which shares F;
- the cross-layer cc (EY_i, EH_{i+1}), which shares D.

`elementwise_chain.predict` is the §9 boundary DP with these group forms.
Each form is (cells, extra), with tile u ∈ R(f) and trips t = f/u. s is 1 for
a streamed end and 0 for a resident one.

- **e:** (s_in + s_out, 0).
- **ce:**
  - input resident: (u + s_out, 0);
  - otherwise: (a + u + s_out, 0) with x kept, or (u + 1, a(t − 1)) with x
    re-fetched.
- **ec:** the mirror of ce, with spill weight 2.
- **cec:** up to two loop levels.
  - Level 1 has tile u and keeps or re-fetches each end.
  - Level 2 either splits all three ops, which costs 2u cells at the
    elementwise op because H and Z tiles are both held, or splits off one
    contraction with its intermediate kept at u and loops the other {c, e}
    pair at a smaller tile u'. That side's end may also be kept at level 2.
  - This lets the H tile and the Z tile differ. For example, keeping the Z
    tile u and looping {EH, EZ} at u' costs u + u' + 1 cells. x is then
    re-fetched per u' trip and z spilled per u trip.

**Held-out test on synthetic stacks.**

- Predictions were frozen in `4f4df3e3` (`elementwise_predictions.json`)
  before any curve was computed (`elementwise_check.jsonl`).
- Coverage: 11 FFN stacks with 1-3 layers and (d, f) up to (4, 8), plus 2
  attention stacks, over all C and both tile domains.
- **Result: 388 of 388 agree.**
  - 100 have positive traffic, with 75 distinct values.
  - 262 are zero.
  - 26 are infeasible.
- In-sample ablation:

  | Removed | Rows predicted worse |
  | --- | ---: |
  | the second cec level | 18 |
  | cec groups | 63 |
  | cross-layer cc groups | 8 |

**Test on archived C2-audit nodes.**

- The DP was extended to resident chain ends. These are held by the caller
  at no cell cost; the frozen predictions are unchanged.
- `python -m research.index_coupling.elementwise_chain archive <cases>`
  compares whole curves, at every capacity up to the last breakpoint + 2.
- A solve node qualifies when it has unit M, all its weights resident,
  contiguous ops, and no interior vector external or owned.

| Case | Nodes | Qualifying | Exact curve | With positive traffic |
| --- | ---: | ---: | ---: | ---: |
| FFN forward 1 / 2 / 3 / 4 layers | 271 / 1,052 / 3,221 / 10,834 | 47 / 147 / 283 / 455 | all | 7 / 40 / 108 / 212 |
| attention forward 2 / 4 layers | 1,052 / 10,834 | 147 / 455 | all | 40 / 212 |
| FFN M8 1 / 2 layers (d 4, f 8) | 2,108 / 6,176 | 148 / 382 | all | 31 / 94 |
| **Total** | | **2,064** | **2,064** | **744** |

**Scope.** Qualifying nodes are a small share of each archive. Most nodes:

- have streamed weights, which is exactly the C2 retention question;
- have M > 1;
- are group-stage queries, which must loop at the top.

**Next.**

- Add streamed weights. Each streamed weight adds operand cells and its own
  re-fetch terms.
- Add group-stage entries.
- Then the forms can bound or replace the C2 anchors directly.

## 11. Streamed weights, and what exact child responses give C2

**Rule.** At unit M, a contraction's weight carries both of the
contraction's ranks. Every loopable group loops only on a rank its ops share,
so a weight is never a "lacking" tensor. It is never kept or re-fetched, only
sliced.

The leaf requires every live tensor to be scalar, so a streamed weight must be
sliced on both ranks. Choosing the loop order (first the rank whose loop
re-fetches nothing) does this with no traffic. The weight then adds exactly
one operand cell to its own op's peak.

Every form of §8-10 therefore takes w = 1 inside the term of the op that
streams it. For example:

- single, ends streamed: f(p, q, K − w);
- single, one end resident: 1 + w;
- cec, all split at level 2: max(u + s_x + w_1, 2u, u + s_z + w_2).

At w = 0 the forms are unchanged. All earlier frozen predictions were
re-checked identical.

**Held-out test on synthetic stacks.**

- Predictions were frozen in `3913122d` (`weights_predictions.json`) before
  any curve was computed (`weights_check.jsonl`).
- Coverage: every streamed-weight subset of 7 FFN and attention stacks, with
  1-2 layers and up to 16 subsets, over all C and both tile domains.
- **Result: 2,064 of 2,064 agree.**

**Archived C2-audit nodes, now admitting streamed weights**
(`elementwise_archive.jsonl`):

| Case | Qualifying solve nodes | Exact curve | Of which with streamed weights |
| --- | ---: | ---: | ---: |
| FFN forward 1 / 2 / 3 / 4 layers | 101 / 423 / 1,421 / 5,123 | all | 54 / 276 / 1,138 / 4,668 |
| attention forward 2 / 4 layers | 423 / 5,123 | all | 276 / 4,668 |
| FFN M8 1 / 2 layers | 313 / 933 | all | 165 / 551 |
| **Total** | **13,860** | **13,860** | **11,796** |

The excluded solve nodes have M > 1, an interior vector that is external or
owned, or a constrained root.

**What this gives C2** (`c2_exact_children.jsonl`). A choice is *covered*
when its child node has a closed form. The table first appeared with an
"ideal exclusions" column. **That column is withdrawn:** see the correction
below.

| Case | Proper choices | Covered |
| --- | ---: | ---: |
| FFN 1 / 2 / 3 / 4 layers | 118 / 446 / 1,414 / 5,050 | 96 / 392 / 1,328 / 4,932 |
| attention 2 / 4 layers | 446 / 5,050 | 392 / 4,932 |
| FFN M8 1 / 2 layers | 2,388 / 7,177 | 910 / 3,043 |

**Correction.** The ideal-exclusion test compares a bound with the final
parent frontier. That frontier is the minimum over all choices, so every
choice's *exact* curve is weakly dominated by it. With all children exact,
the count is 100% in every case: 2,388 of 2,388, 7,177 of 7,177 and 5,050 of
5,050 were checked. Counting exact curves as exclusions is therefore a
tautology, not a pruning gain. The test is meaningful only for strict lower
bounds (§13).

**What the closed form does give.**

- A covered child needs no search: its exact response costs a few divisor
  loops.
- In the tiny stacks, 88-98% of retention choices are covered; in the M8
  stacks, about 40%.
- The saving is the search work under those children. It has not been
  measured.
- The form is exact for this loop grammar (v2, halving or divisor tiles,
  partitions by cut DP), not for physical schedules (§3).

**Uncovered.**

- Children with M > 1. These are most M8 choices; the parent row loop adds an
  outer dimension.
- Group-stage queries.
- Training graphs, where activations are reused across forward and backward.

## 12. One matmul at M > 1: the keep-level model

With M > 1, M is shared by every activation and lacked by every weight. A
weight can now be kept or re-fetched per row. Loops over D or F also become
useful with M > 1, because they slice the weight instead of re-fetching it.
This is the weight-stationary versus output-stationary choice. It means the
problem is the full three-rank loop-order question, and closed forms for
chains need its atom first.

**Model** (`matmul_keep.predict`). Y[M,F] += X[M,D] W[D,F]. The lacking
ranks are F for X, M for W and D for Y.

- Along the nest the current tiles c = (c_M, c_D, c_F) only shrink, through
  reachable tiles.
- A live tensor T with lacking rank r has two fates:
  - **kept** at a loop over r, at tiles c with c_r > 1. It holds the product
    of its own two tiles in cells. It was re-fetched E_r / c_r − 1 times.
  - **never kept.** It is scalar at the leaf (1 cell) and re-fetched
    E_r / c_r − 1 times, with c the leaf tiles.
- Peak cells are the sum over tensors. Extra traffic weights Y by 2 and
  inputs by 1.
- Keeps occur in some order. The state after keeping T has a smaller r tile,
  which is the loop that keeps it.
- The prediction minimises over keep orders and states. This is a structural
  model of the grammar's one-op nest, not the grammar's own recursion over
  loops.
- At M = 1 it equals §6 plus the streamed-weight cell (checked).

**Held-out test.**

- Predictions were frozen in `6027033c` (`matmul_predictions.json`) before
  any curve was computed (`matmul_check.jsonl`).
- Coverage:
  - 7 shapes, from (M, D, F) = (2, 2, 2) to (8, 4, 8);
  - 4 residency patterns: all streamed, X resident, Y resident, W resident;
  - both tile domains;
  - every C up to the sum of all tensor sizes.
- **Result: 2,912 of 2,912 agree.**
  - 240 have positive traffic, with 59 distinct values per shape and
    pattern.
  - 2,602 are zero, which tests the plateau location.
  - 70 are infeasible.

**Meaning.** For one operator, the grammar's response is a min over keep
orders (at most 3! × 2^3) and monotone tile states. Each tensor's cost depends
only on its tiles when kept: cells from its own ranks, re-fetches from its
lacking rank. This is the standard reuse model of loop-nest mappers. It is
now verified as an exact description of this grammar for one matmul.

**Open: chains at M > 1.** In a fused group, interior intermediates are
sliced by the group loops. Inner partitions then keep intermediate tiles.
The natural conjecture composes the keep-level model per tensor with the
§9-11 boundary DP. That composition is not yet derived.

**Is an outer M loop enough?** No. Composing an outer M loop (keep or
re-fetch each weight) with the unit-M forms is strictly worse than the
grammar in 513 of the 2,842 feasible rows of `matmul_check.jsonl`.

The smallest case is (M, D, F) = (2, 2, 2) with X resident, at C = 3. The
grammar reaches zero extra traffic by looping F outside M and keeping only the
weight slice W[:, f]: 2 cells instead of 4. Weight-slice stationarity is
therefore essential at M > 1. An exact M > 1 chain form would be the full
loop-order problem, and it would cost about as much as the grammar's own
search.

## 13. A row-projection lower bound for M > 1 children

**Lemma.** Restrict any grammar plan of a span with M extent m to a single
row:

- M loops have one iteration;
- every other loop and keep decision is unchanged;
- kept activation tiles lose their M factor;
- a weight kept at an M loop becomes resident, and a re-fetched one becomes
  streamed.

The result is a unit-M grammar plan with no larger peak. Its activation
traffic is exactly the original plan's traffic for that row. Weight traffic
is nonnegative and is dropped. Hence

    R_m(C) >= m * R_1(C),

where R_1 is the §11 response with every weight resident. That is the most
permissive case, since a streamed weight only adds cells. A tighter variant
counts each weight not resident at the child entry as streamed (one cell).
It is a conjecture: a weight kept at an M loop holds at least one cell over a
wider scope, but replacing it by a streamed weight has not been shown to be a
valid unit-M plan.

**Check on archived M > 1 solve nodes** (`row_projection.py check`,
`row_projection_check.jsonl`). The qualifying conditions are those of §10
with M > 1. **0 violations in 3,787 nodes, for both variants.** The bound
equals the actual curve in 1,155 nodes (proved variant) and 1,889
(conjectured variant).

**C2 on M > 1 children** (`row_projection.py c2`, `c2_row_bound.jsonl`).

- For a choice whose child has M > 1, the bound is lifted to the parent, as
  in `c2_chain_ceiling.py`.
- It is combined pointwise (max) with the slot bound.
- It is compared with the final parent frontier. Every combined bound is
  asserted to stay below the actual candidate curve.

| Case | Choices with M > 1 child | Ideal exclusions, slot bound | With row bound (proved) | With row bound (conjectured) |
| --- | ---: | ---: | ---: | ---: |
| FFN 1 / 2 / 3 / 4 layers | 22 / 54 / 86 / 118 | 16 / 38 / 60 / 82 | same | same |
| attention 2 / 4 layers | 54 / 118 | 38 / 82 | same | same |
| FFN M8 1 layer | 1,478 | 685 | 747 | 752 |
| FFN M8 2 layers | 4,134 | 1,754 | 1,894 | 1,904 |

The gain is real but small: +9% and +8% of the slot bound's exclusions in
the M8 stacks. The bound ignores the main M > 1 cost, which is weight
re-fetch versus retention across rows. That cost is exactly what C2's anchor
models, so the two bounds measure different things, and combining them
pointwise captures little.

A sharper bound would add a lower bound on weight traffic: each streamed
weight is re-fetched unless a slice of it is held across rows. That is the
next theoretical target.

## 14. An operator-projection lower bound (any M)

**Lemma.** Fix a grammar plan of a chain span and one contraction j. Keep only
the loops and keep decisions that touch j's tensors. The result is a grammar
plan of j alone:

- group loops are over ranks shared in the group, hence ranks of j;
- every tensor of j present at j's leaf (kept tile or scalar) is on chip at
  the same moment in the original plan, so the peak does not grow;
- an interior vector kept across a partition corresponds, in j's own nest, to
  a keep of that tensor before its lacking rank is split. That costs zero
  traffic and its tile in cells.

**Disjointness.** Every extra-traffic event is a (tensor, loop) pair and
belongs to one operator.

- A weight is used by one operator.
- An activation is never lacking in a group that holds both its producer and
  its consumer, because the grammar requires every looped rank to be carried
  by tensors made inside the group. Its re-fetches therefore occur only in
  consumer-only groups, and its spills only in producer-only groups.
- DRAM round trips of interior vectors are dropped.

Hence R_chain(C) >= sum_j R_j(C). R_j is §12's keep-level optimum of
operator j alone. Its weight residency is as in the span. Its activations
are live unless they are resident span ends. Elementwise operators contribute
0. The bound includes weight-slice stationarity, which §13's row projection
dropped.

**Check** (`op_projection.py check`, `op_projection_check.jsonl`).

- Every qualifying chain solve node of the 8 archives at any M, 17,647 nodes:
  **0 violations**.
- The bound equals the actual curve in 5,796 nodes. That is 79% for the M8
  one-layer stack and 14% for FFN-4.

These totals sum the eight archived JSONL records. They correct the earlier
prose totals of 17,857 / 6,416, as independently checked in the
[closure review](https://github.com/HaoningJiang-space/accelforge-streaming-dse/blob/3da98687/research/index_coupling/CLOSURE_REVIEW.md).
The archived measurements and zero-violation result are unchanged.

**C2** (`op_projection.py c2`, `c2_op_bound.jsonl`). Combined pointwise (max)
with the slot bound, lifted as in §13. Every bound is asserted to stay below
the actual candidate curve.

| Case | Proper choices | Ideal exclusions, slot bound | With operator bound |
| --- | ---: | ---: | ---: |
| FFN 1 / 2 / 3 / 4 layers | 118 / 446 / 1,414 / 5,050 | 105 / 372 / 1,055 / 2,865 | 115 / 407 / 1,121 / 2,962 |
| attention 2 / 4 layers | 446 / 5,050 | 372 / 2,865 | 407 / 2,962 |
| FFN M8 1 / 2 layers | 2,388 / 7,177 | 1,383 / 3,955 | **2,149 / 5,825** |

In the M8 stacks this adds 55% and 47% to the slot bound's exclusions,
against 9% for the row projection. These are still candidate counts with the
final frontier as incumbent. Shared-DAG work is what matters (§15).

## 15. Exclusive work removed by closed-form terminals

`closed_form_work.py` makes every closed-form (unit-M) solve node terminal
in the archived call DAG. It removes that node's work, and the work of every
descendant no longer reachable from the root through non-terminal nodes.
Shared children reachable by another path stay. The figures are fractions of
each ledger counter's total (`closed_form_work.jsonl`).

| Case | Terminal nodes | Nodes left | DP transitions | Loop choices | Pareto candidates | Merge inputs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FFN 1 layer | 101 | 88 of 271 | 76% | 39% | 59% | 69% |
| FFN 2 layers | 423 | 247 of 1,052 | 93% | 33% | 86% | 92% |
| FFN 3 layers | 1,421 | 442 of 3,221 | 99% | 22% | 96% | 99% |
| FFN 4 layers | 5,123 | 673 of 10,834 | 99.8% | 11% | 98% | 99.7% |
| attention 2 / 4 layers | same as FFN 2 / 4 | | | | | |
| FFN M8 1 layer | 313 | 1,522 of 2,108 | 29% | 16% | 17% | 23% |
| FFN M8 2 layers | 933 | 4,399 of 6,176 | 32% | 14% | 17% | 22% |

**Reading.**

- In the tiny stacks almost all partition-DP and merge work sits under unit-M
  states, and the closed forms remove it.
- Loop-choice work is not removed. It sits in group-stage and M > 1 states
  above the terminals.
- In the M8 stacks, most work is at M > 1. The closed forms remove a sixth to
  a third.
- These are ledger counts, not wall time. The cost of evaluating the closed
  forms (a few divisor loops per capacity) is not charged.
- An online opt-in substitution with witnesses and replay is required before
  any speed-up is claimed.

## 16. Online exact-response substitution

`exact_search.py` is an opt-in variant of `curve()`.

**How it works.**

- **Adaptation in memory.** The solver is adapted in memory, as in
  `unified_search.make_kernel`, and `graph/curve.py` is unchanged.
- **The hook.** It runs right after the scalar-leaf rule. A state recognised
  structurally as a unit-M chain returns its closed-form frontier
  (`elementwise_chain.predict`) instead of recursing.
  - Activations carry the graph's row ranks, which are the ranks shared by
    every produced tensor. Weights carry none.
  - Every ambiguous state falls back to search.
- **Frontier.** It is scanned upward to the first zero-traffic point, and
  states differing only in names share it.
- **Witnesses.** A closed-form point carries `('exact', key, c, q)`. After
  the root solve, `expand` replaces each such note by the native witness of
  that state:
  - the plain solver is run on the state's sub-graph;
  - its result is matched by (capacity, traffic);
  - a failed match raises an error, which would refute the closed form.
- **Correctness of the speed-ups.** Caching `group` and `reachable_tiles` and
  precomputing loopable segments change no value. All six frozen prediction
  sets were re-checked identical.

**Correctness** (`exact_search.py check`).

- For all 8 cases, the root curve is identical to the baseline.
- Every root frontier point replays exactly in the cell-level executor after
  expansion:
  - 3, 5, 5, 5 for FFN 1-4 layers;
  - 5 for attention-4;
  - 14 for FFN M8-1 and 15 for FFN M8-2, run on the server
    (`server_m8/check.jsonl`).
- Each case expanded at least one closed-form state, so the replay does
  exercise substituted points.

**Frontier-only speed** (`exact_search.py bench`). These historical times
exclude native witness recovery. Each measurement is a fresh process,
with three repeats; the table gives the median. Closed-form time is the time
spent in the hook.

| Case | Baseline | Exact | Speed-up | Hook time | Peak RSS (base/exact) | Hits/checks |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| FFN 1 layer | 0.006 s | 0.005 s | 1.18× | 0.002 s | 21/25 MiB | 71/110 |
| FFN 2 layers | 0.045 s | 0.021 s | 2.17× | 0.012 s | 21/25 MiB | 353/448 |
| FFN 3 layers | 0.450 s | 0.102 s | 4.39× | 0.079 s | 23/26 MiB | 1,311/1,462 |
| FFN 4 layers | 3.849 s | 0.566 s | **6.81×** | 0.480 s | 32/34 MiB | 4,973/… |
| attention 2 / 4 layers | 0.045 / 3.878 s | 0.021 / 0.580 s | 2.18× / 6.69× | | | |
| FFN M8 1 layer | 0.053 s | 0.056 s | 0.94× | 0.011 s | | 250/974 |
| FFN M8 2 layers | 0.264 s | 0.251 s | 1.05× | 0.039 s | | 786/2,864 |

Local machine, `exact_bench_local.jsonl` and `exact_bench_m8_local.jsonl`.
The earlier server timings of the unoptimised hook agree in direction:
M8-1 0.14 → 0.17 s, M8-2 0.62 → 0.68 s.

**Reading.**

- **Tiny stacks.** The speed-up grows with depth. In FFN-4, partition-DP
  transitions fall from 593,020 to 959. Most of the remaining time is the
  Python closed form itself, at 85% of the exact run.
- **M8 stacks: no speed-up.** Work falls by 13-31%: cache misses
  2,108 → 1,841 and DP transitions 3,770 → 2,672 in M8-1. That is consistent
  with the offline audit (§15). The remaining work is at M > 1 states: loop
  choices over M tiles, weight slices under F and D loops, and their merges.
- **The measured mechanism is the work distribution.** In these tiny roots,
  unit-M descendants account for most of the original work; in the two M8
  controls, much remains in M > 1 states. This observation does not prove
  that speedup decreases monotonically with M or that all real operators
  have M > 8. Row extent depends on the operator, execution phase and tiling.

**Consequence.** Unit-M substitution is a correct, measured speed-up only
where unit-M work dominates. To matter at realistic M, the expensive M > 1
states need either:

- an exact response (§12 shows that this is the full loop-order problem for
  one op); or
- a pruning bound that removes whole M > 1 subtrees. §14's operator bound is
  the candidate originally proposed here. Its shared-DAG work accounting is
  now complete in §17; it is not a pending experiment.

### 16a. Complete native mapping generation: timing closure

The existing four controls were remeasured with `witness=True` on both arms.
The exact arm expands **every root frontier witness**, with one initially
empty recovery cache shared across root points in that worker. Generation
time includes search and the baseline-solver calls inside `expand()`.
Executor replay is timed separately after generation. Kernel construction
(about 12.6 ms for the exact arm), imports and graph construction are outside
generation, as in the loop-closure pilot; setup-inclusive times are also saved.
This is native graph-grammar mapping generation, not hardware code generation.

There are three fresh-process repetitions per case/arm, alternating arm order,
with `PYTHONHASHSEED=0`, grammar v2 and partition DP. Python is 3.14.2 on local
Darwin arm64. All 24 runs complete. The 39 distinct case/frontier points agree
across arms and all **234/234** executions, including repeated controls,
replay with exact numerical outputs, traffic and peak occupancy. Every exact
run exercises placeholders, and no placeholder remains after recovery.

| Case | Baseline native generation | Exact search with placeholders | Recovery | Complete exact generation | Generation speedup |
| --- | ---: | ---: | ---: | ---: | ---: |
| FFN-4, M=2, d=f=2 | 3.9924 s | 0.5962 s | 0.0087 s | 0.6048 s | **6.60×** |
| Attention-4 proxy, M=p=d=2 | 3.9883 s | 0.5862 s | 0.0087 s | 0.5949 s | **6.70×** |
| FFN M8-1, d=4, f=8 | 0.0620 s | 0.0653 s | 0.0082 s | 0.0735 s | **0.84×** |
| FFN M8-2, d=4, f=8 | 0.3042 s | 0.2975 s | 0.0155 s | 0.3126 s | **0.97×** |

Each column is its own median; component medians need not sum to the median
total. Including kernel setup, the tiny-case ratios are 6.46× and 6.57×.
Replay medians are about 7 ms for the tiny cases, 96–98 ms for M8-1 and
210–214 ms for M8-2, and are excluded from both generation arms.
The M8-2 exact times are 0.5154, 0.3019 and 0.3126 s; the slower first run
is retained, with no selective rerun. These are small local timing samples.

Recovery is cheap here because only selected root witnesses are expanded:
three placeholders share one conditional recovery state in each tiny case;
M8-1/M8-2 recover five/six states. It does not re-solve every substituted state.
Thus the tiny positive result survives complete witness recovery. It remains
a restricted positive result, and the M8 controls still show no benefit.

The structural reason for the positive case is more specific than small M.
With M=1, distinct feature ranks along a dense chain and at most one intervening
elementwise op, a nontrivial shared loop spans at most two contractions and
their intervening op. The possible patterns are `c`, `e`, `cc`, `ce`, `ec`,
`cec`, whose conditional responses are already exact. A boundary DP needs only
the boundary position and whether its activation is retained. At fixed caller
context and capacity, this gives O(n d²) candidate work, where d bounds the
reachable tile-domain size; full-frontier enumeration and all outer residency
contexts require additional accounting. This is the restricted argument in the
[independent review](https://github.com/HaoningJiang-space/accelforge-streaming-dse/blob/3da98687/research/index_coupling/CLOSURE_REVIEW.md).
At M>1, a common M loop can span the entire chain and couple its weight
reservations. The bounded-span proof no longer applies; its failure is not
an impossibility proof for a faster M>1 algorithm.

Records: `results/contraction_oracle/exact_mapping_local.jsonl`, with sibling
`.manifest.json` (source hashes and timing contract) and `.summary.json`.
This closes the existing measurement gap; no search rule or default changed.

```sh
python -m research.index_coupling.response.experiments exact-mapping-bench NEW.jsonl 3 \
  ffn_forward_l4 attention_forward_l4 ffn_forward_l1_m8 ffn_forward_l2_m8
```

## 17. Operator bound on the shared call DAG: why edge pruning saves little at M > 1

`op_projection.py work` repeats `c2_bound_audit.analyze`'s ordered shadow
policy:

- the captured iteration order;
- the incumbent is the frontier of the preceding actual candidate curves;
- anchors are never cut;
- a proper choice is cut when its bound is dominated by the incumbent;
- saved work is the exclusive work of states made unreachable from the root.

The bound is either C2's slot bound or its pointwise max with the lifted §14
operator bound. The slot column reproduces C2_BOUND_RESULTS.md: 20.31% of DP
transitions in FFN-4, and 0.03% and 0.48% in the M8 stacks. See
`op_bound_work.jsonl`.

| Case | Cut edges, slots / op | Saved DP transitions, slots / op | Saved loop choices, slots / op |
| --- | --- | --- | --- |
| FFN 1 layer | 36 / 40 | 13.2% / 15.8% | 8.2% / 11.5% |
| FFN 2 layers | 121 / 133 | 11.6% / 12.7% | 1.5% / 3.4% |
| FFN 3 layers | 392 / 413 | 22.7% / 22.9% | 0.6% / 1.3% |
| FFN 4 layers | 1,277 / 1,307 | 20.31% / 20.34% | 0.2% / 0.5% |
| attention 2 / 4 layers | as FFN 2 / 4 | | |
| FFN M8 1 layer | 1,028 / 1,459 | 0.03% / **2.9%** | 0.04% / **9.8%** |
| FFN M8 2 layers | 3,059 / 4,116 | 0.48% / **2.1%** | 0.36% / **4.7%** |

**Result.** In the M8 stacks the operator bound cuts 35-42% more edges and
multiplies the saved work by 4-100×. In absolute terms the saving is still
2-10%.

**Mechanism: confluence of the retention lattice.**

- A loop-child solve state is removed only when *every* incoming edge is
  cut.
- Retention and loop order commute. Keeping W1 at an outer loop and W2 at an
  inner one reaches the same state as the reverse; tiling M then F reaches
  the same extents as F then M.
- Among loop-children:
  - FFN M8-1: 1,034 of 1,084 (95%) are reached from parents with different
    resident sets or extents, and 617 have five or more parents;
  - FFN M8-2: 2,863 of 3,143 (91%) are, and 1,693 have five or more parents.
- Cutting one parent's edge therefore rarely removes a state.

**Consequence.** Per-edge pruning is the wrong granularity at M > 1. Work can
fall only through state-level reasoning, of two kinds:

- **Fewer distinct states.** Canonicalise retention orders that provably
  reach equivalent responses. This is search-space reduction, not pruning.
- **Removing a state from every context at once.** For example, a state-level
  bound dominated in all of its parents' incumbents, which needs a
  search-order discipline that makes those incumbents available.

The closed forms and bounds remain correct and useful where work sits under
unit-M states (§16: 6.8× on FFN-4). They do not address the M > 1 lattice.

## 18. Recorded-order pruning and hindsight edge selection

`op_projection.py work` also reports three diagnostics on the shared call DAG
as in §17. The original all-order ceiling interpretation of `oracle` was too
strong; the archived numbers are unchanged by the scope correction below.

| Mode | Bound used | Order |
| --- | --- | --- |
| `perfect` | exact child curve, proper choices only | the captured order, with the ordered incumbent |
| `perfect_any` | the same, with anchors also cuttable | captured |
| `oracle` | none: keep the first action attaining each final parent frontier point | first attainment in the captured action order |

An exact child response limits sound lower-bound rejection against the same
captured incumbent, giving the `perfect` / `perfect_any` recorded-policy
controls. `oracle` is a particular hindsight selection of attaining actions.
It does not optimize among all tied witnesses to minimize shared reachable
work, and so is not an established upper bound for arbitrary edge selection
or arbitrary execution order. No such all-order bound has been proved here.

Figures are saved DP transitions, saved Pareto candidates, and states made
unreachable by `oracle`. The first five data columns are DP, the next two are
Pareto (`op_bound_work.jsonl`).

| Case | slots | op | perfect | perfect_any | oracle | Pareto, perfect | Pareto, oracle | Unreachable (oracle) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| FFN 1 layer | 13.2% | 15.8% | 15.8% | 24.0% | 37.9% | 15.9% | 37.2% | 92 of 271 |
| FFN 2 layers | 11.6% | 12.7% | 26.4% | 28.9% | 43.8% | 25.9% | 42.9% | 268 of 1,052 |
| FFN 3 layers | 22.7% | 22.9% | 55.0% | 55.4% | 71.9% | 52.3% | 69.1% | 1,349 of 3,221 |
| FFN 4 layers | 20.3% | 20.3% | 77.1% | 77.2% | 87.8% | 74.4% | 85.5% | 7,169 of 10,834 |
| FFN M8 1 layer | 0.0% | 2.9% | 16.3% | 24.4% | 42.3% | 17.8% | 38.6% | 821 of 2,108 |
| FFN M8 2 layers | 0.5% | 2.1% | 17.8% | 19.4% | 35.1% | 21.7% | 37.5% | 1,745 of 6,176 |

Attention matches FFN at equal depth.

**Reading.**

- **M8.** Exact-child rejection saves 16-24% of DP work under the recorded
  policy. The selected hindsight policy saves 35-42%. These are exclusive DP
  counters, not time fractions. Taking their reciprocals does not establish
  a wall-time speedup bound: other work, unequal state costs and pruning
  overhead must also be measured.
- **Tiny stacks.** The ceiling is high, 77-88% for FFN-4. There, unit-M
  substitution (§16) already obtains most of it.
- **The remaining 58-65% at M8 stays reachable under this hindsight policy.**
  It has not been proved necessary under every optimal witness selection.
- Cheaper state evaluation and shared computation remain possible research
  questions; these diagnostics establish neither their impossibility nor
  a reason to start another solver after the current consolidation decision.
