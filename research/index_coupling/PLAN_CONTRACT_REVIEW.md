# Plan review: what can already be proved, and what still needs a test

Review of RESEARCH_PLAN.md at `3e229762`, 2026-11-09. This note preserves the
research question and frozen protocols. It does not freeze P20 or introduce a
new search mechanism.

## An existing theorem already settles part of P20

The symmetry below is already stated in P18_STRUCTURAL_INTERPRETATION.md §3.
It is restated with P20's assumptions explicit, not counted as a new result.

Consider `graph/model.py::fork` with fixed I, J, K, L, consumer count m,
uniform element sizes and transfer coefficients. Each consumer has its own
private terminal operand and output; consumers are mutually independent.
Let Gamma-star be the union of the current exact recursive grammar over all
legal consumer orders, with tensor identities preserved within every execution.
Use `grid=None`; the claim concerns numerical frontiers, not witness identity.

**Proposition.** Two role strings with the same (#k, #i) have identical
capacity-traffic frontiers in Gamma-star.

**Proof.** Choose a bijection between their k consumers and another between
their i consumers. Rename each consumer together with its private operand and
output. Keep EX, A, B and X fixed. This preserves dimensions, tensor roles,
producer/consumer incidence, and the set of legal consumer orders. An ordered
execution in one graph maps to an ordered execution in the other. At each
recursive step, contiguous groups, loop choices, retention subsets and DRAM
transfers map bijectively. All block sizes, simultaneous allocations and traffic
coefficients are unchanged. Scalar leaves have the same live-object count.
Induction therefore preserves every achievable (capacity, traffic) pair. The
inverse renaming proves equality of the feasible sets and hence their Pareto
frontiers. The argument also respects the write-through and split-sharing
options when the same options are used on both sides.

At I=K, the established I/K exchange plus role complement additionally
identifies (#k, #i) with (#i, #k). Thus, **for fixed m and shape**, b=min(#k,#i)
indexes the role classes of this homogeneous, order-completed fork family.
For I!=K the exchange also changes the shape; b alone does not establish
equality at the original shape. Heterogeneous consumer shapes or downstream
uses can invalidate the renaming assumptions.

This is ordinary symmetry, not a new complexity or I/O-bound theorem. It does
not compute a curve, prove a maximum-gap formula, or imply that two different
role classes have different curves. The existing fixed-order kki/ikk mismatch
is consistent with it: Gamma-star is a larger grammar than one fixed order.

Consequently, P20's same-count/order test is primarily an implementation
regression, not an uncertain structural prediction requiring an expensive
scan. The substantive held-out question is what happens on **non-isomorphic**
graphs, especially when private terminal tensors become reconvergent inputs.
Role counts can be equal while these new dependency constraints differ.

## State the object and the evidence at the right level

Write the target as

    S_(G,Gamma)(q) = min { P(m) : m in Gamma(G), Q(m) <= q },

with infinity for an infeasible budget. Gamma specifies tile domains, allowed
orders, ownership, precision, recomputation and execution semantics. Existing
`capacity_for` uses traffic **above each curve's own plateau**. An architecture
example needs total traffic, so retain that plateau Q0 and use Q0+q. Different
plateaus cannot silently share the same physical traffic budget.

"Least information" needs a declared class of candidate representations and
contexts. A practical target is a cheaply computable sufficient invariant,
plus counterexamples establishing why particular distinctions are necessary.
Exact replay of a few final curves alone does not prove sufficiency for all
supported future contexts.

P17 proves a role-swap symmetry for the paired private terminal operands and
accumulated outputs. It does **not** erase producer/consumer roles, reduction
completion or materialization legality in an arbitrary graph at spill_cost=1.
Nor does it prove that an interface must literally carry a role flag: a cost
or effect field might encode the same distinction.

The P19 expression n*min(ceil(b/2)*L,n/2) predicts a **maximum vertical gap in
capacity**, not the traffic locations of breakpoints or the full S(q).
Even a successful P19 would not establish a complete curve predictor.

## The 37,710 entries are not a cut-width measurement

MEMORY_DIAGNOSIS.md counts both memo functions, all operator intervals, extents
and retained-tensor sets: 19,314 solve entries plus 18,396 group-curve entries.
They are 37,710 distinct recursive subproblems in one four-consumer run. They
are not 37,710 boundary states at one fixed cut, and not a minimal quotient.
The exact projection is useful, but its proof fixes the graph, grammar and
options and relies on callers charging ancestor allocations.

For step 3, separately count, at a declared cut and context domain:

- distinct boundary signatures;
- numerical frontier size per signature;
- total recursive memo entries and the work to construct them.

Do not aggregate these into a single "interface state count". Passing a
coarser-interface replay is evidence; safe replacement still requires a
composition argument or an explicit finite exhaustive context contract.

## Composition includes boundary charges

For fixed boundary choices I and serial sibling groups g, the recurrence uses

    P = max_g (A_g(I) + p_g),
    Q_extra = Q_boundary(I) + sum_g q_g.

A_g is the capacity of across-group retained objects live during g. In
`graph/curve.py`, `across + c` is charged **before** `combine_max_sum`.
The function combines these adjusted peaks. Fixed interfaces alone do not
justify taking the maximum of unadjusted local peaks; open scopes or different
caller reservations require their own contract. The complete graph adds its
compulsory traffic separately.

Current FFN cuts use the documented copy-alias/lifetime simplifications;
attention uses an elementwise softmax proxy. Results describe those models
until the missing physical semantics have been covered independently.

## Architecture and literature boundaries

A memory-capacity x bandwidth example is a useful systems result. Bandwidth
alone does not determine a traffic budget: one also needs a latency objective
or deadline, compute demand and an overlap model. Under a memory-bound deadline
approximation, Q <= B*T_target is one explicit contract. PE shape, banking,
precision or other hardware changes may alter Gamma and costs, requiring more
than a single capacity-traffic curve.

The plan's blanket statement that prior I/O analyses treat one memory size and
do not separate accumulation reads/writes is not established. The official
[IOOpt description](https://iocomplexity.corse.inria.fr/ioub) explicitly accepts
array access occurrences including reads and writes. The authors' [SOAP
description](https://htor.spcl.ethz.ch/publications/index.php?pub=418) explicitly
covers multiple statements, input/output reuse and tiling. These facts do not
settle whether they already derive the present role-comparison result, but
they prevent treating "whole curves" or "read/write accounting" alone as the
novelty distinction. The IOOpt page was available as indexed primary-source
text; direct retrieval timed out during this review. No claim of a completed
full-paper novelty audit is made here.

## Immediate decision

Keep the research question and step order. Finish P19 without changing its
criteria. P14-FFN' is now scored in FFN_SHARED_INPUT_RESULTS.md: its equality
prediction fails. Use the fork renaming proposition as a regression property;
reserve the next frozen empirical claim for a non-isomorphic graph comparison
or a quantitative threshold prediction. Do not infer a new mechanism merely
from another successful symmetry check.
