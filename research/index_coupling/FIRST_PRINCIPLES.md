# Where the traffic comes from, and a better method

A design note, not a result. It combines the curve model, Codex's constructive
theorems (TILED_RESULTS.md, SCALAR_RETENTION_PROOF.md) and P11-P17.

## 1. One accounting identity underlies every method so far

Fix a fused group, a loop order over its rank variables, a tile factor T_v per
loop, and for every tensor t a retention position (the loop it is held under).
Then, with no recomputation:

    Q = sum_t c_t * |t| * prod_{v above pos(t), v not in dims(t)} T_v  (+ compulsory)
    S = max over nest points of sum of live tiles

c_t = 1 for a read-only input and 2 for a partial sum that leaves the buffer
(write, read back). The curve model's "kept or refetched" choices, Codex's row
and column strip tables, and the scalar-retention theorem are all instances:
e.g. Codex's (p-1)KL cross penalty is the c_V = 2 term for V, which lacks i,
under an i loop of p trips.

## 2. What the graph decides, and what it does not

For the three-matmul fork, EU and EV iterate the same (i,k,l) space. Each tensor
is a projection onto one plane: ik holds X; kl holds {C, D} (same) or {C, V}
(cross); il holds {U, V} (same) or {U, D} (cross). The planes carry the same
number of tensors, of the same sizes when I = K. Load/store-symmetric I/O
bounds (Hong-Kung, HBL) therefore cannot tell the graphs apart. The difference
is only *which side of each plane is an accumulator*: same puts both outputs on
one plane, so a loop over i (indexing both outputs) leaves only inputs exposed;
cross puts one output on each plane, so every shared loop exposes a partial sum.
P17 tested the consequence: with c = 1 for partial sums, the curves coincide
(95/95 shapes). ROLE_SYMMETRY_AND_SYSTEMS_CASE.md proves it inside the
recursive model by swapping D and V, and shows I = K is not needed: same's D
and cross's V are both K x L, same's V and cross's D both I x L. So every shape
in the sweep is a fair role-only control, including I != K (an earlier caveat
here was wrong). For a paired construction m,
Q_cross - Q_same = (c - 1)(B_KL(m) - B_IL(m)): the sign depends on which plane
the revisited object lies on, which is why I != K shapes are mixed.

Observation (graph-level): in a fused group, a loop over v revisits no output's
partial sums iff v indexes every output of the group. If no shared variable has
this property, every split pays c = 2 on some output or keeps it resident. This
is readable from the role-labeled index hypergraph. It is not by itself a
pruning rule (input reuse and other live allocations also change); using it to
prune needs a replacement argument.

Thesis, tightened: buffer capacity is split between retaining reusable inputs
and retaining unfinished accumulations; the index relations across operators
decide which of these retentions can hold at the same time.

## 3. Why the current methods hit their limits

- The curve model enumerates tile sizes (powers of two) level by level; depth
  grows with sum of log2 extents, so real sizes explode, and the power-of-two
  grid itself creates artifacts (the (32,8,32,4) reverse case flips under
  integer tiles; the I^2/2 term in P15 is the I/2 strip).
- Codex's constructors are exact and fast inside six hand-written families but
  cover about 80% of budgets within 5%: the families are fixed by hand, not
  derived from the graph.

## 4. Proposed method: enumerate structure, solve sizes analytically

Split the decision as the identity suggests.

1. Skeleton (combinatorial, from the graph): fusion grouping, loop order of the
   shared variables, retention position per tensor. Its size depends on the
   index hypergraph and fan-out, not on tensor sizes. Dominance rules prune it:
   Codex's equal-traffic substitution (keep the smaller of X strip versus
   operand/output slices), accumulator-free loops outermost, loops indexing
   every live tensor give no reuse.
2. Sizes (continuous, per skeleton): Q and S are posynomials in the T_v, so the
   per-skeleton Pareto curve is a geometric program (convex in log space), or a
   closed form when one factor is free (Codex's Theorem 3 is this case).
   Ceilings, ragged tails and scope changes are not plain GP constraints; keep
   exact ceiling-quotient elimination where it applies, and report any rounding
   or repair loss. Check executions with the simulator.
3. Lower bound: charging accumulator planes twice is NOT valid as stated (an
   output may stay resident). A valid bound must show which partial sums
   necessarily cross an execution partition, with first/final transfers counted
   (an output revisited in R episodes costs 2R-1, an input R). Only bounds with
   the same memory, recomputation and legality assumptions certify optimality.

Expected gains, to be tested: no power-of-two artifacts; cost independent of
tensor sizes (real FFN and attention sizes become feasible); Codex's families
appear as particular skeletons instead of being written by hand.

## 5. Literature to check before claiming novelty

Automatic I/O lower and upper bounds for affine programs (IOLB, IOOpt, Olivry
et al.), multi-statement pebbling bounds (SOAP, Kwasniewski et al.), HBL-based
communication bounds and their tilings (Christ, Demmel et al.; Dinh and
Demmel), and fused-loop retention models (LoopTree). Our angle is comparative:
how input/output roles on a DAG's index structure change S(q), and what that
implies for buffer sizing and mapper mapspaces (FFM's sharing gaps).

## 6. Obligations per axis, and a proved bound on the coupling cost

**Obligations.** Splitting a fused group along v into T trips makes every tensor
lacking v an obligation: keep its tile (capacity) or revisit it, at
(T-1)|t| for an input and 2(T-1)|t| for a partial sum. Per byte retained, a
partial sum saves twice what an input saves. Retention is whole-tile, so the
choice is a 0/1 knapsack: this density does NOT imply keeping partial sums
first (capacity 10: a size-4 partial sum saves 8, a size-10 input saves 10). For the fork (X has axes i, k):

| Outer axis | same | cross |
| --- | --- | --- |
| i | B, C, D (all inputs) | B, C inputs; V partial sum |
| k | A input; U, V partial sums | A, D inputs; U partial sum |

Each matmul consumer of X contributes exactly one partial-sum obligation (on the
axis it contracts) and one input obligation (on its other axis). The set of
obligated tensors is the same for both graphs; coupling decides how it is
distributed over the axes. The weighted totals are not conserved when I != K
(summing the two axes, cross minus same is (K-I)L). Same concentrates both partial sums on k and leaves i input-only; cross
puts one on each axis. The outer loop picks the cheaper axis, so concentration
helps. Unretained single-split cost per extra trip: same min(JK+2KL, IJ+4IL),
cross min(JK+3KL, IJ+3IL).

**Derived, not fitted.** To match same's traffic, cross either keeps the
exposed partial sum whole (|V| = KL, which is IL when I = K) or keeps half an X
strip instead (IK/2 with a two-way power-of-two split). With I = K this is
I·min(L, I/2), the formula P15 had fitted; its small misses come from inner
levels.

**Proposition (recursive model, any shape, write-through on or off).**

    S_same(q) - IL  <=  S_cross(q)  <=  S_same(q) + KL   for every q.

Proof sketch (incomplete: it still needs a closure argument that the modified
construction stays in the recursive grammar, in particular that making V
external cannot trigger the scalar leaf earlier; see LOOP_NORMAL_FORM.md for
the same issue). Take any same construction m and map it to cross by the D/V swap
(ROLE_SYMMETRY_AND_SYSTEMS_CASE.md). In the image, choose "keep" for cross's V
(K x L) at the outermost level where it lacks the loop variable. Its revisits
vanish, so traffic is Q_same(m) - B_KL(m) - B_IL(m) <= Q_same(m); V is external
inside, so the peak grows by at most one V tile, at most KL. Symmetrically,
from cross to same keeping same's V (I x L). So the capacity cost of a coupling
is bounded by the size of the accumulator it exposes.

**Checked on all 287 swept shapes** (exploratory; the bound was written after
the sweeps): max dS <= min(KL, IK/2) and min dS >= -min(IL, IK/2) hold in all
287. The proved part is the KL / IL bound; the IK/2 alternative is a
construction, not proved in general. The upper bound is attained exactly in
174 shapes (11 more within 5%); the lower one in 88 of the 194 shapes where
cross is better somewhere. Where the first-split costs above favour cross,
cross is better somewhere in 95 of 96 shapes; when they favour same, cross
still wins somewhere in 99 of 191. This is an empirical heuristic, not a
sufficient condition.

**General form, for any fused group.** For each shared axis v, the obligation
set is the tensors lacking v, with weight 2 for outputs contracted over v and
1 for inputs not indexed by v. The index relations across operators fix how
this multiset spreads over axes; buffer capacity buys partial sums first, then
inputs; and the price of an unfavourable spread is at most the size of the
partial sums it exposes on the best axis.

## 7. What sets the maximum capacity gap (witnesses, then a prediction)

Witnesses at the q of the maximum gap (results/fork_witness/, I = K = n, s = nL):

- Pure fork, n·L branch: the fused group splits I, which no consumer contracts.
  The split's obligations are the shared input B and each consumer's C, all
  inputs. Each is kept (capacity s) or refetched (traffic s).
- Mixed fork: every axis of X is some consumer's contraction axis. Splitting the
  axis contracted by fewer consumers (b of them) turns their outputs into
  obligations of partial-sum type: kept (capacity s) or spilled (traffic 2s).
  (8,4,8,2): kkki keeps V3 whole at q=96 (53 vs 37); kkii keeps U0 and U1 at
  q=80 (69) while kkkk keeps one C (53).
- n·n/2 branch (L > n/2): keeping or spilling an exposed accumulator costs more
  than giving up the fused split. The mixed fork holds X whole (n²); the pure
  fork holds half of it.

So in the n·L branch the two forks face the same obligation list, of the same
sizes. The only difference is that b items carry refetch weight 2 instead of 1.
The capacity gap at a traffic budget is how many more items must be kept.
Freeing items costs s each in the pure fork. In the mixed fork, the weight-1
items cost s each and the weight-2 items 2s each. The kept-count difference is
at most ceil(b/2), reached when the budget frees every item of the pure fork.
That gives

    max_q dS = n·min(ceil(b/2)·L, n/2),   b = min(#k consumers, #i consumers).

For m <= 4, b <= 2 and ceil(b/2) = 1. This is why the maximum never grew in
P18 while the positive-gap range (about 2b-1 budget steps of s) did. The same
reading also explains P17. With spill_cost = 1 the weights are equal, the
obligation lists coincide and the gap vanishes.

This is a first-split heuristic, not a proof: deeper levels and other groupings
can change either fork's optimum. P19 (frozen) tests its first new consequence: the
maximum doubles at kkkiii.

**P19 outcome.** The maximum is exact in every shape: n·min(2L, n/2) for
kkkiii (8/8) and n·min(L, n/2) for kkkkki and kkkkii (16/16), so the
first-split knapsack predicts the cap beyond b <= 2. Its second consequence,
that the positive-gap range (about 2b-1 budget steps) widens with b, fails in
8/8 shapes: kkkkii's range is the widest everywhere, and at L=4 kkkiii's is
also below kkkkki's. The knapsack fixes the peak, set at the first split; the
range depends on budgets where deeper levels or the other branch decide, which
it does not model.

## 8. Span-legal ranks: one obligation table for forks, FFN and residual blocks

A group may loop over rank v only if every op in it uses v and every tensor
produced and consumed inside it carries v. For a contiguous span S call these
ranks R(S); they follow from the einsum incidence alone (`graph/context.py`).
Every plan for S in the grammar is a chain of loops over R(S) ending at a
nontrivial partition or a leaf. A loop over v with T trips exposes the tensors
of S lacking v: each is kept whole (capacity) or refetched with weight 1 per
extra trip (input) or 2 (accumulated output). This is a theorem of the grammar,
not a measurement.

| Graph | R(whole graph) | Tensors lacking each rank (weight 2 if accumulated output) |
| --- | --- | --- |
| fork, kk...ii | I, K | I: B, C_k, V_i (2) · K: A, D_i, U_k (2) |
| FFN fwd+bwd | M, F | M: W1, W2, dW1 (2), dW2 (2) · F: X, dY, Y (2), dX (2) |
| attention core | M, P | M: K, V · P: Q, O (2) |
| residual block | I | I: W0, W1 |

The rows unify results obtained separately:

- §7's fork obligations are exactly the I and K rows: the mixed fork's minority
  outputs are the weight-2 entries.
- The executed FFN witness at 80 B (FFN_EXECUTION_AUDIT.md) splits F in two:
  64 B is the F row's inputs X and dY read once more, 128 B its outputs Y and dX
  spilled once. 256+64+128 = 448 is the F row priced at T=2.
- In attention the P row is the online-softmax tradeoff: splitting keys exposes
  O as a partial accumulator.
- All 117 frontier witnesses of the unrestricted P21 curves loop over I only at
  whole-graph level, as R = {I} requires (K is illegal because H0 lacks K).

What R(S) does not decide is where the bottom partition cuts. The exploratory
attribution in P21_RESULTS.md (`attribute_p21.py`) separates the two: chaining
I loops above the fixed EX|H|EAdd boundary removes 54% of its wrong integer
capacities at depth 2 but only 20% at depth 8, where the cut placement
dominates. A composable summary therefore needs (a) the R(S) chain context and
(b) freedom in which tensors cross the bottom cut; a fixed cut cannot be
summarized by one curve however rich its residency state.
