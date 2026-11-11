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

## 6. Derivation review: the precise statements to prove

Checked against `curve.py`, `response/prefix.py`, and the archived D1 witness
at `e7b9cd39`. These are proof annotations and bounded semantic probes, not a
new partition algorithm or performance experiment.

### Exactness needs two inequalities, not every original plan

Fix a global order pi, tile domain, entry, v2 and all option flags. Define the
value of an infeasible capacity query as infinity. A new search is exact if:

1. Every returned witness is native-legal with its claimed costs (soundness).
2. For every native plan there is a returned or representable plan with no
   larger peak or traffic (coverage up to dominance).

The first gives F_native <= F_new; the second gives the reverse inequality.
Preserving every native syntax tree is sufficient but stronger than necessary.
A certified analytic replacement can satisfy the second condition without
enumerating every tree. If the reference unions several orders, both statements
must use that same order family. Independently reordering each nested scope
does not automatically belong to that family.

### D1 identifies an omitted construct, not a universal necessary schedule

The saved `(5,32)` witness has X row reservation 2, two scalar accumulators
U0/U1, and one local C operand, giving peak 2+1+1+1=5. Join substitutes Y
for that local operand; EX's own phase fits within 4. The outer I loop refetches
B, C0 and C1, each of size 4, once: Q=20+3*4=32. No intermediate or partial
sum reaches DRAM. Replaying the archived witness on the execution server
reproduced these numbers, including the per-tensor counts in RESULTS.md.

This proves the particular restricted grammar misses an optimum. It does not
prove every native optimal witness must use this exact I/L/K tree. Restoring
one witness proves representation of that point, not full-frontier coverage.

### Fixed partitions: separability after the interface is fixed

Let f_i(c) be the minimum *extra* traffic of the correct native child entry at
capacity c, with infinity for infeasibility. For a fixed boundary policy K:

    f_(regions,K)(C) = Q_boundary(K) + sum_i f_i(C - rho_i(K)).

This is equivalent to the max/sum Pareto formula: max_i(rho_i+p_i)<=C iff
every p_i<=C-rho_i. Independent minimization of the sum is then valid. The
independence premise is substantive: child alternatives must have the same
external data semantics, reservation lifetimes, ownership and exit guarantees.
Otherwise a cheaper child may change another child's feasible set.

Rho includes kept tensors even in an intervening region that does not access
them. Ancestor-external reservations are excluded from the returned response
and charged by the caller. Child compulsory terms must not be summed; the
enclosing invocation's compulsory term is added once. Concatenation proves
soundness, decomposition of any plan respecting these exact sibling boundaries
proves coverage. It does not cover a loop crossing the sibling boundaries.

There is an important **one-region scalar corner** in the diagnostic adapter.
For the all-one Fork–Join, direct group entry can repartition and returns
`{(3,2),(4,0)}` in extra-traffic units. A fixed single whole-parent group must
instead use native `part_curve`'s v2 hold case, returning `{(8,0)}`. At the
reviewed revision, `RegionComposer.compose((graph.ops,))` calls group entry
directly and returns the former. Thus its general single-region extension is
not an exact implementation of native fixed-root semantics. D1 always uses
three regions, so this does not invalidate its archived comparisons. The
frozen code/results are left unchanged; any generalized adapter must handle
this hold case explicitly. A reproducer, also checked on the execution server:

```python
from research.dag_mapping.boundary import workload, RegionComposer, compulsory
from research.index_coupling.graph.curve import curve
g, _ = workload('fork_join', (1, 1, 1, 1))
print([(p, q) for p, q, _ in RegionComposer(g).compose((g.ops,))])
print([(p, q-compulsory(g, g.sizes)) for p, q in curve(
    g, scalar_leaf='v2', partitions='dp', root_groups=(g.ops,), root_kept=())])
```

### Parent-frame equivalence is an equivalence of prefix computations

Put A=T(P[:j]), B=T(P[j:]), H=T(S[p:]) and T(P)=A union B. Then

    B_S(j) = A intersect (B union H)
           = A intersect (B union (T(P) intersect H))
           = A intersect (B union B_S(p)).

This is a set identity, including shared graph inputs, not only DAG edges.
To infer equal prefix recurrences, additionally preserve projected extents,
resident/owned sets, exit decisions, writer classification and entry context.
First uses and writers inside P come from P itself. A writer in the suffix
needs a separate flag for the non-topological inputs accepted by the numeric
core; that flag is empty for a valid topological single-writer order.
Whole-parent versus proper-prefix status matters through the scalar hold rule.
The implementation only interns proper prefixes, keeping full parents separate.

Current caches live inside one graph/solver invocation: global tensor roles
and option flags are shared closure data. Cross-graph reuse would need to carry
or prove equality of those labels too. Inside one fixed order, actual parents
are contiguous spans, not arbitrary subsequences.

Equal frames imply equal *prefix construction responses*. Their suffixes can
remain different and have different costs. This is not a theorem saying the
two complete execution states have identical continuations. The latter is a
separate requirement for merging execution histories.

The premise that frame performance results are still pending is now outdated:
WORK_ATTRIBUTION.md section 6 was archived at `e7b9cd39` (2,190 exact replays).
Its incremental gains remain distinct from the older prefix-sharing results;
one-layer M8 is within timing variation and mixed Fork slightly regresses.

### Loop legality is hereditary; loop cost and optimality are not

For a span S define M(S)=made(S) intersect read(S) and

    Req_v(S) = {t in M(S): v not in dims(t)}.

At fixed extents and R, the nonscalar group loop guard is exactly:

    v in intersection_o D(o), extent_v > 1, Req_v(S) subseteq R.

For S' contained in S, its common-domain intersection is a superset and
M(S') is a subset of M(S). Therefore the guard remains true for S' with R
projected to its tensors. The result applies to contiguous S' in the native
grammar. It also shows increasing R can only enlarge this structural legal
rank set. Neither conclusion compares resource costs: the lacking tensors,
retention charges, parent reservations and children can change.

All-scalar v2 states terminate/repartition instead of enumerating these loops;
so downward closure of the structural guard is not the assertion that every
child solver will actually enumerate the same loop. Precomputing common ranks
and Req sets is safe; discarding non-maximal scopes is not justified. Native
`loop_metadata` already caches common ranks and internal incidences, so the
heredity proof alone is not a new search-work reduction.

### An exact hierarchical representation needs a typed grammar

Use solve S and group G entries, not an untyped arbitrary Plan tree:

- A single-operator all-scalar entry is a leaf.
- Solve chooses contiguous sibling partitions and their boundary decisions.
  Children normally enter group. A single whole-parent, multi-operator,
  all-scalar part instead becomes Hold(all live cells).
- A nonscalar group must choose a guarded loop, a proper divisible tile and
  its keep/spill mask; the body enters solve at the smaller extent.
- An all-scalar multi-operator group has the scalar solve response: proper
  partitions or the explicit whole-span Hold case.

Each loop uses the native uniform child template across its trips. Its costs
are `held + child_peak` and `refetch_or_spill + trips*child_extra_traffic`.
The remaining global options and guards are inherited unchanged. Normalize
scalar group-to-solve delegation and the trivial Hold case before induction;
then proper partitions decrease span length, loops decrease the extent
product, and a nonscalar whole-group entry decreases the entry phase.
Constructor-by-constructor translation proves the two representations equal.
It proves no search acceleration by itself.

Within any one tree, scopes are nested, equal or disjoint (laminar); equal
scopes occur for successive loops. The collection of candidate scopes across
different trees need not be laminar. Preselecting one hierarchy can again
exclude native mappings.

### What sufficiency of a boundary key would actually mean

For closed native subtree calls, the existing `(entry, ordered span, extents,
R, W)` query plus fixed graph semantics already projects the ancestor context.
Different ancestor stacks can share it: the caller owns repetition, reserved
storage and boundary transfers. Retaining every ancestor frame in every cache
key may destroy safe sharing without adding information needed by that query.

For a yielded execution prefix, define concrete states and a projection
alpha(x)=Theta before proposing equality. Loop frames must specify relevant
cursors/control position, not just ranks and tile sizes. Boundary status must
distinguish ready data from reserved/uninitialized cells and incomplete sums;
remaining readers must be per tile when appropriate. Paid-write ownership is
not the same as a valid DRAM copy or a dirty bit. Some fields can be derived
from others, but that derivation must be stated rather than assumed.

A sufficient proof obligation is a cost-preserving transition equivalence:
equal projected states have equal termination/data guarantees; every enabled
action in either state has a matching action in the other with the same
observable effect, resource cost and projected successor. Induction over the
finite remaining computation gives equal continuation responses. This is
stronger than numerical agreement of standalone frontiers on sampled parents.

With the same continuation contract and live-state costs, two histories
`(p1,q1) <= (p2,q2)` can be pruned because, for every matching continuation
`(p,q)`, `max(p1,p)<=max(p2,p)` and `q1+q<=q2+q`. Here continuation peaks
include the retained footprint; an extra-scratch peak must first be shifted
by that footprint. If regions interleave, use section 3's phase contract
instead of collapsing their entire behavior into one pair.

The verified building blocks are therefore a typed hierarchical recurrence,
an observable-context projection, and monotone resource composition. The open
algorithmic question is which projections share enough actual work to repay
their construction and storage costs. Small graph cuts or laminar syntax
alone provide no such bound.

Review checks: the existing 13 prefix/boundary tests passed with
`python3 -m unittest research.index_coupling.test_prefix_sharing research.dag_mapping.test_boundary`.
The additional one-region scalar probe exposes an unhandled API generalization,
not a passing new exactness test. No frozen D1 source or result was rewritten.

## 7. Gate 1 implementation and bounded validation protocol

This continuation adds `hierarchy.py`, a typed plan representation, flat-witness
decoder/encoder and resource certificate checker. It does **not** select regions,
search for plans, merge response states or prune candidates. It imports no native
cost or search helpers. The independent cell executor remains the execution
oracle; agreement with a second recurrence alone would not establish correct
DRAM transactions or numerical outputs.

The supported grammar is exact v2, a fixed topological single-writer order,
halving or divisor tiles, `spill_cost=2`, `write_through=True`,
`split_shared=True`, and corrected final-write ownership. No capacity rounding,
layout conversion, alias, recomputation, arbitrary yield or asynchronous events
are introduced. Closed queries can declare external tensors and owned writes;
their reservations/paid transfers are excluded from the local response.

**Representation theorem for this scope.** Let T_sigma be trees accepted by
the checker at the given invocation, and N_sigma be the native generative v2
grammar before dominated plans are removed. Decoding any N_sigma plan gives a
T_sigma tree with the same resource pair; encoding any T_sigma tree gives an
N_sigma plan with that pair. This is equality of the declared generative
grammars, not physical optimality or a new compression theorem.

Proof by normalized structural induction:

1. A scalar singleton allocates its live operand cells; both entries give
   `(|live|,0)`. A whole-parent multi-operator scalar part allocates the same
   cells but has explicit Hold entry. The typed representation distinguishes
   these from a scalar group that can repartition.
2. At a solve Partition, contiguous child spans and the exact shared-tensor
   decision set are identical in both representations. They induce identical
   first/last reservation intervals and paid-write propagation. Apply induction
   to each correctly typed child, then the same max/sum composition. The inverse
   encoding uses those child spans and decisions as a native groups note.
3. At a nonscalar group Loop, the common-domain, unfinished-intermediate and
   declared-tile-domain guards are identical. The lacking-tensor keep/spill
   sets agree. The body has the same span, a smaller extent, and the same updated
   external/owned sets. Induction preserves its costs; adding held capacity,
   spill/refetch traffic and multiplying child extra traffic by trips preserves
   the enclosing costs. One uniform child repeats, just as in native grammar.
4. Scalar group-to-solve delegation is normalized, and the trivial scalar part
   ends in Hold. Proper scalar partitions reduce span length; nonscalar loops
   reduce extent product; a nonscalar solve-to-whole-group call changes entry
   phase. Thus the induction terminates and the two directions exhaust cases.

Operator domains and global consumed/produced labels stay fixed. Compulsory
input/output traffic is added once at the root. Equal canonical flat notes are
also checked on roundtrip, so cost agreement does not conceal changed schedules.
The proof assumes the implementation follows these rules; finite tests check
that implementation without substituting for the structural argument.

**The scalar one-region repair.** `RegionComposer.compose` now uses the Hold
case when its only region is a whole-parent multi-operator scalar part. It no
longer returns a repartitioned group response for that contract. A regression
test checks empty and nonempty caller-resident sets against the native fixed
root and executes the unconditional witness. D1's three-region arms are
unaffected. Its original records remain immutable; `score.py` now verifies their
source hashes against the recorded Git revision instead of the moving worktree.

**Validation frozen before the server run:**

- Reuse exactly D1's six cases, archived order families and four arms; no new
  shapes or heuristic restrictions. Convert, re-encode, resource-check and
  independently execute all 146 saved root witnesses.
- Regenerate native v2 Cut DP for each archived global order. Check every
  generated witness, then compare the all-order frontier with the complete
  archived frontier at all breakpoints (exact point-set equality).
- Preserve the `(5,32)` Fork–Join typed tree and per-tensor execution details.
- Run the existing/new prefix, boundary and hierarchy tests (currently 24).
  Six adversarial
  categories cover omitted L scope, missing retention decision, unfinished
  internal reduction, wrong tile domain, whole-scalar entry and changed order.
- Run sequentially with hash seed 0, a 120-second / 2-GiB limit. Record source
  hashes, input hashes, full generated witnesses and validation outcomes.
  Failures stay failures; do not silently relax the checker to force equality.

Commands (from a committed checkout):

```sh
python3 -m unittest research.index_coupling.test_prefix_sharing research.dag_mapping.test_boundary research.dag_mapping.test_hierarchy
PYTHONHASHSEED=0 python3 -m research.dag_mapping.check_hierarchy --out FRESH_RESULT.json
```

The run measures representation correctness, not independent optimizer quality
or search speed. A complete native frontier routed through this adapter remains
a native result. Gate 2 still requires a useful conditional-equivalence theorem;
arbitrary interleaving interfaces and state compression remain unimplemented.

## 8. Gate 2: closed responses shared across global-order parents

### What is already shared, and the remaining opportunity

Within one fixed-order invocation, native `projected` plus solve/group caches
already share identical `(entry, ordered span, extents, R, W)` queries. Adding
another identical key there cannot constitute a new reduction. The existing
Parent-Frame experiment instead shares intermediate prefix construction.

This continuation tests a different cache lifetime: separate legal global
orders of the same DAG can reach an identical **closed ordered subregion**.
Currently each root-order invocation rebuilds its response caches. A session
can reuse the entire response across those invocations without identifying
different local operator orders or changing the allowed loop scopes.

This is a specialization/application of existing conditional-response
sufficiency, not a new minimal-interface theorem. It does not eliminate the
global-order enumeration or prove polynomial DAG search.

### Sufficient cross-parent contract and proof

Fix one immutable single-writer DAG with rank projections, full sizes and tensor
roles, the default exact unlimited v2 policy, and a tile domain. Suppose a
contiguous ordered span S occurs in two legal global orders pi1 and pi2. At
the same entry, projected extents, external R and paid-write W:

    F_(pi1)(entry,S,e,R,W) = F_(pi2)(entry,S,e,R,W).

These are internal capacity/extra-traffic responses, excluding caller storage
and compulsory transfers. Neither parent's suffix is claimed equivalent.

Proof: the normalized typed recurrence from section 7 never inspects the
complement's order. Scalar tests use the same live tensors and extents.
Partition children are the same contiguous subspans of S; shared tensors,
first/last uses and boundary/write charges agree. Loop domains, unfinished
intermediates, lacking sets, tiles and retention charges also agree. The child
queries have equal projected contracts, so induction gives equal responses.
Fixed global produced/consumed labels and option flags are indispensable.
Whole-span restrictions would inspect the root parent and are excluded.

Witness substitution follows by the same induction. Native notes name the
same operators/tensors/ranks and use relative loop templates, not absolute
addresses. The caller supplies tile coordinates, repetitions, boundary values
and reservations; these remain its responsibility. There is no alias,
data-dependent control or layout conversion. Thus a stored closed witness is
valid in the destination parent, with its own reservation and transfer costs.
This does not authorize yielding halfway through a subtree.

### Implementation and baseline composition

`reuse.py` binds a session to a copied graph and fixed policy, keeping one
witness namespace and analytic registry alive. A shared pool sits beneath the
existing local solve/group caches. Keys retain the entire ordered span, entry,
projected extents, R and W. The native scalar whole-part Hold remains outside
this pool. No rank/tensor renaming, new dominance, prefix-key change, or local
order permutation is introduced. The production `curve.py` is unchanged.

The prefix baseline uses existing parent-frame sharing and numeric-first
composition. Existing whole-graph automorphisms remove redundant orders before
the new sharing is measured. The analytic pair additionally uses the existing
scalar-separator certificate and guarded Unit-M forms, in that order; both
arms have identical guards. Unit-form witness recovery is included in complete
generation and uses the session's existing recovery cache in both arms.

Audit mode recomputes each observed pool hit's **complete conditional frontier**
from its destination body's recurrence, with new pool lookups disabled during
that reference evaluation. Native local caches may supply responses previously
computed or verified in that invocation. Numeric equality includes empty
responses. Audit calls change execution work and are never timing samples.
Full root frontiers are separately checked against unshared native all-order
DP, per order as well as after union; independent cell execution checks the
reused witnesses in their actual destination parents.

### Frozen experiment before measurement

Correctness cases are D1's six unchanged graphs plus:

| Case | Graph and shape | Role |
| --- | --- | --- |
| two_stage_join | EX, two E→H branches, Join; I=J=K=L=N=2 | Primary symmetric multi-stage DAG |
| asymmetric_join | additional Prepare0 on one branch, Join; I=K=L=2,J=N=1 | Primary asymmetry control |
| mixed_join | three consumers, one extra elementwise branch op, Join; I=J=K=L=2 | Unequal branch structure |

Six arms, all with complete native-order grammar coverage:

1. Native Cut DP over every global order.
2. Prefix sharing over every order.
3. Certified order representatives + prefix sharing.
4. The same representatives + prefix sharing + shared closed responses.
5. Arm 3 plus existing analytic providers.
6. Arm 5 plus shared closed responses.

When there is only one representative and one root query, arms 4/6 disable
the extra pool: there is no cross-order reuse opportunity. This structural
guard is fixed before timing. Analytic providers are disabled in both arms
3/4 and enabled in both 5/6, so their old benefits are not new sharing gains.

First complete all nine correctness audits and tests. Any audit failure stops
the timing stage. Then time only residual_rectangle and fork_join_tiny controls
plus the three new DAGs: five fresh-process sequential rounds, cyclic arm
order, hash seed 0, 120 seconds / 3 GiB per worker. Run one separate work worker
per arm/case. Record order enumeration/symmetry/installation setup, complete
generation including recovery and final union, independent execution, peak RSS
before replay, conditional cache hits/entries and native work counters.

Primary success criterion: arm 4 must reduce median complete generation by at
least 10% on **both** primary DAGs against the faster unshared arm 3 or 5 on
each case, win at least four of five paired rounds against that baseline,
also improve setup-inclusive median time, and use at most twice that baseline's
median peak RSS. This is a predeclared practical gate, not a significance test.
Arm 6 is an ablation and cannot rescue a failed arm-4 primary criterion.
Retain all timeouts, regressions and failed conditions. Stop this bounded
continuation without tuning keys, changing cases or adding another cache after
seeing timing results.

The implementation is experimental and opt-in. A successful run would establish
reuse across a bounded family of global-order contexts, not arbitrary-region
replacement, general-DNN scalability or hardware speedup.
