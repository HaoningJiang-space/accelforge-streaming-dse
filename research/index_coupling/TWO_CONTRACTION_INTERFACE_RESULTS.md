# Conditional two-contraction responses: all frozen interfaces match

The complete solve response and the distinct group response derived in
[TWO_CONTRACTION_INTERFACES.md](TWO_CONTRACTION_INTERFACES.md) match every frozen
case. The conditional contract includes whole input/output residency in addition
to resident weights. This fills a direct interface-validation gap in the
already-derived root formula and chain DP; it is not a new claim of root-formula
novelty or general-DAG composability.

The protocol, pure predictor and 4,000 predictions were committed and pushed at
`5b2b6169` before any reference computation in this study. The predictor imports
neither the solver nor executor. The checker verifies frozen source/prediction
hashes, uses unchanged v2 literal partition enumeration, separately compares
cut DP, and replays each finite frontier point in an explicit caller frame.

## Frozen results

| Entry | Full frontiers equal | Capacity points equal | Positive traffic | Zero traffic | Infeasible | Exact framed executions |
|---|---:|---:|---:|---:|---:|---:|
| solve | 104/104 | 2,000/2,000 | 288 | 1,530 | 182 | 294/294 |
| group | 104/104 | 2,000/2,000 | 390 | 1,356 | 254 | 277/277 |
| Total | **208/208** | **4,000/4,000** | **678** | **2,886** | **436** | **571/571** |

Each tile domain has 104 cases and 2,000 matching points. Each residency context
(neither endpoint, input only, output only, both) has 52 cases and 1,000 matching
points. Both-resident cases have no positive traffic; they test the correct
one-cell intermediary requirement and the caller-reservation convention.
Literal partition enumeration and DP match in all 208 cases. All cases complete
within the frozen 30-second per-case budget; there are no errors or timeouts.

The finite capacity range covers every plateau, and the full breakpoint lists
also match. Hence equality is over the complete integer-capacity response,
including infeasibility, rather than only a few sampled feasible points.
Most comparisons are zero-traffic checks; the 678 positive points are reported
separately so they are not obscured by the headline total.

The frame pins the declared external tensors in real cells, runs the child
twice under a legal parent loop, and drains the retained tensors through real
consumers. Frame traffic is its compulsory transfers plus twice the child's
extra traffic. These are 571 executions, not a claim of 571 distinct physical
algorithms. No timing/energy simulation or search-speedup measurement is made.

## What the conditional formula adds

For input-resident/output-free states, the formula is

    G_10(C) = min(2b + f(b,c;C),
                  min_{u in R(b),u+1<=C} 2c(b/u-1),
                  0 if C>=c+1).

The first choice materializes h; the second retains an h tile and spills output
partial sums; the third holds the complete output. The output-resident case
has the corresponding input-refetch coefficient a. With both endpoints
resident, one scalar h cell suffices. Caller reservations remain outside C.

Across positive solve-entry points, materializing h is the unique winner at
57 points with neither endpoint resident and 32 input-resident points. It is
not uniquely selected in the output-resident stratum of this frozen shape set.
A separately labelled post-freeze control addresses that coverage limitation:
a=6,b=7,c=3, output resident, C=4 gives 28 extra transfers by materializing h,
versus 36 for the best retained-h family. It agrees with literal enumeration;
it is not counted among the 4,000 prospective comparisons.

## Entry contracts are not interchangeable

Of 104 matched shape/context/domain pairs, **50 have different solve and group
frontiers**. The difference comes from whether a root operator partition is
available and whether v2's scalar-group redirect applies.

- For (a,b,c)=(8,2,8), neither endpoint resident and C=3, solve has Q_extra=0
  by keeping all h. Group must begin with its common-j loop and has Q_extra=24.
- For b=1 with a nonscalar nonresident endpoint, group has no legal active
  common loop and stays infeasible. Solve is still feasible. Six frozen group
  cases have this entirely empty response.
- For (a,b,c)=(1,1,1), the v2 scalar redirect permits partitioning and gives
  zero extra traffic at C=2. The mandatory v1 whole-span scalar leaf differs.

A group may also need **materialization inside its first loop**. For (2,15,7),
halving tiles, C=2, the exact group extra traffic is 204. A first j tile of 3
has five trips: the outer charge is (2+2*7)*(5-1)=64; the inner solve materializes
its three h cells and costs 6+f(2,3;2)+f(3,7;2)=28. Total 64+5*28=204.
Retaining a scalar h tile without that materialization costs 224. The whole
solve can materialize h at the root and achieves 148 instead. All three numbers
are extra traffic, excluding compulsory endpoint transfers and external weights.

Therefore a set of fused/retained-h candidates, a complete solve response, and
a reusable group response are three different objects. The existing chain DP
can represent a pair's omitted root-materialization alternative by splitting
at its middle boundary. That does not make its pair-candidate function an exact
replacement for the group cache.

## Proof boundary and implementation decision

The normal-form argument separates two cases. Repeated common-rank loops with
retained h tiles collapse by telescoping repeated-read/spill charges. If h is
materialized, project onto the two single-contraction executions and compare
with the root materialization candidate. Treating the latter as if endpoint
reservations could always be hoisted would miss a capacity constraint.

The study establishes the specified conditional two-contraction response under
v2. It does not cover nonresident weights, elementwise activations/copies,
multi-consumer intermediates, resident internal h, caller-owned h writes,
reordered operators, overlap or a different spill cost. In particular, inserting
an out-of-place activation between the contractions changes the live tensors;
it cannot be silently removed to apply this formula to an FFN.

No production solver rule is installed. An eventual exact replacement must
recognize this incidence and boundary contract, dispatch solve and group
separately, and supply a representable witness. The current formula evaluator
returns numeric responses; archived witnesses come from the reference solver.
Its impact on search work would still require shared-call-DAG accounting.

## Artifacts

- Frozen [predictions.json](results/two_contraction_interfaces/predictions.json)
  records the predictor/protocol/core hashes and base revision.
- [run.json](results/two_contraction_interfaces/check/run.json) records source
  hashes, budgets, all case statuses, exact comparisons and strata.
- [cases.jsonl](results/two_contraction_interfaces/check/cases.jsonl) preserves
  all reference frontiers, witnesses, framed replay counts and execution results.
- Four post-freeze regression tests cover the entry distinction, empty/scalar
  groups, materialization under each one-sided contract and nested materialization.

```sh
PYTHONHASHSEED=0 python3 -m unittest research.index_coupling.test_two_contraction_interfaces
PYTHONHASHSEED=0 python3 -m research.index_coupling.check_two_contraction_interfaces \
  --predictions research/index_coupling/results/two_contraction_interfaces/predictions.json \
  --out NEW_CHECK_DIRECTORY
```
