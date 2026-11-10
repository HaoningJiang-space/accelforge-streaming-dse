# P21e: EH0 must leave EX's group — existence confirmed, threshold corrected

Frozen in `e67f8756` (PROTOCOL.md, P21e) before any held-out run; runner and
scorer `d49dca61`; records and scores in `results/p21e/` (`30daae4e`).
All 64 arms completed under 8 GiB / 1800 s per process; every frontier witness
of both arms executed exactly.

| Prediction | Result | Verdict |
| --- | --- | --- |
| P21e-a: L > K ⇒ tied strictly above free somewhere | 16/16 | **pass** |
| P21e-b: L < K ⇒ tied equals free everywhere | 13/16 | **fail** (needed 15) |
| P21e-c: L > K ⇒ tied's minimum-traffic capacity is larger | 13/16 | **fail** (needed 15) |

Unscored diagnostic: in 16/16 L > K cases the free witness at the smallest gap
capacity contains a group with EH0, without EX, that loops over L — the
mechanism the derivation names.

## Where the failures are

**P21e-c** fails in exactly the three K < L < 2K shapes without X reads:
(4,4,6), (8,8,12), (4,8,12). With X reads the same shapes pass. Both arms in
(4,4,6) without X reads reach minimum traffic at capacity 49 by keeping H0
(24) and X (16) whole; with X reads, free reaches it at 37 by fusing EH0 and
EH1 and keeping H1 instead of H0.

**P21e-b** fails in three K = 12 cases: (4,12,8) without X reads (8
capacities) and (6,12,8) in both modes (4 and 1). Their minimum-traffic
capacities are equal; the differences are at intermediate capacities. Not yet
explained.

## Post-hoc correction of the row model (not a pass)

The frozen derivation omitted the d row from the free route's residency.
Fusing EH0 and EH1 under an L loop reuses one row of EH0's I×K input across
all L steps, so that row must stay resident:

- If EH0 reads X, its row is X's row, which is resident anyway until the
  final join. The free route adds the h1 row (K); the tied route the h0 row
  (L). Threshold: **L > K**.
- If EH0 reads a separate D, the free route adds the d row and the h1 row
  (2K) against L. Threshold: **L > 2K**.

This matches all 16 held-out L > K plateau outcomes, including the three
K < L < 2K shapes the protocol included to separate L > K from L ≥ 2K. It is
the residency value V_X of P21 (FIRST_PRINCIPLES.md §10) appearing as a
threshold shift: when H reads X, X's residency pays for part of the fused
route. The streaming regime at low capacity still favours free whenever
L > K (P21e-a, 16/16), so existence and plateau have different thresholds.

The corrected thresholds were fitted to these results and must be tested on
new shapes before they are claimed. P21e remains failed as frozen.
