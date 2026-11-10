# C2 is valid, but its useful work coverage is limited

The v2 all-resident lower bound is too optimistic to be the main stack-scaling
mechanism on the cases measured here. Its validity is not the problem. It drops
the inner cost of absent residency, and many calls it can discard still lead
to responses needed elsewhere. A scalar operand-slot bound fixes false
feasibility without fixing either problem.

This is the offline analysis requested after the v2 checks. No online pruning
was implemented, no solver default changed, and no frozen P experiment was
re-scored. The [protocol](C2_BOUND_PROTOCOL.md) and collector were committed at
`c6544a77` before nine bounded server runs. All nine completed. The post-hoc
shared-target counts and simultaneous-deletion ceilings below use those same
archived call DAGs; they are not additional predictions or experiments.

## 1. What the bound forgets

Fix one legal group loop, its tile and r iterations. Lambda is the set of
nonexternal tensors lacking that loop rank; K is its retained subset. Write

    A_K = sum_{t in K} |t|
    D_K = (r-1) sum_{t in Lambda\K} rho_t |t|,
    rho_t = 1 for inputs, 2 for accumulated outputs.

At free child capacity c, let q_K(c) be its internal extra traffic and let
q_*(c)=q_Lambda(c). The caller's external reservation and compulsory traffic
are outside these responses. The real candidate and C2 bound are

    P_K(C)  = D_K + r q_K(C-A_K),
    LB_K(C) = D_K + r q_*(C-A_K).

v2 residency monotonicity gives LB_K <= P_K. Where both responses are finite,

    P_K(C)-LB_K(C) = r [q_K(C-A_K)-q_*(C-A_K)].

D_K correctly charges revisits across this loop. It does not recover the
child's cost of keeping missing weights or partial sums live while it executes
its own partitions and loops. The gap is a conditional child-response gap,
not an error in the parent read/write coefficient.

For fixed tile, C2 sees K only through (A_K,D_K). With m equal-size input
weights there are m+1 bound classes for 2^m subsets. This is not an equivalence
of exact states in the fixed-order grammar. Also, the full-keep candidate alone
cannot dominate a proper subset's raw bound on the whole capacity domain:
the latter starts at a strictly smaller reservation plus the same anchor
minimum. Other evaluated candidates are needed to make pruning possible.

The inexpensive strengthening uses

    d_K = max_o |access(o) minus (R union K)|,
    LB_slots(C) = infinity when C < A_K+d_K, else LB_K(C).

Each nonexternal operand/output needs at least one scalar slot when its
operator executes. d_K counts these slots, not full tensor sizes. On a Pareto
list this clips each child capacity c to max(c,d_K); it does not add d_K to
every capacity. All 38,622 non-anchor choices satisfy
LB_raw <= LB_slots <= P_K in the archived responses.

## 2. A concrete failure at the most relevant M loop

In the four-layer tiny FFN, all extents are 2. The whole-graph group can loop
over M, reducing 2 to 1. Its eight lacking weights have size 4 each. The
all-resident child has internal extra-traffic points

    q_* = [(2,36), (3,20), (4,0)].

For k kept weights, A_K=4k and D_K=32-4k. Thus the raw bound has points

    (4k+2,104-4k), (4k+3,72-4k), (4k+4,32-4k).

For every proper subset d_K=3. Slot clipping removes the first point but leaves
the optimistic zero-extra-child endpoint at free capacity 4 untouched.
The saved child responses show why that endpoint matters:

| Kept weights k | Subsets | True child zero-extra capacity | Ideal exclusions, raw / slots | Ordered exclusions, raw / slots |
|---|---:|---|---:|---:|
| 0–5 | 219 | 5 in every case | 0 / 0 | 0 / 0 |
| 6 | 28 | 5 for 27; 4 for 1 | 28 / 28 | 6 / 6 |
| 7 | 8 | 5 for 6; 4 for 2 | 8 / 8 | 6 / 6 |
| 8 | 1 | 4 | required anchor | required anchor |

The proper subsets with plateau capacity 4 omit only W1_0, only W2_3, or both:
the first and last matrix weights. Equal kept counts therefore do not determine
the true child plateau, even though they determine the raw bound.

For k=0, at parent capacity 4 the lower bound claims traffic 32; the final exact
group response is 56. For k=1,...,5, at capacity 4k+4 it is 36-4k, still larger
than the bound's 32-4k. These are internal extra-traffic values, not whole-root
DRAM totals. One optimistic plateau breakpoint is enough to prevent full-curve
dominance. Even an oracle supplying the final group response can discard only
36/255 proper subsets; the recorded traversal can discard 12/255. Changing
candidate order alone cannot make C2 eliminate the other 219 choices.

The one-layer control illustrates a second gap. With no weight retained the
actual points are [(3,20),(4,8)], versus raw [(2,20),(3,16),(4,8)] and slot
[(3,16),(4,8)]. Fixing the infeasible capacity 2 still leaves a traffic gap at 3.

## 3. Count candidates and saved work separately

An **ideal exclusion** uses the final exact group frontier as incumbent. It
may depend on the very candidate being tested. An **ordered exclusion** uses
only candidates preceding it in the captured baseline traversal, always
evaluating each axis/tile family's full-keep anchor first. Every ordered
shadow group envelope equals its unpruned baseline envelope. A solve frontier
cannot substitute for the group frontier: their entry contracts differ.

All candidate counts below exclude required anchors. Default dimensions are
the tiny census dimensions; the final two cases use M=8,D=4,F=8. Percentages
of DP work sum exclusive counters only on states made unreachable from the
root after marked loop edges are removed. Shared children are counted once
and disappear only when no reachable caller needs them.

| Case | Proper choices | Ideal exclusions raw / slots | Ordered exclusions raw / slots | Projected DP work saved raw / slots |
|---|---:|---:|---:|---:|
| FFN forward, 1 layer | 118 | 21 / 105 | 4 / 36 | 9.67% / 13.20% |
| FFN forward, 2 layers | 446 | 146 / 372 | 31 / 121 | 11.02% / 11.59% |
| FFN forward, 3 layers | 1,414 | 687 / 1,055 | 235 / 392 | 22.58% / 22.68% |
| FFN forward, 4 layers | 5,050 | 2,355 / 2,865 | 1,064 / 1,277 | 20.29% / 20.31% |
| Attention forward, 2 layers | 446 | 146 / 372 | 30 / 118 | 11.02% / 11.59% |
| Attention forward, 4 layers | 5,050 | 2,355 / 2,865 | 1,061 / 1,265 | 20.29% / 20.31% |
| FFN training, 1 layer | 16,533 | 8,582 / 11,360 | 3,024 / 4,027 | 5.41% / 6.04% |
| FFN forward, 1 layer, M8 | 2,388 | 302 / 1,383 | 225 / 1,028 | 0.00% / 0.03% |
| FFN forward, 2 layers, M8 | 7,177 | 1,394 / 3,955 | 1,113 / 3,059 | 0.34% / 0.48% |

Two examples show why the last column matters:

- Four-layer FFN: slot clipping adds 213 ordered exclusions, but saves only
  86 additional DP transitions, from 120,350 to 120,436 out of 593,020. Many
  added exclusions remove inexpensive states. The ordinary bound already
  removes most of the expensive work that this policy can reach.
- Two-layer M8 FFN: slots discard 3,059/7,177 choices (42.62%), yet only 48
  of 6,176 response states become unreachable. Among the 1,280 distinct direct
  targets of skipped calls from still-reachable parents, 1,242 remain reachable
  by other calls. Only 106/22,124 DP transitions disappear (0.48%).

These are projected counter reductions, not measured acceleration. They omit
new bound-check overhead and savings from avoiding lookups, transformations or
merges in retained parents. Baseline workers ran concurrently with observers;
their times cannot establish an optimized/unoptimized speed ratio. Neither
policy removes the outer enumeration of all retention subsets.

Post-hoc, remove **all** ideal-eligible edges simultaneously to get a ceiling
on eliminated-state DP work for this bound and mandatory-anchor interface.
This can remove mutually supporting candidates and need not preserve any
frontier; it is not an implementable policy. Any safe set of such edge deletions
is a subset, so its eliminated-state work cannot exceed this ceiling.

| Case | Ordered DP saving raw / slots | Ideal simultaneous DP ceiling raw / slots |
|---|---:|---:|
| FFN forward, 4 layers | 20.29% / 20.31% | 40.44% / 40.61% |
| FFN training, 1 layer | 5.41% / 6.04% | 19.18% / 24.26% |
| FFN forward, 1 layer, M8 | 0.00% / 0.03% | 4.83% / 8.86% |
| FFN forward, 2 layers, M8 | 0.34% / 0.48% | 2.08% / 3.98% |

There is some ordering headroom on tiny stacks, but this does not rescue the
larger-extent examples. These ceilings do not constrain other bounds, capacity-
specific queries, changed interfaces, or different execution grammars.

## 4. Validation and limits

- 9/9 roots equal their existing v2 archive exactly. All six available old
  census state counts also match. The other three had no old census summary.
- All group loop actions and their 2^|Lambda| families are reconstructed;
  all actual group envelopes and both ordered shadow envelopes match.
- The raw bound starts below the candidate's minimum feasible capacity in
  27,725/38,622 choices. Slots remove all these observed feasibility mismatches.
  Full-curve equality improves from 6,172 to 15,098 choices; the remaining
  23,524 still have a traffic/plateau gap. This is observed coverage, not a
  proof that the slot bound always gives exact feasibility in arbitrary DAGs.
- Every raw artifact/source digest is verified. All nine analyses reproduce
  from archived DAGs. Exclusive counters sum to the original baseline totals.
- Five focused tests pass. These diagnostic runs use numeric responses and
  add **no** physical executor replays to the earlier 291 v2 checks.

The fixed-order, serial, halving-tile, v2 grammar and its pinned external
reservations remain essential. No order-complete quotient, DMA overlap,
recomputation, or production-size scaling claim is tested. The older v1
observation that 99.5% of work was in nontrivial states is not a percentage
that C2 can prune.

## 5. Research decision

Do not implement C2 as the proposed solution to stack growth on this evidence.
It can remain a valid optional tool, but counting excluded masks alone would
overstate its value. The cheap slot correction is useful for feasibility and
has negligible incremental DP coverage on the deeper tested stacks.

The next theoretical target is a lower bound that retains some of the child's
capacity/traffic conflict after external residency is relaxed. The four-layer
example isolates a concrete requirement: explain when zero extra traffic needs
free capacity 5 instead of 4, including the exceptional first/last positions.
A certified zero-extra threshold could tighten the plateau endpoint, but would
not by itself bound all positive-traffic points. Derive such a bound from the
declared lifetime/partition contract before adding another search rule. Any
candidate should face this same shared-DAG work accounting before online use.

## Artifacts and reproduction

Raw baselines, decision records and run/source hashes:
[results/c2_bound](results/c2_bound/manifest.json). Full summary including all
post-hoc ceilings and root M-loop profiles:
[summary.json](results/c2_bound/summary.json).

```sh
PYTHONHASHSEED=0 python3 -m unittest research.index_coupling.test_c2_bound_audit
python3 -m research.index_coupling.summarize_c2_bound_audit \
  --data research/index_coupling/results/c2_bound \
  --out /tmp/c2-summary.json
```

The summarizer checks the historical source and root/census archives at the
recorded revision, current collector-source equality, artifact hashes, and
complete re-analysis equality. It never invokes a solver. To recollect the
bounded baseline, use `run_c2_bound_audit` at `c6544a77` with a fresh output
directory on Linux, as specified by the protocol. The post-hoc summarizer has
its own source digest in summary.json; it does not alter the original run record.
