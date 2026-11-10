# Frozen predictions for held-out shapes

Written after the n = 4, 8 and 16 square runs and before any run below. The
held-out cases are not used to change these statements. Each case runs
`run.py --no-join`, with and without `--cross`.

| Case | NI | NJ | NK | NL |
| --- | ---: | ---: | ---: | ---: |
| T1 square | 32 | 32 | 32 | 32 |
| T2 token-heavy | 64 | 8 | 8 | 8 |
| T3 width-heavy | 8 | 32 | 32 | 32 |

## Mechanism behind the predictions

Same: `V[i,l] = X[i,k] D[k,l]`. Cross: `V[l,k] = D[l,i] X[i,k]`. When X is
streamed by rows (i outermost), the same graph keeps D resident: D is an
input, so each extra pass rereads it once. The cross graph must keep V's
partial sums resident instead: V lacks i, so it is an accumulator, and each
extra pass writes and rereads it. |V_cross| = NL·NK = |D_same|, and
|D_cross| = NL·NI = |V_same|. Transposition therefore swaps which tensor is
resident without changing resident sizes, but changes the cost per extra pass
from |D_same| to 2|V_cross|.

## Predictions

- **P1, equal plateau.** Same and cross reach the algorithmic minimum traffic
  (read A, B, C, D once; write U, V once) at the same capacity.
- **P2, plateau location.** The plateau capacity lies in [R, R + 2·max(N) + 1],
  where R = min(|B|+|C|+|D_same|, |A|+|U|+|V_same|, |X|).
  T1: R = 1024, exact prediction 1057 (n²+n+1). T2: R = 192, so [192, 321],
  traffic 1728. T3: R = 256, so [256, 321], traffic 3840.
- **P3, transfer law.** Take every same-frontier point whose mapping has zero
  X traffic and reads B, C and D_same each exactly p ≥ 2 times their size.
  At that capacity, the cross frontier equals
  `min(F_mat(C), F_same(C) + (p−1)·(2|V_cross| − |D_same|))` exactly.
- **P4, onset (square only).** The first capacity at which cross fusion beats
  the materialized frontier is (n/2)² + n/2 + 1 = 273 B for T1.

Any miss is reported as a miss; the statements are not revised for these cases.

## Amendment before reading held-out output

Running `evaluate.py` on the training runs (n = 8, 16) shows that P3 as
written already fails at one point per size: n=8 at 21 B (predicted 960,
measured 896) and n=16 at 73 B (3840 vs 3584). At those points the same
graph's mapping itself spills both U and V partial sums, so transposition adds
no cost. P3 remains scored as written. A narrower statement is added:

- **P3′.** As P3, but only at same-frontier points whose mapping also writes
  V_same exactly once (D is the resident tensor, V is not spilled).

This amendment was committed while the held-out runs were in progress and
before any of their output was read.

# FFN training step (upstream FFM, copy-wrapped inputs, no detailed evaluation)

Calibration seen before freezing: M=8, D=4, F=8 reaches the algorithmic
minimum 256 B at 147 B. There the two single-nest resident sets tie at 128 B.

Single loop nest with outermost index s; every tensor lacking s stays on chip:
- s = m (tokens): {W1, W2, dW1, dW2}, R_m = 4·D·F.
- s = f (FFN hidden): {X, Y, dY, dX}, R_f = 4·M·D.

Let R = min(R_m, R_f). Frozen before running:

| Case | M | D | F | R_m | R_f | Predicted resident set |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| F1 token-heavy | 16 | 4 | 8 | 128 | 256 | weights and weight gradients |
| F2 hidden-heavy | 4 | 4 | 16 | 256 | 64 | activations and their gradients |

- **P5.** Each case reaches the algorithmic minimum (inputs read once,
  outputs written once).
- **P6.** The plateau capacity lies in [R, 1.25·R]: F1 in [128, 160], F2 in
  [64, 80].
- **P7.** At the plateau, the mapping keeps the predicted set on chip: in F1,
  F2's set does not fit (R_f = 256 > 160), and vice versa.

These are join values from FFM without detailed re-evaluation, so P5–P7 test
the model against FFM's own mapspace, not against a replayed execution.

# Nest model (`nest_model.py`), frozen before C1, C2, F3, F4

The model computes the minimum buffer with zero extra DRAM traffic over
recursive loop nests (see its docstring), with no mapping search. Calibration
points already seen: all six coupling plateaus (exact), FFN F2 (81, exact) and
the two D4·F8 FFN cases (model 148, measured 147). Copy einsums are aliases.

| Case | Workload | Sizes | Prediction, B |
| --- | --- | --- | ---: |
| C1 same / cross | coupling, no join | I16 J4 K32 L8 | 337 / 337 |
| C2 same / cross | coupling, no join | I8 J16 K4 L32 | 37 / 37 |
| F3 | FFN with copies | M8 D2 F16 | 76 |
| F4 | FFN with copies | M16 D8 F4 | 149 |

- **P8.** Each measured plateau equals the prediction exactly.
- **P8′.** Each measured plateau is within 2 B of the prediction (allows the
  calibration's one-scalar excess).
Coupling cases use the fork's `run.py` with replay; FFN cases use the upstream
probe without detailed evaluation.

# F4 copy-order test, frozen before running

Codex's review (REVIEW_NOTES.md) found that placing `CopydY` first makes the dY
token row live from the start; adding that lifetime to the nest model gives
exactly F4's measured 153 B and leaves F1–F3 unchanged. If this is the cause,
moving `CopydY` to just before its first consumer (EdW2) should remove it.

- **P9.** With the late dY copy, F4 (M16 D8 F4) reaches the algorithmic
  minimum (640 B) at exactly 149 B, the nest model's value.
- **P9′.** With the late dY copy, F1 (M16 D4 F8) stays at 147 B.

# Attention core, frozen before running

`attention_core.yaml` (S = QKᵀ, softmax as elementwise, O = AV; Q, K, V are
graph inputs read once). Nest model predictions:

| Case | M | P | E | F | Prediction, B | Model's resident set |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| A1 | 8 | 8 | 4 | 4 | 74 | K, V (query-outer) |
| A2 | 16 | 4 | 4 | 8 | 56 | K, V (query-outer) |
| A3 | 4 | 16 | 8 | 4 | 56 | Q, O (key-outer) |

- **P10.** Each FFM plateau is within 2 B of the prediction.
- **P10′.** Each is exact.
The model ignores online-softmax row statistics (max and sum, 2·M values).

# Write-through switch and chain view, frozen before running

`curve_model.curve(..., write_through=False)` forbids an intermediate from both
feeding a consumer in its producer's group on chip and going to DRAM for another
group (the sharing FFM cannot encode, REVIEW_NOTES_2.md E1). `chain_view.py`
rewrites a graph so each tensor passes on chip to its first consumer only.
Calibration seen before freezing: n4 same/cross only (write-through off gives
FFM's 288 B at capacity 6 for n4 cross; both chain curves are identical).

- **P11.** With write-through off, the model equals FFM's best traffic at the
  six cross points L1–L6, and the four attention points L7–L10 stay lower
  (attention has no multi-consumer tensor).
- **P12.** With write-through off, the FFN M8 D4 F8 model is never below FFM's
  best at any saved FFM capacity. A failure means write-through is not the
  whole explanation of the FFN gaps.
- **P13.** For square coupling (n8, n16, T1), the chain-view curves of same and
  cross are identical, while the graph-view curves differ.
- Measurement, no prediction: chain-view minus graph-view traffic at each
  capacity for coupling and FFN M8 D4 F8. At unbounded capacity the gap is by
  construction the extra reads and writes of multi-consumer tensors.

# Amendment to P11's scope (after the union-breakpoint check)

P11 passed as frozen (scored at FFM's saved capacities). Scored on the union of
FFM and model breakpoints, the no-write-through model is still below FFM's
archived best at 19 non-attention breakpoints (n8/n16/T1/T3 cross, T2/C1/C2
same and cross), all between FFM's saved capacities. So write-through does not
explain every coupling gap; the README claim that it did is withdrawn.

# FFM-like sharing, frozen before running (P14)

Witnesses for n8 cross and T2 same at 18 B (seen before freezing) run EX alone,
send X via DRAM, and tile EU and EV jointly so one fetched X tile serves both.
Hypothesis: FFM shares a tensor between einsums only through its backing
reservation, so a DRAM-backed tensor is fetched separately by each consumer.
`ffm_like.py` restricts the curve model accordingly (multi-consumer
intermediates stay on chip for all consumers or are fully materialized;
multi-consumer graph inputs are read per consumer). Calibration: n4 same/cross
match FFM exactly on the union of breakpoints.

- **P14.** On the union of breakpoints, the FFM-like curve equals FFM's archived
  best traffic at every capacity for the other 14 coupling cases (n8 to C2,
  same and cross).
- **P14-FFN.** Same for FFN M8 D4 F8 (copies as aliases), allowing the known
  1 B plateau offset (147 vs 148).
- **P14′.** For the three attention cases (no multi-consumer tensor) the
  FFM-like curve equals the graph curve, so their gaps remain unexplained.

# Coupling capacity gap, frozen before running (P15, P16)

Exploratory sweep (results/coupling_sweep.jsonl, sides 4 to 32): with I = K the
two graphs have identical operators, tensor sizes and per-operator costs. The
maximum over traffic targets of dS(q) = S_cross(q) - S_same(q) (sweep_analysis.py,
extra traffic above each graph's plateau) equals I·min(L, I/2) in 61 of 64
shapes; the other 3 (I = 32, L ≤ 8) are 4 B lower. Fitted after seeing the data.
Witness reading: a split along a variable shared by all three einsums leaves
one consumer's output without that variable when cross (U lacks K, V lacks I),
so the output becomes a partial sum that is kept resident or spilled at twice
the cost; same has I in both outputs.

Held-out shapes: (64, J, 64, L) for J, L in {4, 8, 16, 32, 64}, and (I, J, I, 64)
for I in {8, 16, 32}, J in {4, 16}; 31 shapes, write-through on.

- **P15.** max_q dS(q) = I·min(L, I/2) exactly in at least 28 of 31 shapes.
- **P15′.** Within 5% of I·min(L, I/2) in all 31.
- **P16.** dS(q) ≥ -0.05·S_same(q) at every q in every held-out shape, and the
  plateau dS(0) = 0 in all 31.

# Read-write asymmetry as the source of the coupling cost, frozen before running (P17)

First-principles argument. EU and EV both iterate (i,k,l). Every tensor is a
projection onto one plane: ik holds X; kl holds C,D (same) or C,V (cross); il
holds U,V (same) or U,D (cross). Both graphs put the same number of tensors on
each plane, and with I = K the same sizes. They differ only in which tensor on
a plane is a read-only input and which is an accumulated output. I/O bounds
that charge loads and stores alike (Hong-Kung pebbling, HBL) are therefore the
same for both. The only asymmetry left in the curve model is the cost of a
partial sum leaving the buffer: 2 transfers (write, read back) versus 1 for
refetching an input. Calibration seen before freezing: (4,4,4,4), (8,4,8,4),
(4,8,4,16), (8,8,8,8) give identical curves with spill_cost=1 and different
ones with spill_cost=2.

- **P17.** With `spill_cost=1` (accumulate in place at DRAM), the same and cross
  curves are identical, point for point, for all 95 I = K shapes of
  coupling_sweep.jsonl and coupling_sweep_heldout.jsonl, with write-through on.
- **P17-control.** With the default `spill_cost=2` they differ in all 95 (already
  implied by the sweeps; rechecked in the same run).

# Forks with three and four consumers, frozen before running (P18)

`nest_model.fork(I, J, K, L, roles)`: X = AB feeds one consumer per role;
'k' contracts K (U = X C, U is I x L), 'i' contracts I (V = D X, V is L x K).
With a 'k' and b 'i' consumers (m = a + b), the obligation table gives the
unretained first-split cost per extra trip nJ + nL(m + min(a, b)) when I = K = n:
every minority consumer exposes one partial sum on the cheaper axis. Seen before
freezing: only that fork(4,4,4,4,'kk') and 'ki' reproduce the two-consumer
curves. Shapes: (n, J, n, L), n in {4, 8, 16}, J, L in {4, 8}; roles kkk, kki,
ikk, iik, kkkk, kkki, kkii. dS(q) as in sweep_analysis.py (extra traffic).

- **P18a.** For each mixed roles string with b 'i' consumers, versus the all-'k'
  string of the same length: -b·IL <= dS(q) <= b·KL at every q.
- **P18b.** Mixed strings never need more than 5% less capacity than all-'k'
  at any q (all shapes have I = K).
- **P18c.** For kki versus kkk, max_q dS = n·min(L, n/2) in at least 10 of 12
  shapes and within 5% in all 12 (one exposed partial sum, as for two
  consumers).
- **P18d.** max_q dS(kkii vs kkkk) >= max_q dS(kkki vs kkkk) in every shape
  (cost grows with the number of minority consumers).
- **P18e.** iik and kki give identical curves (transposition symmetry, I = K,
  A and B both n x J). kki and ikk may differ (consumer order matters in the
  grammar); no prediction.

# Six-consumer forks, frozen before running (P19)

Seen before freezing (fork_witness.py at the max-gap q; two consumers (8,4,8,2)
and (4,4,4,8); four consumers (8,4,8,2) kkkk/kkki/kkii and (4,4,4,8) kkkk/kkii):

- n·L branch. The pure fork splits I outermost (no consumer contracts I), so the
  split's obligations are inputs only: B and every C, refetch weight 1. A mixed
  fork splits the axis contracted by fewer consumers; each of those b consumers
  leaves a partial sum lacking the split axis, refetch weight 2 (spill). All
  consumer tensors have size s = nL. Keeping an item costs s capacity, dropping
  it costs s (input) or 2s (partial sum) traffic. At kkii q=80 the pure fork
  keeps one C (53) and kkii keeps U0 and U1 (69); at kkii's next budget it keeps
  one U and spills the other. Gap s in every case.
- n·n/2 branch (L > n/2). Keeping or spilling an exposed partial sum costs more
  than abandoning the fused outer split: the mixed fork holds X whole (n²) where
  the pure fork holds an I-half (n²/2).

First-split knapsack (heuristic: deeper levels are not modelled). With the
shared input (A or B) dropped first and budget k·s for the consumer items, the
pure fork drops min(m, k) items; the mixed fork drops k items while k <= m-b,
then one partial sum per 2s. The kept-count difference peaks at k = m with
value ceil(b/2), and is positive for k in [m-b+1, m+b-1]. Hence the predicted
max_q dS = n·min(ceil(b/2)·L, n/2), b = min(#k, #i). For m <= 4 this equals
n·min(L, n/2) for every mixture, which is why P18c and P18d (equality) held. It
first differs at b = 3.

Shapes (n, J, n, L): n in {8, 16}, J in {4, 8}, L in {2, 4} (8 shapes). Roles
kkkkkk, kkkkki, kkkkii, kkkiii. dS(q) and extra traffic as in P18.

- **P19a.** max_q dS(kkkiii vs kkkkkk) = n·min(2L, n/2) in at least 7 of 8
  shapes, and is strictly greater than max_q dS(kkkkii vs kkkkkk) in all 6
  shapes with L <= n/4 (n=8,L=2 and all n=16).
- **P19b.** max_q dS = n·min(L, n/2) for kkkkki and for kkkkii, each in at least
  7 of 8 shapes.
- **P19c.** The length of q with dS > 0 (common domain [0, q_hi] per shape as in
  P18_PROFILE_PROTOCOL.md) strictly increases kkkkki < kkkkii < kkkiii in at
  least 7 of 8 shapes.
- **P19d.** -b·IL <= dS(q) <= b·KL at every q for every mixed string (P18a).

A P19a failure with kkkiii's maximum equal to n·L means the first-split
knapsack does not explain the cap, whatever the P18 agreement.

# P14-FFN outcome and an amended FFN test, frozen before running (P14-FFN')

P14-FFN failed: with all 8 subsets the FFM-like union is never below FFM's best
on the union of breakpoints (0 points), but it is above it at 15 points. Seen
before freezing: its lowest traffic is 384 = 256 + 4·32, one extra read of each
multi-consumer graph input (X, W1, W2, dY). FFM's reference case wraps these
inputs in copy einsums (ffn_full_copy), so each is read once and its copy can be
shared on chip like an intermediate. The frozen rule "multi-consumer graph
inputs are read separately" therefore does not describe this case.

Amended view (`ffm_like_si`): multi-consumer graph inputs are left to the curve
model (kept on chip across groups or read once per group); intermediates are
unchanged from P14 (on chip for all consumers or materialized). Same 8 subsets
of {H, Z, dH}, same scoring (graph/scoring.py ffn).

- **P14-FFN'.** On the union of breakpoints, the ffm_like_si union equals FFM's
  best at every saved-capacity breakpoint, allowing the known 1 B plateau
  offset (147 vs 148).
- **P14-FFN'-weak.** It is never above FFM's best (it may be below: reading an
  input once per group is cheaper than materializing a copy, which FFM also
  writes).

# Retain or spill across a residual block (P21, frozen 2026-11-09)

Frozen before executing any P21 curves. Independent of P19; P20 remains a
separate prediction to freeze after P19. Serial, no recomputation, one memory
channel, unit-byte elements, exact Pareto pruning, existing divisible halving
tile grammar. No prefetch, overlap, double buffering, bank or 3D model.

Graphs: `residual(I,K,L,depth,reads_x)` in graph/model.py. X = copy(R), then
H0 = D W0 (P21a) or X W0 (P21b), H1 = H0 W1, depth-2 elementwise operations,
finally Z = H_last + X. D has X's shape. Shapes (I,K,L): (2,2,2), (2,2,4),
(4,2,2), (4,4,2); depth in {2,8}. Both read modes: 16 cases, including eight
10-operator graphs. Compare every integer capacity through the last breakpoint
of either curve; the constant tail is also checked. Do not assume one switch:
report all retain/spill/tie/infeasible intervals.

Definitions and necessary qualifications (not experimental outcomes):

- s = |X| at the current interface granularity. A dirty internal X written once
  and read once later costs 2s. A clean input, an already-written tensor, or
  multiple consuming groups has a different transfer count.
- Q_H is calculated independently, with the same entry mode as the child in
  the grammar (`group_curve` for a fixed sibling group). Its boundary traffic
  and external/resident tensors must be specified. A standalone arbitrary
  `solve` curve cannot silently replace a `group_curve` child.
- If H never accesses X, holding X only shifts its capacity by s. For this
  bridge, keep is strictly better iff Q_H(C-s)-Q_H(C) < 2s; equality is a tie.
  Infeasible capacities use +infinity; never subtract infinity from infinity.
- This identity alone does not prove a whole-graph identity. The producer and
  join can bind capacity, and free fusion can cross the proposed boundary.
  We record both effects instead of treating them as failure of cache projection.

**P21a-bridge (exact prediction).** H does not read X. Independently computed
H curves with/without an unused external X are identical before the caller's
s-byte reservation. The two-choice bridge is exactly
min(Q_H(C-s), Q_H(C)+2s), with all equality intervals explicitly retained.

**P21a-composition (exact prediction).** Fix the top partition EX | H | EAdd,
materialize H_last, and either keep X through all three groups or send it via
DRAM. Calculate each child's curve independently, excluding the traffic and
allocation of external X. Compose serially with max(capacity), sum(traffic),
adding s to each phase while X is resident. The predicted whole frontier and
branch choices equal a monolithic recursion restricted to the same root
partition and X decision at every capacity. Producer/join costs are included;
the bare bridge inequality is compared separately wherever endpoints are
feasible and add identical traffic to both branches.

**P21a-free (diagnostic, no equality prediction).** Compare that fixed-interface
frontier with the unrestricted whole-graph frontier. Record every discrepant
interval and a witness. Equality is not implied by the bridge theorem.

**P21b-coarse (falsifiable prediction).** H reads X. Apply the same capacity-only
bridge formula to the standalone DRAM-input Q_H. Predict at least one wrong
capacity across the eight cases, including feasibility disagreements. Keep
common endpoint profiles when comparing coarse and corrected whole curves so
that an endpoint change is not mistaken for a failure of the H interface.

**P21b-interface (exact prediction).** Replace the coarse retained child by
Q_H(C-s | X resident), excluding X's compulsory read; the spilled child uses
Q_H(C | X in DRAM). Compose producer and join as above. Predict exact equality
with the fixed-root monolithic recursion. Repeat at full granularity and tiles
(I/2,K), (I,K/2), (I/2,K/2) where integral, with L unchanged, recording the exact
extents and residency. These are conditional interface experiments, not a
claim that shrinking the whole graph models arbitrary partial retention.
Report whether granularity alone suffices: same extents with different X
residency must remain distinguishable if their curves differ. X's fixed
lifetime is producer through join; varying lifetime is deferred.

Verification: preserve branch curves, exact error intervals, witnesses, source
revision, protocol hash, Python version, elapsed time and peak RSS. Replay the
unrestricted and fixed-root whole witnesses cell by cell using simulate_nest;
its product-valued join is access-equivalent to addition (numerical addition
is not a claim). Test default solver regression on archived curves. Resource
limit per case: one worker, 8 GiB address space, 180 seconds; timeout/error is
an incomplete case, never a pass. Run on the user-designated experiment server.

# Structural cuts and lifetime events on held-out residuals (P21d)

Frozen before any curve calculation on the P21d shapes/depths. Prior evidence
is P21_CUT_ANALYSIS.md: five hand-selected first-partition families recovered
16 seen curves, with the last family chosen after inspecting errors. P21d
replaces that menu by a topology-only rule; it does not amend P21a/b or turn
those exploratory families into held-out predictions.

## Fixed cases and execution scope

Use `residual(I,K,L,depth,reads_x)` without changing its operators. Shapes are
exactly (8,2,4) and (4,8,2); depths exactly 4, 6 and 12; reads_x is False and
True: 12 cases (6, 8 and 14 operators). These shape/depth combinations were not
used to select the earlier menus. Keep serial execution, no recomputation,
unit-byte elements, the existing divisible-halving tile grammar, spill_cost=2,
write_through=True, split_shared=True, and exact Pareto pruning. No overlap,
new release primitive, alias rewriting, reordering or change to scalar leaves.

As in the preceding cut analysis, restrict the **first nontrivial partition
of the whole span**, including after any chain of whole-span loops. All proper
child spans retain the existing solver. This tests a sufficient menu for that
interface, not a recursive restriction at every cut and not a proof that a
small set of lifecycle labels is itself sufficient.

## Deterministic structural rule (no cost or witness input)

Let S=(o_0,...,o_(n-1)) in the existing fixed order. A cut position k means
between o_(k-1) and o_k, with 1 <= k < n. R(T) is the bare-span legal rank set:
the intersection of ranks used by all operators in T, excluding any rank
absent from a tensor both produced and consumed inside T. It is structural;
unit extents do not remove ranks from R. The whole-span contexts in these
residuals expose only W0/W1 as external tensors, neither an internal result.

Select k if at least one of these conditions holds:

1. **Adjacent rank-set change.** R(S[k-1:]) != R(S[k:]), or, for k >= 2,
   R(S[:k-1]) != R(S[:k]). The empty prefix has no rank set and does not
   automatically select position 1. Record the before/after sets and which
   transition selected the position.
2. **Last use of a crossing tensor.** A tensor has accesses in at least two
   distinct operators of S (a producer's output counts as an access), and its
   last input/consumer access in S is o_(k-1). This denotes a residence that
   can span an internal operator boundary. A one-use input/weight is local,
   not crossing, and does not by itself select a cut. Graph outputs with no
   later consumer in S create no such event. Record each tensor and its
   producer/access/consumer indices.

The candidate set K(S) is their union. All nonempty subsets of K(S) are allowed
first nontrivial partitions; the empty subset remains available to wrap the
span in a legal loop before partitioning. Retention choices at allowed cuts
remain exhaustive, including H_last retention. Compute K once from topology
and keep it fixed across extents and outer input reservations. Tensor names,
case outcomes and the old hand-selected menu must not affect selection.

These definitions deliberately resolve two possible vacuities: counting
single-use weights would select essentially every boundary; comparing every
prefix/suffix only with the whole span rather than adjacent spans could also
select nearly every boundary. Report excluded positions, candidate-position
fraction and candidate partition count versus 2^(n-1). If K equals every
position, equality on that case is an accounting control, not positive evidence
for pruning or minimality. No new cut event may be added after seeing results.

## Predictions and scoring

- **P21d-equality (primary).** On all 12 cases, the envelope allowed by K(S)
  equals the unrestricted capacity/total-traffic curve at every capacity.
  Score the union of both breakpoint sets, including infeasibility and the
  constant tail. Report all maximal discrepant intervals. One confirmed
  mismatch falsifies the 12/12 prediction; no tolerance or pass-fraction change.
- **P21d-validity (required check).** Every saved candidate and reference
  frontier witness must replay with exactly its predicted peak and traffic.
  The restricted curve must never fall below the reference. A replay failure
  or a below-reference curve is an implementation/model issue to investigate,
  not evidence that the structural prediction passed or failed cleanly.
- **P21d-scope.** A failure establishes that these two event rules do not cover
  the optimum in this grammar. Inspect the first counterexample to distinguish
  missing cut events from insufficient boundary state. It does not by itself
  prove that occupancy profiles, an additional lifecycle label, or a new
  hardware mechanism are necessary. A pass would be held-out evidence for this
  residual family and this first-partition scope, not global minimality.

Save the generated cuts/reasons before starting search, both exact curves,
full witnesses and cell replays, protocol hash, source revision, Python version,
runtime and peak RSS. No use of existing unrestricted held-out witnesses in
candidate generation. A topology-only coverage audit is allowed before runs;
checks on previously seen small cases are implementation regressions, not
P21d outcomes.

Run on the designated experiment server, at most four simultaneous processes,
one process per curve, 8 GiB address-space limit and 600 seconds per curve
(including witness replay). Each case has separate candidate and unrestricted
records, so one timeout cannot erase the other result. Timeout, memory failure,
missing output or simulator failure is recorded as incomplete/invalid, never
as equality. All cases remain listed; do not silently remove a slow depth.
If incomplete cases remain, distinguish the global prediction's falsification
(if a complete counterexample exists) from unfinished full-curve coverage.

# When must EH0 leave EX's group? (P21e), frozen before running

Seen before freezing: `results/p21e_explore/sweep.jsonl` (54 residual shapes,
I,K,L in {2,4,8}, depth 4, both read modes; commit `30586525`), and the
witnesses of (8,2,4) and (4,8,2) at capacities 4 to 6. Those shapes and depth
are excluded below.

**Arms.** `free`: `curve(residual(I,K,L,depth,reads_x), partitions='dp')`.
`tied`: the same with `whole_span_cuts = 2..n-1`, so the first whole-span
partition never separates EX from EH0 (P21d's structural rule without its
other exclusions). Both use corrected final-write ownership and the exact cut
DP; every frontier witness of both arms is executed.

**Derivation.** A group must loop over ranks every member uses and every
internal tensor carries. EX lacks L, so while EH0 shares EX's group, no loop
around EH0 or around {EH0, EH1} can be over L. Consider one I row. The tied
arm can only complete the h0 row (L elements) and then contract it in EH1
into the h1 row (K): about L + K resident. Separated from EX, the pair
{EH0, EH1} has legal ranks {I, L}; looping L, h0 streams element by element
while the d row and the accumulating h1 row stay resident: about 2K. Row
tiles of t rows scale both by t. So the free arm reaches each traffic level
with less capacity when 2K < L + K, i.e. L > K, and the tied arm's
minimum-traffic capacity is larger. When L < K, materializing the h0 row is
the cheaper route and is available to both arms. L = K is the tie and is
excluded. In the seen data this rule holds for 18/18 L > K and 23/24 L < K
shapes; the exception, (2,8,4) without X reads, differs at two capacities.

**Held-out cases** (depth 6, both read modes, 32 cases). L > K:
(4,4,6), (8,8,12), (4,8,12), (16,4,8), (2,4,16), (6,4,12), (16,2,8),
(4,4,16). L < K: (4,6,4), (8,12,8), (4,12,8), (16,8,4), (8,16,4), (12,8,4),
(6,12,8), (16,16,8). The first three L > K shapes have K < L < 2K and
separate the derived condition L > K from L >= 2K, which the powers of two
in the sweep cannot.

Each arm runs in a fresh process with an 8 GiB address-space limit and 1800 s
including replay. A timeout, memory failure or inexact replay makes a case
incomplete; incomplete cases count against every prediction below.

- **P21e-a.** For L > K, tied is strictly above free at one or more integer
  capacities, in at least 15 of 16 cases.
- **P21e-b.** For L < K, tied equals free at every integer capacity and on the
  constant tail, in at least 15 of 16 cases.
- **P21e-c.** For L > K, the least capacity at which tied reaches its minimum
  traffic is strictly larger than free's, in at least 15 of 16 cases; the
  minimum traffic itself is equal.
- **Diagnostic, not scored:** in L > K cases, whether a free witness at the
  smallest gap capacity contains a group with EH0 but without EX that loops
  over L.

If P21e-a fails mainly for K < L < 2K, the row model's capacity terms are
wrong and the threshold is not L > K. If P21e-b fails, materializing h0 is not
generally available to the tied arm at the needed capacities.
