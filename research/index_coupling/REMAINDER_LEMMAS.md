# Two lemmas on conditional states: remainder sufficiency and infeasible groups

Scope: the recurrence in `graph/curve.py` (`_solve`, `cut_dp`, `_group_curve`)
with these settings:

- exact frontiers (`grid=None`) and `max_capacity = ∞`;
- no `whole_span_cuts` and no root constraint;
- single-writer spans, or the enumeration fallback, which treats both the same
  way below.

Both lemmas are statements about this grammar's responses, not about physical
optimality. Evidence for the finite checks: REDUNDANCY_RESULTS.md §5 and
`results/redundancy/*.suff.json`, `*.empty.json`.

## Notation

A state is σ = (entry, S, e, R, W):

- entry ∈ {solve, group};
- S is an ordered span of operators;
- e is the current extent of each rank;
- R is the set of resident (external) tensors, after projection to S;
- W is the set of owned writes, after projection to the outputs made in S.

Let T(S) be the tensors accessed in S, and let L = T(S) \ R be the live
tensors. For an operator o, let D(o) be its iteration domain: every rank it
accesses.

**The remainder ρ(σ)** is the labelled structure made of the following:

- the operators of S, in order, each with its domain D(o);
- the live tensors t ∈ L, each with:
  - its rank set;
  - the operators that access it, marking the one whose output it is;
  - its global flags (produced, consumed, number of consumers);
  - whether t ∈ W;
- the extents e and full sizes of the ranks in ∪D(o).

An isomorphism of remainders is a triple of bijections, on operators, live
tensors and ranks, that preserves the operator order and every listed
incidence and label.

## Lemma 1 (remainder sufficiency)

If ρ(σ) ≅ ρ(σ′) under φ, then σ and σ′ have the same frontier F(σ) = F(σ′)
as a set of (capacity, traffic) points. Applying φ to every operator, tensor
and rank in a witness of σ gives a witness of σ′ with the same cost.

Resident tensors therefore influence a state only through the operator
domains D(o). Their identities, number and sizes do not matter.

**Proof.** We use induction on the recursion. Every recursive call strictly
shrinks either the span, or the extent product at an equal span:

- a partition child is a proper sub-span;
- a loop child has a tile b < e_v.

So the order is well-founded. It suffices to show two things:

1. every quantity a step computes is a function of ρ(σ) that commutes with φ;
2. every recursive call goes to a child whose remainder is the image under φ
   of the corresponding child of σ′.

The steps are listed below; line references are to `graph/curve.py` at
`66ed94ca`.

- **Projection (`projected`).** Unused ranks are given extent 1, and
  R ← R ∩ T(S), W ← W ∩ made(S). "Unused" is the complement of ∪D(o). The
  projection therefore preserves ρ.
- **Scalar leaf.** If every t ∈ L has size 1 at e, the response is (|L|, 0).
  Here |L| and the sizes depend only on ρ.
- **Independent split (opt-in).** The condition is that every tensor shared
  by two operators of S lies in R. Equivalently, no live tensor is accessed
  by two operators. This is a property of ρ. The children are singleton
  spans with the same R.
- **Partition enumeration and the cut DP.**
  - The shared and crossing tensors are filtered to live ones.
  - Each charge uses only these live-tensor facts:
    - the size at e;
    - the writer position;
    - whether the tensor is consumed;
    - whether it is in W;
    - the numbers of user and writer groups;
    - for the DP, the first use before the cut.
  - The two option filters use the produced/consumer-count labels and the
    reader/writer incidence of dropped (live) tensors.
  - Retained capacity `across` sums the sizes of kept live tensors.
  - The child state is (group, e, R ∪ K, W ∪ written). K and the written
    set are sets of live tensors, so the child's remainder is ρ(σ) restricted
    to the group's operators, with K deleted and W extended. φ maps this to
    the corresponding child of σ′.
- **Loop step (`_group_curve`).**
  - The candidate ranks are ∩_o D(o). This uses the full domains, and it is
    the only point where resident tensors' ranks enter.
  - The candidates are filtered by e_v > 1, and by v lying in every
    non-resident tensor that is both made and read inside the group.
  - The lacking set is {t ∈ L : v ∉ rank set of t}.
  - The keep/refetch charges use the sizes at e, the trip count and whether
    an operator of the group writes t.
  - The child state is (group, e[v ← b], R ∪ kept, W). It corresponds as
    before, with the tile b identical because e_v = e′_{φ(v)}.
- **Composition.** max/sum merging and Pareto pruning act on the (c, q)
  values only. Iteration order can change which witness is kept for a tied
  point, but not the point set.

The global quantities (`spill_cost`, the tile domain, the option flags) are
the same for σ and σ′. Each step is equivariant under φ, so by induction
F(σ) = F(σ′), and witnesses map under φ. ∎

**Why the operator domains are needed.** If the rank edges of resident
tensors are deleted as well, the census finds states with equal reduced
structure but different frontiers. Examples are fork_kk (8 classes),
fork same6 (1,384) and FFN training (15). With a resident tensor's ranks
removed, a rank can wrongly appear to be outside an operator, which changes
the common loop set.

**Finite check.** A Weisfeiler-Leman label of ρ (op positions, live-tensor
labels, rank sizes/extents, domain edges) separates every differing pair on
all 47 censuses. The check finds 0 violations, which is consistent with the
lemma. The label is isomorphism-invariant, so the lemma predicts this.

**Consequences.**

- The Fork quotient, alpha-equivalent spans and the ancestor control's
  (k+1)² classes are all special cases of sharing responses between
  isomorphic remainders.
- Name-based canonicalization misses rank renaming. That is why
  `canonical_spans` finds nothing in FFN or attention stacks, whose layers
  use distinct rank variables.

## Lemma 2 (infeasible group queries)

Let σ be a group state, and define the candidate ranks

V(σ) = { v ∈ ∩_{o∈S} D(o) : e_v > 1 and v ∈ ranks(t) for every t ∈ M \ R },

where M is the set of tensors that are made in S and read by an operator in S.
Then F(σ) = ∅ if and only if some t ∈ L has size > 1 at e and V(σ) = ∅.
Solve states are never empty.

The test needs only S, e and R ∩ M; residency of every other tensor is
irrelevant. It runs in time linear in the span's incidence.

**Proof.** We first show that every solve state is nonempty, by induction in
the same order.

- If all of L is scalar, the leaf returns a point.
- Otherwise, consider the partition into singletons, with every shared live
  tensor kept. This choice passes both option filters, because those filters
  reject only dropped tensors.
- Each singleton group {o} is nonempty:
  - If its live tensors are all scalar, the group leaf applies.
  - Otherwise, some live tensor has a rank v with e_v > 1, and v ∈ D(o).
    Also M = ∅, because an operator's output is the last access key and is
    never also its input. So v ∈ V.
  - `tile_sizes` always contains 1 for e_v > 1: the halving sequence ends
    at 1, and 1 divides every extent. So at least one tile exists.
  - The inner solve is nonempty by induction.
- max/sum merging of nonempty frontiers is nonempty (max_capacity = ∞), and
  the cut DP realizes the same partition.

Now the group state.

- If all of L is scalar, the group leaf returns a point.
- Otherwise the response is the union, over v ∈ V(σ), over tiles and over
  keep bits, of the shifted inner solve frontiers.
  - If V(σ) = ∅, the union is empty.
  - If V(σ) ≠ ∅, at least one tile exists, and the inner solve is nonempty
    by the claim above.

This gives the stated equivalence. ∎

**Finite check.** `check_empty_groups.py` predicts emptiness for every
recorded state and compares it with the recorded frontier. See
`results/redundancy/*.empty.json`.

**Consequence.** Callers query a group from the partition enumeration and
from the cut DP, where each group is merged into the prefix. Lemma 2 lets the
caller skip an empty group before the recursive call. It also skips the
enclosing keep-bit enumeration whenever no kept set can change R ∩ M. The
skipped work adds no point to any frontier, so the response is unchanged.
Infeasible keys are 27-43% of all cache entries in the forks and the FFN and
attention stacks.
