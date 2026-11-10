# Releasing a private input is not a local operation, and the grammar is not monotone in residency

Question (WORK_ATTRIBUTION.md §2): in layered stacks, almost all work is in
nontrivial states that differ in which private weights are resident. Is
F(sigma), with weight W live, a function of F(sigma') (W resident) and local
data about W? If so, the 2^(2L) retention combinations would separate.

Source `private_lift.py`; records in [results/private_lift/](results/private_lift/).
Run over all 47 censuses, 6 GiB and 900 s per case. Pairs (sigma, sigma') are
taken from the recorded states, where W is:

- live and nonscalar;
- accessed by exactly one operator of the span;
- not produced inside the span.

Everything else in the state is identical.

## 1. No local lifting

For each descriptor of W, we count classes with equal F(sigma') and equal
descriptor whose F(sigma) differ. These are violations, given as violations
over classes, solve entries only.

| Case | solve pairs | size of W | plus its operator | plus lacked axes |
| --- | ---: | ---: | ---: | ---: |
| FFN forward 4 layers | 12,725 | 96/109 | 231/370 | 231/370 |
| FFN training 1 layer | 7,174 | 102/266 | 145/727 | 141/756 |
| residual depth 24 | 829 | 9/88 | 9/116 | 9/116 |
| fork 6, same role | 148,026 | 23/41 | 45/135 | 45/135 |
| fork kkk, extents 4 | 7,156 | 124/215 | 251/901 | 243/952 |
| ancestor k=8 | 16,472 | 0/28 | 0/28 | 0/28 |

Only the fully symmetric ancestor control lifts locally. An FFN example:

- Releasing W2_1 in the one-layer span EH1..EY1 leaves the frontier
  unchanged: (3,6),(4,0).
- Releasing W1_1 in the span EH0..EH1 doubles the traffic at C=3: 6 → 12.

The partner frontiers and the weight sizes are the same. The cost of
releasing a weight depends on which loops the rest of the span wants to take.
This is the conditional residency value V_X of P21 again, now for weights.

## 2. Keeping a weight whole is never the whole story

We classify solve pairs by how F(sigma) relates to F(sigma'):

- *free*: F(sigma) = F(sigma'), so releasing W costs nothing;
- *keep*: F(sigma) is F(sigma') shifted by |W|, so keeping W whole is optimal
  at every capacity;
- *between*: anything else.

| Case | free | keep | between |
| --- | ---: | ---: | ---: |
| FFN forward 4 layers | 20% | 0% | 80% |
| FFN training 1 layer | 61% | 0% | 39% |
| residual depth 24 | 45% | 0% | 55% |
| fork 6, same role | 87% | 0% | 13% |
| fork kkk, extents 4 | 37% | 0% | 63% |

The pure shift never occurs in any of the 47 censuses. A live weight's
response always mixes streaming and partial retention.

## 3. The grammar is not monotone in residency

Making W resident should never hurt. That is the left side of the sandwich
Q'(C) <= Q(C) <= Q'(C - |W|). For solve entries, the right side should also
hold, because keeping W for the whole span costs |W| and no traffic. Both
sides fail in some cases:

| Case | solve violations | group violations |
| --- | ---: | ---: |
| FFN forward 4 layers | 0 | 24 |
| FFN training 1 layer | 46 | 259 |
| residual depth 24 | 90 | 90 |
| fork 6, same role | 40 | 148 |

**Group entries.** A group must loop unless every live tensor is scalar.
Releasing W can leave no legal loop axis, which makes the group infeasible
(Lemma 2 of REMAINDER_LEMMAS.md). Meanwhile sigma' takes the scalar leaf.

**Solve entries: the mandatory scalar leaf.** When every live tensor is
scalar, `_solve` returns (number of live tensors, 0) and does not allow a
partition. All ten solve violations in residual depth 4 (independent input) were checked by hand:

- *Direct (6 of 10).* With W resident, the remaining tensors are all scalar,
  so the leaf counts all of them (capacity 3), while sigma can partition
  (capacity 2).
- *Nested (4 of 10).* An example is EH1..EH3 at extents (1,2,2). After a unit
  K loop, W1 (L,K) still has size 2, so sigma's child partitions into
  singletons and reaches capacity 3. With W1 resident, the same child is all
  scalar and is forced to the leaf at capacity 4. At C=3 the extra traffic
  rises from 0 to 4.

The violations in the other cases are counted, not individually traced.

## 4. Consequences

1. **Separating retention combinations is refuted.** Releasing a private
   weight is not a local transform of the response. Any separable treatment
   of weights must carry a non-local context: at least which loop axes the
   enclosing span uses.
2. **The scalar leaf breaks residency monotonicity.** Monotonicity is the
   premise behind several arguments:
   - dominance pruning across residency contexts;
   - "keeping more never hurts";
   - the nonnegativity of P21's V_X.

   The fault lies in the grammar's leaf, not in the physics. Allowing
   partitions at all-scalar spans, where the leaf would give the per-operator
   bound d, would restore monotonicity at this point. It would also change
   archived curves and frozen verdicts, so it must be a separately versioned
   grammar and is not changed here.
3. **Exact equivalence of non-isomorphic states is not the lever for
   stacks.** Neither local lifting nor isomorphism covers them, which leaves
   two options:
   - dominance or bounds over retention contexts, which first needs a
     monotone grammar;
   - accepting their combinatorics as intrinsic to this model.
