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

## 6. Obligations per axis, and a candidate bound on the coupling cost

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
helps in this single-split comparison, not necessarily in the optimized full
curve. Unretained single-split cost per extra trip: same min(JK+2KL, IJ+4IL),
cross min(JK+3KL, IJ+3IL).

**Motivating constructions, not a general proof.** Keeping the exposed partial
sum whole (|V| = KL, which is IL when I = K), or retaining half an X strip
(IK/2 with a two-way power-of-two split), suggests I·min(L,I/2) at I=K,
the formula P15 had fitted. Their general legality and optimality are not
established; the first-split account alone does not explain every inner-level
deviation.

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
287. Neither the KL / IL bound nor the IK/2 alternative is currently a complete
general theorem: the former still needs the closure argument above, and the
latter is a construction. The upper bound is attained exactly in
174 shapes (11 more within 5%); the lower one in 88 of the 194 shapes where
cross is better somewhere. Where the first-split costs above favour cross,
cross is better somewhere in 95 of 96 shapes; when they favour same, cross
still wins somewhere in 99 of 191. This is an empirical heuristic, not a
sufficient condition.

**General form, for any fused group.** For each shared axis v, the obligation
set is the tensors lacking v, with weight 2 for outputs contracted over v and
1 for inputs not indexed by v. The index relations across operators fix how
this multiset spreads over axes. At a fixed split, whole-tile retention is a
0/1 knapsack, not a partial-sums-first rule. Extending the proposed capacity
bound to arbitrary groups requires a legal replacement construction; a table
of obligation weights alone does not establish that bound.

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
also below kkkkki's. The first-split knapsack predicts the measured peak; the
range also involves budgets where deeper levels or the other branch decide,
which it does not model. Exact agreement on these eight held-out shapes validates
the frozen maximum-gap prediction; it does not prove the first split fixes
the optimum in every shape. The interval analysis in §9 leaves P19c failed.

## 8. Span-legal ranks: one obligation table for forks, FFN and residual blocks

A group may loop over rank v only if every op in it uses v and every tensor
produced and consumed inside it carries v. For a contiguous span S call these
ranks R(S); they follow from the einsum incidence alone (`graph/context.py`).
This statement is for the unconditioned span. The implementation's arbitrary
external-residency queries have a separate contract and are not covered by
this unconditioned statement.
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
- In the modeled attention core, splitting P exposes O as a partial
  accumulator. The current elementwise-softmax abstraction omits row maximum,
  normalization sums and rescaling; this is not a complete online-softmax
  resource or execution theorem.
- All 117 frontier witnesses of the unrestricted P21 curves loop over I only at
  whole-graph level, as R = {I} requires (K is illegal because H0 lacks K).

What R(S) does not decide is where the bottom partition cuts. The exploratory
attribution in P21_RESULTS.md (`attribute_p21.py`) separates the two: chaining
I loops above the fixed EX|H|EAdd boundary removes 54% of its wrong integer
capacities at depth 2 but only 20% at depth 8, where the cut placement
dominates. To cover the unrestricted grammar, composition therefore needs
(a) the R(S) chain context and (b) alternatives for which tensors cross the
bottom cut. A conditional curve can be exact for one fixed cut, as P21 shows;
it does not thereby represent plans using other cuts.

## 9. What the completed P19 and native FFN checks actually distinguish

This section is exploratory synthesis after P19, not an amended prediction.
`analyze_p19_profile.py` reads the 32 saved curves and reuses P18's exact
step-interval integration. No mapping search is run. The signed area also
matches the independent capacity-axis integral, and inserting extra samples
inside constant intervals changes none of the reported metrics.

### Peak, support width and average are different questions

Let Delta_b(q)=S_b(q)-S_0(q), where b is the minority consumer count and q
is extra traffic above the common compulsory floor. Use the same finite
[0,q_hi] domain for every role mix of a shape.

| Comparison, b=3 versus b=2 | Shapes satisfying it |
| --- | ---: |
| Wider positive-gap domain (frozen P19c component) | 0/8 |
| Larger signed area integral of Delta_b | 8/8 |
| Larger uniform-q mean of Delta_b / S_0 | 2/8 |
| The two inverse curves cross | 8/8 |

In fact signed areas increase b=1 < b=2 < b=3 in all eight shapes. That is a
post-hoc observation, not a replacement success criterion for P19c. Area
has units B²; its normalized mean assumes a uniform distribution of traffic
budgets and is not an expected deployment saving. None of these summaries
alone gives a pointwise ordering.

The shape (I,J,K,L)=(16,4,16,4), with 896 B compulsory traffic, gives a direct
counterexample to monotone ranking by minority count:

| Allowed **total** traffic | Pure capacity | b=1 capacity | b=2 capacity | b=3 capacity |
| ---: | ---: | ---: | ---: | ---: |
| 1,344 B | 137 B | 201 B | 201 B | 265 B |
| 2,624 B | 55 B | 69 B | 69 B | 55 B |

At the first budget b=3 incurs the predicted 128 B maximum gap. At the second
it matches the pure fork and needs 14 B less than b=2. The plots and exact
intervals are in `results/p19_profile.{png,pdf,json}`. All statements retain
P19's fixed consumer order and power-of-two grammar; they are not an
order-completed or arbitrary-integer-tile theorem.

### The FFN first-layer obligation tables tie

At M=F=8, D=E=4, each tensor in the M and F obligation rows has size 32 B.
For two outer trips, keeping none of those obligations costs in either row:

    2 input tiles × 32 B + 2 accumulator tiles × 2 × 32 B = 192 B extra.

Adding compulsory traffic gives 448 B **if the inner execution adds no extra
traffic**. Thus the first-layer table cannot by itself choose M over F or
explain why the selected native M-first plan costs 576 B. Neither does it
prove a 448 B M-first plan fits the 80 B budget.

Detailed native replay supplies the missing term. In each of two M blocks,
EH and EdX independently read the 32 B W1, while EY and EdZ independently
read W2. Relative to one shared fetch per block, this adds 32+32=64 B per
block, or 128 B overall. The independently executed F-first graph witness
has no analogous child-level extra traffic:

    Native M-first: 256 + 192 + 2×64 = 576 B.
    Graph F-first:  256 + 192 + 2×0  = 448 B.

This is counted traffic for the two schedules, not an optimality proof for
either axis. Native actual peak is 76 B and graph peak is 80 B, both within
the common 80 B budget. See FFN_NATIVE_ATTRIBUTION.md for the copy-order
reconstruction control and native versus independent-executor distinction.

For these schedules no intermediate reaches DRAM. A more precise accounting
unit is a physical residency episode of a cell: an input loaded e times costs
e reads; a terminal accumulator processed in r resident segments costs
2r−1 transfers, including its final write. Several consumers may share one
input episode. A single (tile size, input/output weight) does not determine
the number of episodes: consumer grouping, scope and the inner plan do.

### Consequence for a sufficient summary

Three separate roles are now evidenced:

1. Rank incidence rules out illegal whole-span loops before tile search.
2. Role/size obligations price a **fixed** split and retention choice.
3. Conditional child curves and cut alternatives account for shared copies,
   lifetime overlap and the additional cost of completing that choice.

P19 supports one quantitative maximum-gap prediction; it also refutes the
proposed monotone support-width rule. FFN shows that equal first-layer tables
can have different child costs. P21 shows that adding loop contexts to one
fixed cut is insufficient to recover the free-cut curve. These support a
scope-sensitive, conditional demand description, not a scalar graph score.
They do not yet prove that a sufficient description is compact or cheap to
construct. Keep the existing grammar and measured effects while testing that
remaining question; do not infer a new optimizer or speedup from this synthesis.

## 10. Conditional residency value and release contracts (P21 follow-up)

For fixed P21 endpoints, let Q0(c) be H's curve with X in DRAM and Q1(c)
its curve with X resident and its reservation charged outside H. Define
V_X(c)=Q0(c)-Q1(c). On the finite, endpoint-compatible domain,

    3s + Q1(C-s) < 5s + Q0(C)
    iff Q0(C-s)-Q0(C) < 2s + V_X(C-s).

Equality is a tie; infeasible branches must be compared directly. If H does
not access X, V_X=0 by projection. If it does, V_X includes both eliminated
reads and the effect of removing X's local allocation. It need not be constant
or monotone. In the 10-operator (2,2,4) example, V_X(3..6)=16,4,16,4 with s=4.
All 212 finite eligible comparisons agree with the saved monolithic branches.

The exploratory fixed-partition curve in §8 allows H_last retention; frozen
P21 forces H_last through DRAM. The latter has a 2s plateau penalty in every
case. Separate that policy change from outer-loop lifting and moving cuts.

P21_CUT_ANALYSIS.md gives a constructive follow-up: four chosen first-cut
families recover 12/16 seen curves, and one more family selected from the
remaining errors closes all 16; 560 new witnesses execute exactly. The missing
family splits the elementwise tail so that an incoming H1 reservation ends at
its last use. A conditional tail at I=1,K=2 has local minimum-traffic capacity
13 under group entry and 5 under solve entry. Pinning its two two-element
external inputs throughout the macro still requires 9 total capacity, while
the whole-graph streamed-tail witness fits in 8 by releasing H1 earlier.

This requires distinguishing "resident on entry, releasable after last use"
from "pinned until exit". It does not prove that these labels alone form a
sufficient or minimal quotient. The five-family envelope was selected on seen
data and its children still use the full recursive solver. A held-out contract
check, not a broader hardware model, is the next discriminating experiment.

## 11. P21d: local cut contexts and ownership of a physical store

The frozen P21d experiment tests one topology-only generator on unseen
depths/shapes. Adjacent whole-prefix/suffix rank changes and last crossing
uses select every cut except the one after EX. Four valid paired frontiers
are unequal, two are equal, two have an accounting validity failure, and
four depth-12 cases are incomplete at the frozen time limit. See
P21D_RESULTS.md for the rule, coverage and raw witnesses.

At (8,2,4), depth 4, H not reading X, capacity 4, the restricted and free
curves give 336 and 328. Both schedules execute exactly. The free witness
uses `EX | EH0 | tail`: the two cuts isolate EH0 and let it put L outside I.
The restricted witness fixes I outside before separating EX and EH0. The
free witness saves 56 W0 reads at the cost of 48 additional D reads. Thus
the opportunity is local to the child exposed by a **pair of endpoints**.
It need not appear as a whole-prefix or whole-suffix rank event at each
endpoint. This refutes the frozen generator; it does not prove that a
lifecycle-state quotient is insufficient.

The second finding concerns physical accounting. At (4,8,2), H reading X,
two structural witnesses predict 32 more transfers than they execute. A
parent and its child both charge the final write of the same 32-cell X.
The cell executor stores X once; later reads reuse its DRAM backing. This
also occurs with pre-P21d source. No rule for adding costs can count the
same physical store in two nested scopes.

An ancestor-owned final-write ledger matches all 160 saved executions;
the unmodified ledger reproduces all 160 predicted prices. This is a
post-hoc diagnosis, not a repaired optimizer: discarded schedules have not
been re-evaluated. A compositional proof must assign each physical transfer
to exactly one scope, with partial-sum spills handled separately. It may
require backing/charge state or a different ownership convention; these
records do not prove a minimal representation.

The cache projection theorem establishes equivalence for its recurrence.
It does not establish that the recurrence prices physical execution
correctly. Likewise, exact replay of all selected frontier witnesses does
not certify prices of candidates discarded during search. Preserve the
frozen P21d verdict and repair that correctness obligation before another
sufficiency experiment or the P22 overlap extension.
