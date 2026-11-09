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
