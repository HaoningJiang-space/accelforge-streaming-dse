# After D1: conditional separators with explicit loop scopes

This is a design/proof note, not an implementation or a new benchmark result.
D1's frozen six-case experiment remains unchanged. The proposed next experiment
is dynamic conditional region selection, contingent on the contract below.
M8 optimization is not the primary objective.

## 1. Partition search work without forcing an execution barrier

A region is queried **at a particular loop scope and execution phase**. It is
not permanently assigned to Producer, Branch or Join. D1's executed `(5,32)`
Fork–Join witness has these nested scopes:

    I: {EX,E0,E1,Join}
      L: {E0,E1,Join}, with X supplied by the parent
        K: {E0,E1}, with U0/U1 accumulators supplied by the parent

The downstream L scope is essential to this witness but is not a valid whole-DAG
loop because EX does not iterate L. More generally, a proposed common loop must
pass the full iteration-domain and unfinished-intermediate guards under the
current residency. A Tensor being external can change the guard. There is no
permanent, topology-only label saying that two operators must always fuse.

For whole-operator execution, a completed ideal I determines remaining consumers
from the DAG. During streaming, an operator can be partly executed while I has
not changed. An exact state must additionally identify which tile instances and
reduction contributions have completed. A total SRAM byte count cannot replace
their identities.

## 2. A conservative observable contract

Keep two cases distinct:

**Closed invocation within a fixed parent scope.** Existing native v2 subtrees
already have a usable conditional interface: ordered operators with their full
domains, extents, external residency, paid final writes, and solve/group entry.
The parent controls loop iteration, cross-child lifetimes and cost scaling.
Reusing such a subtree does not require its graph-global operators to have
finished every iteration. The existing remainder and conditional-response
proofs are useful here; no new theorem is claimed merely by renaming this a
region. Unsupported constraints or context changes require native fallback.

**Invocation that yields to another region before returning.** Endpoint tensor
states and a single `(P,Q)` need not describe all intermediate interactions.
Expose a protocol of boundary events, not just entry and exit sets:

    contract = (eta_0, event_1, eta_1, ..., event_h, eta_h; lambda)

Each eta identifies live boundary tensor versions and tile coordinates,
projection/layout, storage and owner, produced/consumed tile progress, partial
sum completion, and outstanding readers. Lambda identifies active loop scopes,
their operator sets, extents/cursors, reset/reduction obligations and legal
continuations. Event ports include acquire, produce-ready, consume, final-write
and release. Values must represent the same deterministic computation, not just
coincidentally equal byte counts. Aliases, recomputation and asynchronous DMA are
outside this first contract.

This is deliberately conservative. It might be as large as an execution trace;
its existence is not the sought compactness result. Future compression must
prove that forgotten information cannot change enabled actions or costs.

## 3. A sufficient substitution lemma for synchronous phases

Restrict execution to serial, data-independent plans with single writers and
no aliases/recomputation. Contexts may interleave only at the declared event
ports. Between two ports, the incoming boundary allocations are borrowed and
cannot be freed or resized. All persistent allocations and produced versions
are exposed at the next port; there is no hidden live state.

For phase j, summarize a region plan by its additional peak p_j and traffic q_j,
excluding the incoming borrowed allocation. Newly allocated buffers count in
p_j, and any surviving buffers appear in the next eta. Let L_j be the incoming
boundary allocation plus the context's other constant live allocation during
that phase. Then its peak contribution is L_j + p_j. Context-only phases are
accounted separately. No real timing or energy conclusion follows from this law.

Suppose plans A and B implement the same protocol, including data meaning,
progress and enabled continuations, and for every admitted concrete boundary
instantiation and every phase:

    p_j(A) <= p_j(B),  q_j(A) <= q_j(B).

Then A can replace B in every supported context without increasing total peak
or traffic. Proof: at each event the visible state is identical, so the same
context action remains legal. Between events, identical borrowed allocations
give identical L_j; monotonicity of addition preserves each peak inequality.
Induct across events and take the maximum over phase/context peaks and the sum
of traffic. Exit progress, ownership and final-write obligations are unchanged.

This is a sufficient simulation-style rule, not a minimal interface or a novel
general composition theorem. It does not justify scalar Pareto pruning across
different protocols. If a context may free a borrowed input mid-phase, that
release must become an event port or the lemma does not apply. Checking finitely
many parents does not prove the universal premise about all admitted contexts.

## 4. Concrete partition procedure to investigate

1. At a reached native conditional state, retain every legal loop rank/tile and
   retention action. Select loop scopes before closing regional interfaces.
   Candidate regions can cross the old producer/body/join labels. Do not limit
   region size merely to manufacture Unit-M oracle hits.
2. Select a region only when its boundary protocol is declared and verified.
   For a closed subtree, use the existing conditional contract. For interleaved
   regions, require the event protocol above or leave the original native
   action intact. Failure to recognize a separator is not infeasibility.
3. Reuse an exact response under the same contract. Use symmetry only under
   a proved automorphism preserving tensor/version, reduction role and boundary
   decoration. Use Unit-M/Scalar oracles only inside their proved guards.
4. Compose capacity with caller reservations and traffic with single ownership.
   Preserve native witness provenance and one globally consistent operator
   order. Independently choosing local orders at different loop scopes can
   enlarge the grammar; it is not automatically equivalent to the current
   union of fixed-global-order solvers.

Calling this procedure "dynamic partitioning" does not establish novelty:
native Cut DP already chooses different partitions at different loop states.
The new quantity to establish is **reusable work across compatible DAG-region
contexts**, together with its total construction and management cost.

## 5. One next experiment, three gates

Gate 1 — Representation: express both D1's closed/materialized plans and its
nested-loop witnesses without changing their resource counts. Check versions,
per-tile readers, partial sums and lifetimes with independent execution. Include
mutations that omit the L scope, omit a remaining consumer, or treat a partial
sum as complete; each must be rejected or distinguished.

Gate 2 — Substitution: state the exact set of permitted parent contexts and
prove the interface's sufficiency there. Exhaustive small-context checks and
native witness replay test the implementation. Only then substitute responses
inside complete search. If no compact contract is found, report the state/trace
growth and stop; do not disguise the full execution trace as compression.

Gate 3 — Work: compare identical complete v2 frontiers and complete native
witness generation against **Cut DP plus Conditional Prefix Sharing**, with
existing analytic replacements matched across arms. Separately ablate region
reuse, symmetry and analytic certificates. Count construction, cache payload,
Pareto joins, fallback work, setup, recovery and peak memory. Baseline Prefix
Sharing gains cannot be counted again as a new partition gain.

The new adapter must preserve all native actions or use a proved replacement;
otherwise it is a restricted search-space experiment like D1. Initially retain
the same explicit global-order family in both arms. Eliminating that family is
a separate correctness obligation, not an implicit consequence of DAG syntax.
Do not increase graph size to mask a failed correctness or overhead gate.

Actual ResNet/GLU extraction, FFM Event/cache candidate coverage, and hardware
timing follow only after these gates. No choice of ordinary graph partitioner
by itself resolves the boundary or nested-loop proof obligations.
