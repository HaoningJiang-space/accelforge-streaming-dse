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
