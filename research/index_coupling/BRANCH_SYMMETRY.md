# Downstream dependence changes the symmetry unit and boundary decoration

The next controlled family is X=AB, U_i=X C_i, V_i=U_i D_i, with literal ranks
X(I,K), C_i(K,L), U_i(I,L), D_i(L,N), V_i(I,N). Each independent branch now has
two dependent operators. An optional single-writer join computes the elementwise
product of all V_i. This join is deliberately commutative under Graph's einsum
semantics; it is not an implementation of a shared multi-writer accumulator.

## 1. The cost-preserving action is on whole branches

Swapping E_i/E_j alone is not an automorphism after the tails are attached.
Swapping E,H,C,U,D,V together is. The shared X and producer remain fixed.
The symmetric product join preserves this action: its input set is permuted,
its output and projections stay fixed. Giving only one branch a tail destroys
the swap. These statements are certified against the entire graph incidence,
not inferred from consumer counts or equal byte sizes.

`is_automorphism` verifies bijections of all operators/tensors, literal rank
projections, the output role, and each operator's complete input set. Permuting
input ports is valid here because the model multiplies operands in an einsum;
it does not authorize permuting arguments of an arbitrary noncommutative op.

Let sigma=(S,ext,R,W,entry) be a conditional state and let pi be such a certified
automorphism. Use the order-complete grammar over every topological order of S,
with no externally fixed order constraints. Relabeling every group, loop and
tensor of a plan gives a plan for pi(sigma):

- dependency legality and scalar-base-case eligibility are preserved;
- common ranks, internal-tensor completion rules and tile choices are preserved;
- input vs partial-sum revisit weights, tensor sizes and boundary writes agree;
- retained capacity, max/sum composition and Pareto dominance agree;
- the inverse permutation reconstructs a plan and its original tensor identities.

Therefore the complete conditional curves agree. Ownership and entry must be
mapped/preserved too. If an outside interface fixes an order, a tensor identity,
or a placement-dependent cost, restrict to the subgroup preserving it. A graph
automorphism alone cannot erase those additional constraints.

To remove redundant orders for ONE fixed state, use its stabilizer (permutations
mapping the decorated state to itself). To reuse responses across states, use
their whole orbit, restoring the selected order and witness names afterwards.
These are different operations. The oracle implements both, while its inner
`curve.py` searches remain ordinary fixed-order calls.

## 2. A continuation boundary with an explicit finite alphabet

For the primary cut experiment, EX has completed. Each two-op branch has
progress 0 (E,H remain), 1 (only H remains), or 2 (both done). No recomputation
is admitted. Resident tensors are chosen ONLY from the continuation's ready
private inputs. X is DRAM-backed if still used; prefix cost is excluded.

Without a join, the per-branch alphabet is:

| Progress | Possible ready private inputs | Number of residency states |
| --- | --- | ---: |
| 0 | C_i, D_i | 4 |
| 1 | U_i, D_i | 4 |
| 2 | none | 1 |

There are nine joint branch types. The symmetric join adds V_i as a ready input
at progress 2, making that row two states and the alphabet ten. Equal HISTOGRAMS
OF THESE JOINT TYPES imply orbit equivalence. Separate histograms of progress
and resident tensor roles need not preserve which branch owns which state.

For m branches, the labeled boundary counts 9^m / 10^m reduce to
binomial(m+8,8) / binomial(m+9,9). Thus m=2 gives 81→45 and 100→55; m=3 gives
729→165 and 1000→220. These are sufficient syntactic orbit counts, not counts
of distinct numerical frontiers, not a minimality theorem, and not a runtime
bound for all recursive states. Internal recursive groups can have different
operator-membership/ownership decorations and require a larger alphabet.

Continuation queries use the induced remaining graph. Its ready tensors are
inputs; its traffic excludes resident-input compulsory reads. This is a clearly
defined suffix response, not an unproved composition of full prefix/suffix
optima or an alias for the old recurrence's internal extra-traffic convention.
Physical replay wraps a conditional plan in the previously tested retaining
loop, restoring caller capacity A and traffic: (c,q) becomes (A+c,A+2q).

## 3. Minimal negative controls found in the preliminary diagnostic

These are seen-data counterexamples, to be reproduced rather than scored as
held-out predictions. All numerical extents are two.

- With EX,E0 complete, pinning ready-branch D0 gives Q(3)=44; pinning D1 in
  the not-yet-started branch gives Q(3)=48. Both have the same progress counts,
  one resident D tensor and the same external footprint. Correlation matters.
- At the full two-branch root, resident {C0,D0} gives Q(3)=64, while {C0,D1}
  gives Q(3)=76. Both have one resident C and one D; the inputs' branch pairing
  matters even after all legal orders have been considered.
- With only branch 0 receiving a tail, {C0} and {C1} need not have equal
  curves. The whole-graph automorphism check rejects exchanging these branches.

The symmetric join is a positive control: dependence/reconvergence alone does
not imply lost symmetry. These results do not say every non-equivalent state
has a different curve; orbit equivalence is sufficient, not necessary.

## 4. Bounded validation plan, fixed before server measurements

`graph/branch_symmetry.py` is a deliberately exhaustive reference, not a new
scalable general-DAG optimizer. It generates topological orders, reduces them
only under certified state stabilizers, and caches decorated-state orbits.
The comparison disables BOTH reductions and enumerates every literal order.
Neither mode changes the core solver or executor. No old P verdict is revised.

Seven jobs, fresh Linux processes, hash seed zero, 60 seconds including replay,
6 GiB address space each, at most four workers:

1. All 81 two-branch continuation states without the join.
2. All 100 continuation states with the join.
3. All 16 full-root C/D residency assignments without the join.
4. All 16 root assignments with the join.
5. All 8 root-input assignments of the asymmetric one-tail graph.
6. Three-branch full root without join, only certified order representatives.
7. Three-branch full root with join, only certified order representatives.

The first five jobs must compare complete curves to literal-order enumeration
and execute every returned quotient point. Root jobs 6/7 have 90 literal orders
and 15 symmetry representatives; they have no separate literal numerical oracle
in this budget. Partial order envelopes after timeout are not optima and are
not counted as equality successes. Keep all attempts, hashes, counters and
replay failures. The primary expected equality/orbit counts follow the stated
action; negative-control differences are exploratory findings from the pilot.

For a future generalization, the state signature must include the full branch
operator-membership mask, joint residency and final-write ownership. A shared
multi-writer partial sum is outside the current single-writer executor and
requires a separate model/proof; attaching a symmetric join does not test it.
