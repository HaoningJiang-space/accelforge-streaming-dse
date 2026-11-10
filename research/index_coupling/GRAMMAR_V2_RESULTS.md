# Grammar v2: monotone, replayable, and different only on residual chains

Implementation `afe0e8d0` (option `scalar_leaf='v2'`, executor
`simulate(..., scalar_leaf='v2')`). Helpers were refactored in `786b7cad`, and
the check script added in `bda4783b`. Definitions and proofs are in
[GRAMMAR_V2.md](GRAMMAR_V2.md). Records are in
[results/grammar_v2/](results/grammar_v2/).

All jobs ran in fresh Linux processes with hash seed 0, the exact cut DP and
halving tiles. Each job was capped at 600 s and 6 GiB, with at most four
workers. All 48 census cases completed. v1 remains the default, and no
archived curve or frozen verdict changes.

## 1. The three checks fixed before measurement

| Check | Result |
| --- | --- |
| Every v2 root frontier point replays exactly in the cell-level executor | 291/291 |
| v2 ≤ v1 at every integer capacity | 48/48 cases, no capacity worse |
| Residency monotonicity, solve entry (23 censuses, 40,448 pairs) | v1: 239 violations; **v2: 0** |
| Residency monotonicity, group entry (≈40,500 pairs) | v1: 339 violations; **v2: 0** |

The v1 violations occur in:

- residual chains: all depths and both extents;
- forks with three or more consumers;
- FFN training.

There are none in FFN or attention forward stacks or in the ancestor control.
The keep bound Q(C) ≤ Q'(C − |W|) still fails at group entries in both
grammars, as GRAMMAR_V2.md §1 states: a group must loop, so it cannot hold W
whole. It holds at every solve entry in v2.

## 2. Where v2 changes the curve

19 of 48 root curves change. Every residual chain and fork4_kkk is among them.
No FFN or attention stack, no fork at extent two and no ancestor control
changes.

| Case | v1 → v2 |
| --- | --- |
| residual depth 4, independent input | Q(4): 56 → 52 |
| residual depth 4, reads X | Q(4): 52 → 48; **minimum-traffic plateau 13 → 11** (24 B) |
| residual depth 24, reads X | Q(4): 132 → 128; plateau 13 → 11 |
| residual (4,4,8) depth 8 | Q(4), Q(7), Q(8), Q(11), Q(12) lower |
| fork4_kkk | new point (5, 416) |

The new points come from all-scalar sub-spans of the residual H chain that v1
had to hold whole. With X read by EH0, v2 reaches the minimum traffic with
2 B less capacity at every tested depth.

v2 costs 1.3-1.4× v1's search time on the largest cases (same6/mixed6 and
residual depth 16/24).

## 3. What this changes

1. **Dominance arguments over residency contexts are now valid in v2.** The
   lower-bound prune for retention choices (GRAMMAR_V2.md §5, C2) can be
   implemented and measured.
2. **Some v1 conclusions about residual chains are grammar-dependent.**
   - The P21 family used residual chains.
   - P21e/P21f plateau comparisons were scored in v1.
   - Their verdicts stand as v1 statements.

   Under v2, residual plateaus with X reads move by 2 B. This report does not
   test whether the free/tied plateau gaps change; any re-scoring would be a
   new, separately frozen experiment.
3. **Stacks and small forks are unaffected at the root.** Their v1 internal
   states still violate monotonicity (FFN training, forks), but the root
   optimum does not depend on those states.
