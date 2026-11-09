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
P17 tests the consequence: with c = 1 for partial sums, the curves coincide.

General rule (graph-level): in a fused group, a loop over variable v is
"accumulator-free" iff v indexes every output of the group. If no shared
variable is accumulator-free, every split pays c = 2 on some output or keeps
that output resident. This is a property of the index hypergraph labeled with
input/output roles, readable before any search.

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
   Round to integers at the end and check with the simulator.
3. Lower bound: a write-aware partition bound that charges accumulator planes
   twice. Pairing it with step 2 gives certified gaps; where they meet, the
   curve is exact over all executions, not only over a grammar.

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
