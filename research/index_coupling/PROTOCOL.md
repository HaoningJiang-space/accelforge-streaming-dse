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
