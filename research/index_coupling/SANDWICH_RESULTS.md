# Sandwich certificate: results

Protocol: [SANDWICH_PROTOCOL.md](SANDWICH_PROTOCOL.md), frozen in `699815bb`
before measurement. Code: `sandwich.py`. Records:
`results/contraction_oracle/sandwich.jsonl`.

## Validity and coverage

| Case | Qualifying | M > 1 | Certified | Certified, M > 1 | LB / UB violations | Certified but inexact |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| FFN 1 layer | 140 | 39 | 103 | 23 | 0 / 0 | 0 |
| FFN 2 layers | 519 | 96 | 274 | 55 | 0 / 0 | 0 |
| FFN 3 layers | 1,574 | 153 | 445 | 87 | 0 / 0 | 0 |
| FFN 4 layers | 5,333 | 210 | 616 | 119 | 0 / 0 | 0 |
| attention 2 / 4 layers | as FFN 2 / 4 | | | | 0 / 0 | 0 |
| FFN M8 1 layer | 1,085 | 772 | 708 | 486 | 0 / 0 | 0 |
| FFN M8 2 layers | 3,144 | 2,211 | 1,669 | 1,128 | 0 / 0 | 0 |

- LB <= actual <= UB holds at every capacity of every qualifying state. That
  includes the assumption that the keep-level model prices single-op groups
  at every residency used.
- Every certified state equals its archived curve. 63% and 51% of the M8
  states with M > 1 are certified.

## Work (shared-DAG reachability, as §15)

Fractions of exclusive counters removed when the listed states are terminal.
Each cell gives unit-M only / certified only / union.

| Case | DP transitions | Loop choices | Pareto candidates | Merge inputs |
| --- | --- | --- | --- | --- |
| FFN 1 layer | 76.2 / 58.0 / 79.9 | 38.9 / 27.1 / 52.9 | 59.4 / 37.0 / 65.5 | 69.1 / 47.3 / 73.2 |
| FFN 2 layers | 93.5 / 15.7 / 94.3 | 33.3 / 15.0 / 39.3 | 86.1 / 9.3 / 87.3 | 91.6 / 11.1 / 92.4 |
| FFN 3 layers | 99.0 / 2.2 / 99.1 | 22.0 / 8.7 / 25.2 | 96.1 / 1.6 / 96.3 | 98.6 / 1.5 / 98.7 |
| FFN 4 layers | 99.8 / 0.3 / 99.9 | 10.7 / 4.0 / 12.0 | 98.5 / 0.3 / 98.5 | 99.7 / 0.2 / 99.8 |
| FFN M8 1 layer | 29.4 / 22.2 / **40.7** | 15.9 / 40.7 / **50.0** | 17.3 / 20.0 / 32.8 | 23.0 / 16.8 / 33.2 |
| FFN M8 2 layers | 31.6 / 9.3 / **36.0** | 13.9 / 27.3 / **36.6** | 16.5 / 5.9 / 20.9 | 22.5 / 4.8 / 25.2 |

## Decision (frozen rule)

**The stop condition holds.** Beyond the unit-M closed forms, the union adds
11.3 and 4.4 points of DP transitions in the M8 cases, below the frozen 20.
No online version is built.

The loop-choice counter does improve substantially, from 15.9 to 50.0 and
from 13.9 to 36.6. This was not the frozen criterion and does not change the
decision. It does show that certified M > 1 states carry much of the
loop-retention enumeration.

## Where the certificate fails

Uncertified M > 1 states:

| Case | UB gap only | LB gap only | Both |
| --- | ---: | ---: | ---: |
| FFN M8 1 layer | 118 | 35 | 133 |
| FFN M8 2 layers | 375 | 79 | 629 |

**The upper bound is the weak side.** In 89% and 93% of failures, the
singleton partition is not optimal: the optimum fuses operators, so that an
intermediate is held as a tile instead of whole or round-tripped through
DRAM. The bound side fails alone in only 7-12%.

An upper bound built from §8-10's fused segment forms, generalised to M > 1,
would target the dominant failure. Its single-op atom (§12) is verified, but
the M > 1 fused forms are the full loop-order problem (§12). That is the
open question, not a further bound.
