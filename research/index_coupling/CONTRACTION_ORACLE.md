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

In 21 of the 57 complete cases the grammar is above the schedule optimum,
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
- **Grammar-level counterpart.** Derive the grammar's own single-contraction
  curve in closed form and check it against `grammar` here. The grammar
  column already contains the data for this.
