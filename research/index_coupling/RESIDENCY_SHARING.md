# Sharing across residency contexts: ceiling and structure

Question: is the M8 search work redundant across the weight-residency
contexts in which the same sub-problem is solved? If so, a representation
shared across contexts could remove it. This follows Codex's conclusion in
LOOP_CLOSURE_RESULTS.md §5.

Offline only. Command: `python -m research.index_coupling.response.experiments residency`.
Records: `results/contraction_oracle/residency.jsonl`.

## 1. Ceiling: contexts are the dominant multiplicity

A *context-free key* is (stage, ops, ext, owned, constrained). Its
*contexts* are the external sets seen with it in the archive. Solving each
key once, charging its costliest member, would remove the following share of
each exclusive counter:

| Case | States | Keys | DP transitions | Loop choices | Pareto candidates |
| --- | ---: | ---: | ---: | ---: | ---: |
| FFN 4 layers | 10,834 | 742 | 98.7% | 43.6% | 97.5% |
| FFN M8 1 layer | 2,108 | 469 | 84.1% | 69.9% | 71.6% |
| FFN M8 2 layers | 6,176 | 1,230 | 87.6% | 70.4% | 81.6% |

This is far above the 35-42% DP savings of the tested hindsight edge policy
(CONTRACTION_ORACLE.md §18) and the residual path redundancy in
PREFIX_DOMINANCE_RESULTS.md. That policy is not a proved universal pruning
ceiling. Residency multiplicity is where much of the measured M8 work
is. The ceiling is not achievable unless one key's computation can serve all
of its contexts.

## 2. Three candidate sharing structures, tested on weight contexts

Here contexts are compared for solve keys whose external sets differ only in
weights.

**(a) Gap invariance.** F = LB + G with G independent of weight residency.
LB, the operator-projection bound, is per-op local. The gap is identical
across contexts in 21 of 414 keys (M8-1) and 60 of 1,088 (M8-2).
**Rejected.**

**(b) Locality of interactions.** For weights a, b, the second difference is

    F(R+a+b) - F(R+a) - F(R+b) + F(R).

LB is additive across ops, so the gap has exactly the interactions of F.
Pairs whose owning operators are more than two ops apart still interact:
52 of 84 in M8-2, and 4,170 of 10,096 in FFN-4. **Rejected.**

**(c) Pure shift.** A context's curve equals the most-resident context's
curve shifted by (s, t).

| Case | M = 1: identical / shift / other | M > 1: shift / other |
| --- | --- | --- |
| FFN 4 layers | 114 / 382 / 4,157 | none |
| FFN M8 1 layer | 17 / 130 / 15 | 80 / **250** |
| FFN M8 2 layers | 63 / 345 / 136 | 204 / **898** |

Every shift is (1, 0): one more cell and no traffic change. That is the §11
rule, under which a streamed weight adds one operand cell. **At M > 1, where
the work is, 76-81% of contexts change shape.** Rejected there.

## 3. Mechanism

Two properties of the grammar explain why contexts at M > 1 are genuinely
different problems.

1. **A streamed weight at M > 1 opens a new trade-off.** It must either be
   re-fetched per row tile, costing (m / c_M − 1)|W| traffic, or have a slice
   reserved across rows, costing cells. The trade-off adds breakpoints, so
   the curve changes shape rather than shifting. At unit M no rows exist, so
   streaming costs exactly one cell (the shift in (c)). §12's keep-level model
   is the single-op form of this trade-off.
2. **A reservation at a shared loop charges every op below it.** A slice kept
   at an outer M or F loop occupies cells throughout that loop's subtree.
   Weights of distant ops therefore compete for one capacity budget, a
   knapsack, which gives the non-local interactions in (b).

An exact representation shared across contexts must account for these
reservation conflicts and per-weight keep/re-fetch trade-offs. This does not
prove it must enumerate the same choices as the current search.

## 4. Conclusion

- In the measured M > 1 comparisons, 76-81% of contexts do not match the
  reference response by identity or a pure shift. Different response shapes
  alone do not establish that their computations cannot share work.
- Their interaction is global, because of shared reservations.
- The 84-88% hypothetical saving measures the cost of context multiplicity,
  not a proved amount of unavoidable work. No cheap exact sharing structure
  was found among the three tested candidates:
  - invariant gap: no;
  - local interactions: no;
  - shift: only at unit M, where closed forms already apply.
- This does not prove that no symbolic solver could share work. It does
  show that any such solver must reason about the reservation knapsack
  itself, and it would not be a reuse of existing responses.
