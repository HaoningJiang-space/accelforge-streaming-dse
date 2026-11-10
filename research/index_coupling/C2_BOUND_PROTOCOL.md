# Offline C2 tightness and work audit, v2 only

This analysis follows the v2 validation at b69bf02e. It does not enable pruning,
change grammar or re-score any frozen P experiment. The existing v2 archive has
root/census summaries but no locally available raw call DAG. Recollect the same
unmodified v2 baseline with observers; cross-check roots against that archive
and state counts wherever an older census summary exists.

## Bound and two different questions

For a legal group loop (axis v, tile b, r trips), Lambda is the nonexternal
lacking set. Let A_K be retained bytes and D_K the parent revisit charge.
Child responses q_K and q_* = q_Lambda exclude caller reservations and compulsory
traffic. C2 is LB_K(C)=D_K+r q_*(C-A_K). Monotonicity makes it a lower bound.
For finite responses the gap is exactly r[q_K(C-A_K)-q_*(C-A_K)].

The cheap strengthened bound additionally enforces

    C >= A_K + d_K,
    d_K = max_o |access(o) minus (R union K)|.

d_K counts scalar operand/output slots, NOT full tensor sizes. Below the
threshold set the bound to infinity. Operationally clip each anchor capacity
c to max(c,d_K), then shift/multiply and Pareto-prune; do not shift every point
by d_K. Both bounds are validated against every reconstructed real candidate.

The *ideal ceiling* compares each bound to the final exact GROUP response at
the same state. That response may include the candidate itself, so the ceiling
is necessary but not jointly attainable. A solve response of the same span
cannot be used to discard alternatives from a reusable group response: their
entry contracts differ. No solve-incumbent shortcut is counted here.

The *ordered shadow* follows the actual recorded group-loop iteration order.
Before each candidate it uses only preceding, evaluated candidate frontiers.
Each axis/tile family's all-retained child is evaluated first and remains a
mandatory dependency for producing the lower bounds. Other candidates are
marked skippable only when the current incumbent dominates their entire bound.
Check that every marked candidate is already dominated and that the final
shadow envelope equals the baseline group response. This is an offline policy
simulation using saved exact responses, not an implemented search optimization.

## Call sharing and work

Observers sit outside each response LRU cache to record all parent→child queries,
and inside it to record one response and exclusive counters per miss. Preserve
the complete projected key: stage, ordered ops, extents, residency, write owner,
constraint. Every loop edge is reconstructed from changed extent and residency;
check 2^|Lambda| choices per axis/tile, full-keep first, and exact reconstruction
of the group's complete frontier. Scalar group→solve redirects are not loops.

For each shadow policy, delete only its marked loop-call edges; retain every
other edge and all bound-anchor dependencies. Recompute reachability from the
root. A shared child is removed only if it loses ALL reachable callers. Sum
exclusive DP transitions of unreachable states, not inclusive child times and
not a sum of per-edge costs. Exact unchanged response values imply other numeric
DP decisions are preserved; this is a structural projection of work, excluding
new bound-check overhead and runtime effects. Report skipped calls, unique
unreachable response states and projected DP work separately. Removed loop calls
do not imply that subset enumeration itself has been eliminated.

For each fixed loop/tile, original C2 depends on K only via (A_K,D_K). If all
lacking tensors are equal-size inputs, it has m+1 classes for 2^m choices.
These are BOUND classes, not exact state equivalences. Report their count and
whole-root M-loop profiles. The slot-strengthened bound can add d_K to its key.

## Bounded cases and accounting

Nine fresh Linux baseline workers, seed zero, at most four concurrent, 300 s and
6 GiB each, including recording and offline analysis:

- FFN forward depths 1,2,3,4 at the original tiny extents;
- attention forward depths 2,4;
- FFN training depth 1;
- FFN forward depths 1,2 with M=8,D=4,F=8.

Exact cut DP, scalar_leaf=v2, halving tiles, no name/remainder canonicalization,
no optional independent split or infeasible-group pruning; fixed graph order.
No capacity limit, no recomputation, no DMA overlap, default byte/traffic costs.
All arms preserve source hashes, graph parameters, baseline statistics, full
compressed call DAGs, per-choice analysis and result summaries. Retain failures
and timeouts rather than changing the budgets or silently excluding cases.

Primary outputs are raw/slot ideal and ordered percentages over non-anchor
choices, the same counts for axis M, bound tightness and phantom-feasibility
counts, and shared-DAG work projections. No speedup prediction or pass threshold
is frozen. Cross-check every new root with the archived v2 frontier. These
diagnostic runs do not add new executor-replay evidence or replace the 291
archived physical replays. Existing v1 work fractions are not v2 savings.

The one-layer FFN toy was inspected beforehand: for M split 2→1, no weight
retained has actual points (3,20),(4,8), raw bound (2,20),(3,16),(4,8), and
slot bound (3,16),(4,8). This is a disclosed implementation control, not a new
prediction. Five small tests check observation, clipping, entry/version and
shared-child accounting. A useful implementation decision must follow the
work-weighted result, not simply the number of candidates with a loose bound.
