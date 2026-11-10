# Unified serial search: contract, replacement rules and bounded factorial study

Fixed before the remote measurements. This is an implementation/correctness
study, not a new frozen P prediction or an assertion of algorithmic novelty.
Keep every attempt, including timeouts, mismatches and rules with zero hits.

## 1. One grammar and one conditional response

The six-op family is X(I,K)=A(I,J) B(J,K); U_i(I,L)=X C_i(K,L), i=0,1,2;
V0(I,L)=U0 D0(L); Y(I,L)=V0 U1 U2. The last two ops are elementwise products,
not addition, softmax or a multi-writer accumulator. Operands are distinct,
one-byte cells, and every tensor has one rank projection and at most one writer.

Gamma* is the union of the current exact `curve.py` grammar over ALL global
topological orders. A plan has one consistent order, reused by loop iterations.
No recomputation, overlap, approximate grid or order changes between iterations.
Use historical halving tiles, write-through/sharing allowed, spill cost two,
and repaired final-write ownership. Preserve the original scalar leaf literally:
when all nonexternal tensors are scalar, solve returns their total cell count
before considering partitions. All arms use this same rule.

A response key includes the ordered remaining ops, projected extents, resident
tensors R, already caller-owned final writes W, solve/group entry and any root
constraint. R is pinned for the query; its allocation belongs to the caller.
The internal response is free capacity and EXTRA traffic. Full root curves add
compulsory input reads/output writes exactly once. Each partition charges the
retained tensors over their first-to-last singleton/group-use intervals BEFORE
taking max across child peaks. Loops add retention and revisit charges, and
multiply child extra traffic by the trip count. These are fixed contracts,
not an arbitrary last-use-release or multi-writer model.

## 2. Common replacement theorem

In this finite, well-founded recursion, a state replacement is exact if it
preserves its complete conditional Pareto response and can reconstruct legal
witnesses with the same boundary effects. Resource transforms are coordinatewise
monotone: sums of traffic, positive trip multiplication and maxima of adjusted
peaks preserve dominance. Therefore replacing children by their exact frontiers
and composing any finite sequence of exact rules preserves the parent frontier.
Rules need not commute as implementations; they must retain/recheck their
preconditions and the common interface.

For equivalence, equal leaf responses plus a bidirectional matching of legal
decisions, their full resource transforms and equivalent child states gives
response equality by induction. A bijection of decision labels is sufficient
but unnecessary. A single same-cost action is not enough. Cut DP stores a Pareto
set of accumulated PREFIX costs at each boundary; equal continuation keys do
not identify unequal prefix costs.

Three switches use exactly this response:

- D: existing cut DP, or unchanged full partition enumeration.
- Q: discover literal-rank typed graph automorphisms, canonicalize the full
  query decoration, and enumerate global orders modulo its stabilizer. Restore
  tensor names and the order in witnesses. With Q off, enumerate all orders.
- C: the local scalar-separator certificate below, or ordinary recursive search.

Q is currently at the query/order boundary, not a dynamic quotient of every
recursive internal state. D and C interact inside each representative order.
This first composition test does not claim to have removed order enumeration.

## 3. A local certificate replacing the whole-graph Fork guard

Consider an unconstrained ordered solve S with at least two ops, not already
handled by the mandatory scalar leaf. Let H be the nonexternal tensors accessed
by at least two ops of S. Let P_i=access(i) minus (R union H). Require:

1. H is nonempty and every t in H is one scalar at the current extents.
2. Every active rank appearing in any tensor of P_i appears in EVERY tensor of
   P_i. Unit streaming of these ranks therefore creates no missing-axis private
   obligation; tensors in R union H stay reserved outside the singleton group.
3. Let a_i count the H tensors whose first-to-last use interval covers op i.
   Let d=max_i |access(i) minus R|. Require max_i(a_i+|P_i|)=d.

The grammar's operand-slot lower bound is C>=d and extra Q>=0. A singleton
partition retaining H, followed by the private unit streams, has zero partition
traffic, zero loop revisit traffic and peak max_i(a_i+|P_i|)=d. Hence its WHOLE
internal frontier is {(d,0)}. A larger peak is only an upper-bound construction
and must be rejected. Shared tensors that span unrelated ops are charged at
those ops too; retaining scalars is not automatically free.

The proof uses the local incidence, projections and lifetimes, not names X/C/U
or terminal-output status in the original graph. A produced tensor used outside
S is either a caller-resident output, or a nonexternal private/local shared
output whose final boundary write is still charged outside this response.
Keeping local shared tensors adds no write, so W is preserved without inventing
or cancelling any caller charge. No comparison across different caller costs
is made. Single writers and topological legality are checked at the outer API.

This generalizes the old scalar-X construction as a sufficient certificate,
not a complete recognizer of all zero-extra-traffic states. All-scalar leaves,
group entries and constrained root solves retain their original semantics.

## 4. Fixed measurements

The graph has 12 topological orders and a certified two-element group exchanging
E1/E2 and C1/U1 with C2/U2. E0 remains fixed because of F. The undecorated root
has six order orbits. These structural counts were checked before measurement.

All eight D/Q/C settings on each of these cases, each in a fresh Linux process:

| Name | I,J,K,L | Purpose |
| --- | --- | --- |
| skinny | 1,2,1,2 | Negative reachability control: local Fork-shaped solve exists syntactically but need not occur under group entry |
| core | 2,2,2,2 | Full small graph, loop-induced conditional states |
| rectangle | 2,3,2,4 | Additional extents and an additional L tile level |

Bound each arm to 180 seconds including search, census and final replay; 6 GiB
address space; seed zero; at most four concurrent workers. No memory/capacity
approximation is allowed. Every root frontier point is replayed by the existing
element-level executor. Every completed internal solve/group cache miss is
saved with full order, state and numerical response in compressed JSONL.

The independent reduction-free reference is D=Q=C=0: all literal orders and all
partition masks, with no certificate or quotient. It shares the cost recurrence
with the optimized arms, so equality does not independently establish physical
accounting. Executor replay is the separate physical check. Compare every saved
optimized state to the corresponding baseline state; report missing contexts
separately, never as matches. The checksumed source and counters make this a
complete comparison within each finished census, not a sample of roots only.

Measure solve/group response entries, partition choices or DP transitions,
loop choices, Pareto candidates, certificate checks/hits, symmetry overhead,
search time, process CPU and peak memory. Different counters are not numbers of
unique physical schedules. Attribute reductions by all eight settings rather
than adding three separately measured speedups.

Store certificate provenance on returned plans and strip annotations before
replay. In an all-on arm, seek a returned point with an actual certificate and
a recorded cut-DP ancestor, under a canonical order representative. Record
whether that chain exists; do not treat hits in disjoint controls as its proof.
An internal zero-hit case is a legitimate negative result.

After the census jobs finish, run sequential fresh-process, no-census/no-profile
timing controls for 000 and 111 on core and rectangle: three repetitions each,
alternating order between repetitions. Same witnesses and costs; same 180-second
and 6-GiB caps. Report ratio of medians only for complete equal-curve controls.
Python imports/process startup are outside the measured search interval; graph
validation, symmetry detection, kernel construction and search are inside it.

## 5. Prior diagnostics and exclusions

Local small tests cover the original leaf, group entry, root constraints,
nonterminal local outputs, interval-gap rejection, failed private streaming,
broken boundary stabilizers and name-restored witnesses. The skinny local
eight-arm check is an implementation test, not held-out data. A preliminary
25-second combined smoke test completed core 000 (seven exact root replays)
then hit its shared alarm during core 111; it is not a per-arm timing result.
No rectangle search preceded this protocol.

Unchanged production solver/executor and frozen P protocols. No speed threshold,
minimal-state claim, general-DAG complexity theorem, automatic separator theorem
or novelty claim. A successful experiment establishes composability of these
specific certified rules in this declared grammar. Dynamic state quotienting,
broader certificates and an execution-obligation representation remain future
proof obligations, not additional branches in this study.
