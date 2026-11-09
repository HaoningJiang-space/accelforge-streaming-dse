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
