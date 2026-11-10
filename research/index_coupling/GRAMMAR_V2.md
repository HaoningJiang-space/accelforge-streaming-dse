# Grammar v2: a residency-monotone scalar leaf

Analysis and proofs only; no solver change is made by this note. v1 is the
grammar of `graph/curve.py` at `b84ad727`. It stays the default, and every
archived curve and frozen verdict refers to it. v2 differs only at states whose
live tensors are all scalar.

Scope is the same as REMAINDER_LEMMAS.md:

- exact frontiers, `max_capacity = ∞`;
- no root constraint;
- single writers;
- serial execution in the fixed operator order, with no recomputation.

## 1. Diagnosis: which rules break monotonicity

Write F(σ) for the response of a state σ = (entry, S, e, R, W), and
Q_σ(C) for its least extra traffic at capacity C. **Residency monotonicity**
means that Q_{σ+W}(C) ≤ Q_σ(C) for every C and every live tensor W, where
σ+W is σ with W added to R.

Grammar rules either add options or replace all options by one answer when a
predicate holds. A replacing rule whose predicate can become true as R grows
removes options from σ+W that σ had. Such a rule preserves monotonicity only
if its single answer is optimal among the options it replaces. In that case it
is *exact*.

| Rule in v1 | Predicate | Exact? |
| --- | --- | --- |
| scalar leaf, one operator | all live scalar | yes: (\|L\|, 0) attains the operand bound and zero traffic |
| independent split (opt-in) | every shared tensor resident | yes, projection argument (SOLVER_SCALING.md) |
| infeasible-group pruning (opt-in) | Lemma 2 | yes: it only removes empty responses |
| **scalar leaf, several operators, solve entry** | all live scalar | **no** |
| **scalar leaf, several operators, group entry** | all live scalar | **no** |

The two inexact rules return (|L|, 0), which keeps every live cell for the
whole span. LIFT_RESULTS.md §3 hand-checks all ten solve violations in
residual depth 4 (independent input) and traces each one to these rules:

- *direct*: σ+W itself becomes all-scalar;
- *nested*: a child of a loop becomes all-scalar.

The group-entry violations recorded there are of the other inequality, Q(C) ≤
Q'(C − |W|). That inequality is not monotonicity, and v2 does not claim it.

## 2. Definition of v2

Let σ have at least two operators and every live tensor scalar at e. For both
entries, v2 sets

F_v2(σ) = S(S, e, R, W),

where S is defined recursively over contiguous partitions:

- **Choices.** Pick a contiguous partition (g_1, ..., g_m) of S. For each live
  tensor shared by two or more parts, choose *keep* or *DRAM*. The trivial
  partition m = 1 is included.
- **Costs.** Partition charges, retained capacity ("across"), ownership of
  final writes and the two option filters are exactly those of `_solve`'s
  partition step (cut DP or enumeration).
- **Parts.**
  - A single-operator part has response (|L_g|, 0).
  - A multi-operator proper part has response S(g, e, R ∪ K, W ∪ written).
  - The trivial part (the whole S) has response (|L|, 0): every live cell is
    held.

States that are not all-scalar keep the v1 rules unchanged, including the
group requirement to loop. Loops are not offered at all-scalar states; Lemma
A shows they would be dominated.

So v2 removes the restriction that an all-scalar multi-operator span must be
held whole. A sequential scalar program may free cells between operators.
Every v2 plan is a v1-style witness (groups, keep and DRAM notes), so the
existing executor can replay it.

## 3. Structure of the scalar response

Let a_i = |access(o_i) \ R| (the operand slots of operator i), and let
d = max_i a_i. For a live tensor t, let f_t and l_t be its first and last use
in S.

MaxLive = max_i ( a_i + |{ t live : f_t < i < l_t, t not accessed by o_i }| ).

**Lemma A (loops are dominated at all-scalar states).** Consider a loop over
a rank v of extent e_v > 1 at an all-scalar state. Such a v is carried only by
resident tensors, because every live tensor is scalar. Suppose the loop keeps
K ⊆ Λ (the live tensors lacking v), has r trips, and its inner solve has point
(c, q). This gives the point (|K| + c, extra(Λ \ K) + r q). Take the inner
plan and also keep every tensor of K across its whole use interval. This is a
partition plan at the original extents with capacity ≤ |K| + c and traffic
q ≤ r q + extra. ∎

**Lemma B (the zero-traffic point is MaxLive).** In v2:

- The least capacity at zero extra traffic is MaxLive, and
  d ≤ MaxLive ≤ |L|.
- *Attained by* singletons that keep every shared tensor. The peak at operator
  i is then a_i plus the kept tensors live across i but not used by it.
- *Optimal because:*
  - Every DRAM choice of a shared live tensor has positive charge: an input is
    refetched once per later user group, and a written tensor is written
    and/or refetched.
  - Coarser parts hold supersets of these cells.
  - Nested partitions with all shared tensors kept reproduce the singleton
    peaks.

The scalar-X bridge (SCALAR_BRIDGE_RESULTS.md) is the special case
MaxLive = d. v1's answer |L| is the trivial partition alone.

**Below MaxLive.** Here the problem is to choose which live scalars travel
through DRAM, with weight 1 for inputs and 2 for partial sums (write plus
refetch), under a fixed operator order. This is a restricted form of **local
register allocation**: straight-line code, k registers, inserting loads and
stores but no reordering. Farach-Colton and Liberatore proved that problem
NP-hard and gave a 2-approximation.

v2 restricts the general problem in one way: retention decisions follow a
hierarchy of contiguous cuts, not arbitrary per-gap choices. The NP-hardness
does not transfer automatically, and the complexity of this restriction is
open. No closed form is claimed for the full scalar curve. It is computed by
the existing cut DP; only its zero-traffic point has a closed form (Lemma B).

## 4. Theorem: v2 is residency-monotone

**Theorem.** For every state σ and every live tensor W, F_v2(σ + W) ⪯ F_v2(σ)
pointwise: Q_{σ+W}(C) ≤ Q_σ(C) for all C. Equivalently, every point of F(σ)
is weakly dominated by a point of F(σ+W).

**Proof.** We use induction on the well-founded recursion order of
REMAINDER_LEMMAS.md (span length, then extent product). It suffices to map
every plan P of σ to a plan P' of σ+W with capacity no larger and traffic no
larger. Construct P' by treating W as resident and taking cases on P's top
step.

1. **σ+W is all-scalar** (W was the only nonscalar live tensor, or σ was
   already all-scalar).
   - If P is a partition, the same contiguous partition is available in S,
     with keep/DRAM choices on the remaining shared tensors. Charges for W
     disappear, and every other charge is unchanged.
     - Each part's response does not increase: by induction, or by Lemma A
       if a part of P was a nonscalar group that looped and its counterpart
       is now scalar.
     - The across sums lose W.
   - If P is a loop (σ is a nonscalar group), Lemma A applied at σ+W gives a
     partition plan of no larger cost. The inner state of that plan is the
     inner state of P plus W, which is covered by induction.
   - If P is σ's own trivial or scalar leaf, then σ+W has the same option
     with |L| − 1 cells.
2. **σ+W is not all-scalar.** Then σ is not all-scalar either, and both use
   the v1 rules.
   - *Partition step.* The shared set loses W. Both option filters reject
     only DRAM choices of a tensor, so removing W cannot make a choice
     illegal. Charges for W disappear and the others are unchanged. Child
     states gain W in R; the induction hypothesis applies.
   - *Loop step.* Legality requires v to be carried by every nonresident
     tensor made and read inside the group. That set loses W, so the
     candidate set only grows. The lacking set loses W, the keep and refetch
     charges for W disappear, and the inner state gains W.
   - *Single-operator leaf.* This rule is exact (Section 1), so its answer
     is at least as good as P'.
   - *Exact opt-in rules.* Independent split and infeasible-group pruning
     return the unrestricted optimum or remove only empty responses, so they
     preserve the claim.
3. **Composition.** max/sum merging is coordinatewise monotone, and Pareto
   pruning preserves weak dominance.

Ownership needs one more check. If W was written inside σ and sent through
DRAM, P charged its final write unless the caller owned it. In σ+W, W is
caller-resident and no such charge arises. Other ownership projections are
unchanged. ∎

**Why v1 fails the same proof.** In case 1, P' would need the partition or
loop option at σ+W, but v1's scalar leaf removes it. This is exactly the
hand-checked violations of LIFT_RESULTS.md §3.

## 5. Consequences

**C1. Conditional residency value.** P21's V_X(c) = Q(c | X in DRAM) −
Q(c | X resident) is nonnegative in v2 for every state. In v1 it can be
negative because of the leaf. The P21 conclusions measured in v1 are not
affected retroactively.

**C2. An exact lower-bound prune for retention choices.** This targets the
stacks' main cost (WORK_ATTRIBUTION.md, LIFT_RESULTS.md). Consider a loop
step over v with r trips and lacking set Λ. Choice K ⊆ Λ contributes

  P_K = { (|K|_cap + c, extra(Λ \ K) + r q) : (c, q) ∈ F(G, e', R ∪ K, W) }.

By the theorem, Q_{R∪K} ≥ Q_{R∪Λ} pointwise. Hence P_K is pointwise above
the curve

  LB_K(C) = extra(Λ \ K) + r · Q_{R∪Λ}(C − |K|_cap).

Suppose LB_K is weakly dominated everywhere by points already found for this
loop step, or for the enclosing state. Then K contributes no frontier point,
and its child solve can be skipped. One extra solve, F(G, e', R ∪ Λ, W),
serves all 2^|Λ| choices.

The rule is exact in v2 and unsound in v1. How much it removes depends on how
tight LB_K is, which only measurement can answer; there is no prediction yet.

**C3. Lemmas 1 and 2 hold in v2.**
- S depends only on the remainder (operators, live tensors, domains, extents,
  ownership), so the proof of Lemma 1 extends.
- An all-scalar group is never empty in v2, which matches Lemma 2's first
  condition.

**C4. Every curve changes only within the scalar region.** Any v2 curve is
pointwise ≤ its v1 curve, because v2 only adds options. Curves can change
wherever an all-scalar multi-operator state is reachable. Comparisons with FFM,
and the frozen P predictions, must name their grammar version.

## 6. What remains before any claim

1. **Literature.** The paper below fixes the complexity context. It does not
   settle the complexity of the hierarchical-cut restriction, which is open.
2. **Minimal implementation.** An option `scalar_leaf='v1'|'v2'`, with v1 the
   default. v2 routes multi-operator all-scalar states of both entries to a
   cached partition-only recursion, and skips loops there.
3. **One decisive check on small graphs:**
   - zero solve-entry monotonicity violations in v2;
   - every v2 frontier point replayed exactly by `simulate_nest`;
   - v2 ≤ v1 pointwise.
4. Only after that, measure C2 on the stacks.

## Reference

M. Farach-Colton and V. Liberatore, *On local register allocation*, Journal of
Algorithms 37(1), 2000. DIMACS TR 97-33.
