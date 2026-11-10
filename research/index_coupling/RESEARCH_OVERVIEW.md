# Research overview after the unified replacement test

This assessment combines the archived results through the branch-symmetry
report at `a7cf85a1` with [ONE_OBLIGATION_RESULTS.md](ONE_OBLIGATION_RESULTS.md).
It distinguishes fixed-order recurrence claims, order-complete claims, and
physical execution checks. The new one-obligation audit itself used base
`046c318c`; the later branch work is separately attributed.

Subsequent joint evidence: [UNIFIED_SEARCH_RESULTS.md](UNIFIED_SEARCH_RESULTS.md)
uses source `b6e2ddbc` and one declared grammar for all three reductions.

The later [remainder implementation](REMAINDER_SEARCH_RESULTS.md), source
`da52c801`, adds exact reuse inside the fixed-order recurrence. Live-tensor
incidence, full operator domains, entry and ownership suffice; resident
identities can disappear and rank names can be changed. Infeasible groups can
also be rejected structurally. All 64 local runs agree with 496 exact replays,
but this separates mathematical compression from implementation benefit:
precheck improves stack time, whereas full remainder matching reduces entries
but slows those stacks and increases memory. Only the highly rank-symmetric
ancestor control shows a large reuse speedup (12,866 entries to 81, 4.08x).
P19 server measurement remains pending. This ordered equivalence is a useful
component, not the dynamic order-complete closure theorem still sought below.

The strongest current research story is **exact conditional resource response**:
which parts of a mapping search can be composed, identified by symmetry, or
replaced by a proved response? A single graph-width law or a scalar fusion
threshold is no longer an adequate statement of the problem.

The first joint D/Q/C test is now complete: 24 arms on one six-op family with
partial symmetry and a downstream join, 1,018,272 equal internal-response
comparisons and 228 exact server replays. A local scalar shared set can be
retained over its live intervals and streamed privately; when that concrete
peak attains the operand-slot bound, it certifies the entire conditional
frontier. This rule is selected inside cut-DP/order-quotient root witnesses
containing the join. It establishes compatibility under one grammar, not a
general-DAG state bound or a dynamic quotient algorithm.

## 1. Three complementary reductions, with different contracts

| Method | Mathematical fact used | What it removes | Boundary of the claim |
| --- | --- | --- | --- |
| Cut DP | Serial composition is sufficient after boundary retention and write ownership are fixed | Explicit continuous-partition enumeration | Does not bound all nested loop/residency contexts |
| Fork Quotient | Certified permutations preserve the complete conditional problem | Labeled state and transition redundancy | Uses an order-complete grammar; roles and joint residency profiles remain distinct |
| Scalar/Streamed Bridge and free retention | An executable plan attains simultaneous global lower bounds | Search inside a certified conditional state | Coverage can be small; a larger scalar leaf can block attainment |
| Two-live normal form | Every plan in a restricted core is dominated by one of three constructive families | Search for a complete, potentially nonzero-traffic response | Requires vector X and exactly one other locally live private tensor |

These mechanisms can support one solver architecture, but they cannot be mixed
without aligning order domains, solve/group entry, tile domains and caller-paid
costs. In particular, count merging proved in the all-order solver is not a
valid cache-key change in the old fixed-order solver. The new certificates
preserve the fixed order and do not rely on consumer permutation.

The composition contract still has to include reservations **before** taking
the maximum across serial children:

    P = max_g (A_g + P_g),
    Q_extra = Q_boundary + sum_g Q_g.

For a loop, the corresponding child traffic is multiplied by its trip count.
Dropping A_g, ownership, or entry semantics can invalidate a formula even when
the child response itself is exact. P21f's one-byte plateau counterexample is
an experimental illustration of this requirement, not a replacement threshold.

## 2. Search redundancy and physical conflict are now separately visible

[Fork Quotient](FORK_QUOTIENT_RESULTS.md) has five complete root references,
128 complete conditional references and 685 exact saved executions across its
first study and ablation. The all-k six-consumer timing control has a 9.80x
ratio of medians. The 106,604-to-6,092 response-entry reduction measures the
implemented searches, not a minimum number of physical states.

Its joint-context bound

    96 D binomial(a+4,4) binomial(b+4,4)

includes ancestor residency and operator membership for this fixed-rank,
two-role family. It is a stronger statement than counting one mask layer,
but not a runtime bound: transitions, frontiers, extent domains and witness
construction also cost work. The mixed-eight timeout remains unresolved.

At the same time, complete order optimization leaves a physical difference in
the tested tiny six-consumer family. The saved complete internal solver outputs,
with whole-graph compulsory traffic restored, are:

    all k:       ((3,136), (4,84), (7,56))
    three k/i:   ((3,136), (4,92), (6,84), (7,56)).

Thus the mixed graph costs eight more transfers at capacity four despite the
complete order optimization. It ties at capacities three, six and seven. This
is a demonstrated capacity-dependent conflict in this grammar, not a claim
that mixed roles are always worse or that order never matters elsewhere.
Sources: [same6](results/fork_quotient/quotient_same6.json) and
[mixed6](results/fork_quotient/quotient_mixed6.json).

The useful division is therefore between eliminating equivalent plans and
explaining why inequivalent plans have different resource responses. Faster
search enables the latter measurement; it is not itself an explanation of
the traffic penalty.

## 3. What the new scalar-retention result does and does not add

The user's condition is best viewed as a lower-bound certificate. Moving one
scalar from the inner operation into an outer reservation can leave total peak
capacity unchanged. If the child attains its reduced bound at zero extra
traffic, global optimality follows immediately.

This is an exact proof, but the census advises against making it the next
performance headline. Its 150 matches per old six-consumer case are all covered
already. Across ten small root cases it adds 276 matches; incremental
cache savings are at most 0.40%. Only 20 of those new matches occupy an entire
producer span. The observer counts do not establish cost-weighted coverage of
the slow mixed-role quotient search, which is a different recurrence.

The right implementation decision is to keep this optional certificate and its
tests, and to retain the original leaf semantics. Changing the scalar leaf to
increase the hit rate would change the grammar and would require a separate
comparison. A rejected certificate does not mean a state lacks another cheap
optimal construction; the old overlapping cases demonstrate exactly that.

## 4. The substantive new physical boundary is about alternative axes

The two-live normal form progresses beyond zero-extra-traffic attainment. It
computes all breakpoints of a restricted positive-traffic curve and includes
the costs of both moving t and materializing/revisiting X. At small capacity,
the latter can win even though it introduces a producer/consumer cut.

This explains why two local Keep/Spill endpoints do not generally describe the
whole conditional problem. Intermediate X tiles create additional breakpoints;
another loop orientation can introduce a different lower-cost family.

The three-live counterexample is especially informative. In the same graph,
the states {X,V0,A} and {X,V0,D1} have one I-axis obligation, equal sizes, equal
revisit coefficient, equal operand-count lower bound and equal external
footprint. Yet at capacity two their extra traffic is 20 versus 24. A and D1
are both inputs varying along I, but A uses J whereas D1 uses L. They therefore
interact differently with the alternative L loop and the producer cut.

Consequently, a count for one selected axis is not a property of the entire
optimization space. A tensor that is streaming along one axis can become a
retention obligation along another. The missing information is the **joint
incidence and lifetime of locally live tensors across the competing axes**,
including where production must complete. This example is not attributed to
non-power-of-two tiling: all its nonunit extents are four.

## 5. What should be pursued next

The current priority is one conditional-resource method, rather than parallel
special-case optimizations. The first joint test has aligned decomposition,
symmetry and optimality certificates on the same six-op grammar. Next prove
closure of a dynamic remaining-state quotient: preserve all legal continuations,
boundary effects and a consistent global order. Use the complete unified census
to compare internal responses and count states, transitions and frontier work
separately. The current global order quotient alone does not provide that result.

The three-live core {X,t,z} remains a useful negative control and a future
certificate target within this contract. It must retain joint axis incidence,
position relative to the producer cut, read/reduction role and write ownership.
A positive-traffic response would require a matching lower bound and proof that
other partitions and loop orders are dominated; a feasible schedule is only an
upper bound. This is not a separate optimization branch in the current plan.

Broader validation can later reuse the completed mixed-six quotient. Do not
transfer coverage fractions between grammars or extrapolate from the partial
mixed-eight timeout. First complete the unified-state argument on the small
partially symmetric graph where all reference responses are available.

The [completed branch-symmetry study](BRANCH_SYMMETRY_RESULTS.md) is a
generalization of the equivalence contract that preceded the joint test.
All 221 completed literal-reference queries agree and its
852 saved executions are exact, while the three-branch join search remains
incomplete. Whole dependent branches, rather than their first consumers, are
the symmetry units. A separate continuation control recovers symmetry after
unequal prefixes: two response misses become one, with all six restored
witnesses exact. Paid prefix costs and surviving boundary constraints remain
in the caller. This supports defining equivalence on the remaining typed
problem, rather than demanding an automorphism of the entire original graph.

The new [numerical-redundancy census](REDUNDANCY_RESULTS.md) addresses another
useful question: how many completed keys happen to return the same curve?
Such numerical classes can identify promising targets for structural proofs.
They are not, by themselves, a computable pre-search key, a lower bound on the
number of recursive solves any algorithm must perform, or evidence of equal
physical histories. A formula can generate many different curves without
solving each recursively; equal curves still require a valid witness for each
original interface. Treat this census as diagnostic evidence for a future
sufficient statistic, rather than a ready-made compression theorem.

## 6. What a defensible contribution would look like

The present results support a scoped claim: exact search can exploit boundary
decomposition, conditional symmetries and constructive optimality certificates,
and each transformation has an explicit execution/interface contract. The
failures identify information that simpler summaries cannot discard.

A stronger next result should characterize a class of conditional states whose
redundancy can be recognized before search, with a bound that includes ancestor
residency and extent contexts. An attaining positive-traffic response is another
possible certificate inside that method. The new joint test already connects
one local structural condition to eliminated search and executable witnesses;
its finite coverage does not establish either broader result.

There is still no general graph optimizer, universal width/runtime law,
minimal-state theorem, unrestricted physical optimum, or completed novelty
comparison with the broader I/O-complexity literature. These are separate
questions; the existing exact results remain useful without claiming them.
