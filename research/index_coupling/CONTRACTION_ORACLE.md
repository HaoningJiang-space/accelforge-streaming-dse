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

**What this gives C2** (`c2_exact_children.jsonl`). Covered choices are the
proper retention choices whose child node has a closed form. For those, the
exact child curve replaces C2's bound. For the others, the slot bound is kept.
The counts below are ideal exclusions, measured as in CHAIN_THRESHOLD.md §6
with the final frontier as incumbent.

| Case | Proper choices | Covered | Ideal exclusions, slot bound | Ideal exclusions, exact where covered |
| --- | ---: | ---: | ---: | ---: |
| FFN 1 / 2 / 3 / 4 layers | 118 / 446 / 1,414 / 5,050 | 96 / 392 / 1,328 / 4,932 | 105 / 372 / 1,055 / 2,865 | 112 / 430 / 1,388 / **5,014** |
| attention 2 / 4 layers | 446 / 5,050 | 392 / 4,932 | 372 / 2,865 | 430 / **5,014** |
| FFN M8 1 / 2 layers | 2,388 / 7,177 | 910 / 3,043 | 1,383 / 3,955 | 1,595 / 4,797 |

**Interpretation.**

- **Most of these children need no search at all.** In the tiny stacks,
  88-98% of retention choices have a child with a closed form that costs a
  few divisor loops.
- **Pruning becomes nearly ideal.** In FFN-4, 5,014 of 5,050 choices are
  excluded, against 2,865 with the slot bound. These are ceilings, because
  the incumbent is the final frontier. The real saving depends on search
  order.
- **The form is grammar-specific.** It is exact for this loop grammar (v2,
  halving or divisor tiles, partitions by cut DP), not for physical
  schedules (§3).

**Uncovered.**

- Children with M > 1. These are most M8 choices; the parent row loop adds an
  outer dimension.
- Group-stage queries.
- Training graphs, where activations are reused across forward and backward.
