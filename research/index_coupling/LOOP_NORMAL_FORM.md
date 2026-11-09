# A bounded loop skeleton inside the recursive grammar

This derivation is restricted to the exact `curve_model` grammar: serial
execution, projective accesses, divisible rectangular tiles, no recomputation,
contiguous operation-group partitions, and monotonically inherited reservations
on a root-to-leaf path. It is not a normal-form theorem for arbitrary hardware
schedules. The transformation does not change a fusion partition or move a
loop across a nonempty reservation scope.

## Empty-retention blocks

Fix an operation group O and an inherited external reservation set E. Consider
a path segment of loop nodes whose `kept` sets are all empty, with only trivial
single-group, empty-retention wrappers between them. There is no change of O
or E in this segment. Let the entry extents be n_v, the exit extents b_v, and
r_v=n_v/b_v, taking r_v=1 for unsplit ranks. Let N_t be the entry size of a local
tensor and c_t its fixed input/accumulator coefficient in O.

The segment's extra traffic and its continuation obey:

    extra = sum_t c_t*N_t*(product_{v not in dims(t)} r_v - 1)
    traffic = extra + product_v(r_v)*traffic_of_continuation
    peak = peak_of_continuation

Already inherited allocations are unchanged and contribute equally outside
this local recurrence. The identity applies to the recurrence's extra traffic;
compulsory and materialization terms retain their original boundary accounting.

To prove it, expand one loop at a time. A rank indexing t shrinks N_t by its
trip count while the outer repetition multiplies the continuation by the same
count. A rank not indexing t instead adds c_t*N_t*(r_v-1). Repeated additions
telescope into the product above. This is also a per-tensor identity.

Consequently:

1. Adjacent loops over different ranks in this segment commute in the resource
   recurrence, subject to preserving the grammar's implicit leaf boundary.
2. Repeated splits of the same rank coalesce into its final extent.
3. Each such segment needs at most d loops, where d is the number of ranks.

Legality is preserved: the group and external set determine the common ranks
and the forbidden unfinished-intermediate reductions, and neither changes.
For the implementation's halving/divisor domain, a chain of legal same-rank
splits remains a legal direct split. Integer floor-halving composes, and the
final extent divides the entry extent. This is not arbitrary rounding.

There is an important syntactic boundary: the model forces a leaf as soon as
all local tensors are scalar, even if some ranks of externally held tensors
still have extent greater than one. Arbitrarily sorting ranks could reach this
leaf too early. If a block ends at a leaf, keep one rank that indexes a local
tensor, shrinks from an extent greater than one to one, and therefore guards
that leaf, as the final rank of the block. Such a rank exists because the block
started at a non-leaf. Earlier intermediate states remain non-leaves. If the
exit is not a leaf, all earlier, larger extents are non-leaves as well.

Thus there is a canonical block with at most one loop per rank. This is an
existence result; the particular guard convention is not a performance choice.

## A graph-dependent bound on structural depth

Let n be the number of operations and t the number of tensors. On a static
root-to-leaf path:

- A loop with a nonempty `kept` set introduces at least one previously external-
  free tensor into E. There are at most t such loops.
- A nontrivial group partition strictly reduces the number of operations on
  the selected child path. There are at most n-1 such partition events.
- Group reservations can only increase E; they cannot reset this argument.

Between these events there are at most t+n empty-retention segments. Applying
the block transformation gives the loose bound

    loop_depth <= d*(t+n) + t.

Static group branching has at most n operator leaves, because groups partition
rather than duplicate operations. After trivial wrappers are identified, these
depth and branching bounds imply finitely many structural skeletons independent
of dimension magnitudes. Tile values and integer feasibility constraints are
still variables. The count can be enormous in n,t,d; this result establishes
finite representation, NOT a small search space or a speedup.

The theorem relies on this grammar's monotone reservation scopes. Selective
release/reacquire, overlapping execution, new physical copies, recomputation,
bank constraints and nonprojective accesses need separate analysis. It also
does not turn discrete tile optimization into a continuous geometric program.

## Frozen implementation checks

Before running, validate `loop_normal_form.py` using the existing independent
cell simulator. Do not alter the reference model or the simulator.

The normalizer reads a witness AST, uses only group/rank/reservation information,
and outputs a witness in the same flat syntax. It does not read cost vectors or
call `curve_model`. Reference generation is confined to the experiment driver.

Frozen cases:

- Both fork patterns at (2,2,2,2), (4,2,4,2), (4,4,4,4), (2,4,4,2),
  (3,2,3,2), and (6,2,4,2).
- A 4x4x4 MatMul and a two-stage chain with all extents 2.
- The existing elementwise attention proxy at all extents 2 and alias-based
  FFN proxy at M=2,D=1,F=2. These do not validate actual softmax/alias semantics.

For every returned reference frontier witness:

1. Execute the original and normalized witnesses; require identical peak,
   per-tensor reads/writes, total traffic, arithmetic count and checked outputs.
2. Require the existing parser to accept the normalized witness and independently
   check each tile against the original halving/divisor domain.
3. Require normalization to be idempotent, never increase loop count, and obey
   the structural depth bound.
4. Where possible, insert one redundant legal dyadic refinement, independently
   execute it, and verify normalization removes a loop without changing any of
   the checked metrics. Report these synthetic checks separately from changes
   to unmodified reference witnesses.

Each case has an 8 GiB address-space limit and a 120-second timeout. Timeouts
and failures remain in the output. Execution is restricted to the designated
experiment machine. This validates a transformation; it does not measure an
optimizer, avoid reference generation, or demonstrate small skeleton count.

The next algorithmic question, if these checks support the proof, is whether
the *bounded* skeleton set can be generated economically and paired with exact
size solvers. Neither that cost nor coverage of a smaller subset follows from
this theorem.

## Follow-up coverage fixed after inspecting the first run

The original 16 cases passed, but their original witnesses did not trigger the
optional redundant-refinement injection. Do not report that path as tested.
The follow-up uses normalized witnesses from cases 4, 5, 10 and 12 to expose
coalesced loops eligible for refinement. It requires at least one injected case,
unchanged independent execution metrics, and a strict loop-count reduction.

A separate hand-built MatMul has I=4,J=2,K=4, A[I,K], B[K,J], C[I,J]. Its scopes
are J(tile=1, keep A), I(tile=2, keep B), K(tile=1, keep nothing), I(tile=1,
keep nothing). The free K,I block has only C local. Reordering it to I,K would
prematurely invoke the implicit scalar leaf. The guard convention must preserve
its partial spills. Before executing this follow-up, the hand prediction is
peak=21 cells, reads={A:16,B:8,C:24}, writes={C:32}, traffic=80.
