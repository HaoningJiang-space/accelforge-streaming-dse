# Decision-hypergraph decomposition: initial feasibility gate

The target is **Graph-Structured Architecture–Mapping Co-Optimization**, not a
new FFM cache or a rename of Compatibility. This audit separates three graphs:

| Representation | Meaning here |
| --- | --- |
| Computation graph | Actual tensor uses and producer/consumer dependencies |
| AND/OR search graph | Alternative templates/implementations, with simultaneous requirements inside each implementation |
| Decision hypergraph | Variables appearing in the same domain, feasibility, cost or policy dependency |

Alternative templates are **OR choices**. The audit does not conjoin all their
tile constraints into one fictitious simultaneous program. Each real symbolic
template program is inspected separately; a coarse joint mapping-selector model
is also shown, with unresolved whole-prefix resource transfer explicitly opaque.
Effective Fusion interfaces also depend on instantiated tiles: unit loops can
disappear and Reservation indices can shift. A raw template therefore does not
receive a single fixed layout/interface label in this experiment. The symbolic
incidence extraction is not a complete producer–consumer interface factor.

## What was executed

Real 2mm/3mm chains, M=16 and KN=16, on NVDLA 16×16 with 4 KiB GlobalBuffer,
normal RU/E/L search, zero Pareto tolerance and conservative Fusion filtering:

1. Observe the existing pre-Tile enumeration entry point without changing its
   arguments or returned arrays. Extract actual Tile symbols, domain relations,
   objective expression scopes and ordered fallback flags.
2. Annotate the relevant hardware axes: Px/Py for spatial usage, C for GB
   capacity and a conservative B dependency for total latency. This is an
   incidence model, not newly derived symbolic hardware cost functions.
3. Measure primal induced widths for native, reverse and min-fill orders, with
   architecture retained, conditioned, or removed first. No alternate Tile
   enumeration program is executed.
4. Prepare one fixed candidate catalog. Compare ordinary FFM with an observed
   start/advance/finalize path, preserving its operator order, reservations and
   Pareto sequence. Verify all numeric frontier columns and Mapping identities.
5. Inside each actual numeric Join, audit only the conjunction of its already
   prepared equality predicates. Natural, reversed and selectivity-first key
   orders construct factorized row-index blocks. Verify exact pair lineage
   against an independent Pandas index Join, then let the unmodified numeric
   Join run. All final mappings are reconstructed and re-evaluated.

The index oracle deliberately expands pairs for verification. That audit work
is counted separately and is not claimed as avoided search. Over-budget or
mixed-type/null-key cases are marked unknown and retain the native path.

## Results

| Metric | 2mm | 3mm |
| --- | ---: | ---: |
| Inspected symbolic template programs | 24 | 42 |
| Actual numeric group Joins | 4 | 18 |
| Native matched pair rows materialized | 110 | 697 |
| Largest single pair frame | 54 | 270 |
| Peak active frontier at observed stage boundaries | 30 | 185 |
| Factorized leaf index occurrences, natural key order | 60 | 343 |

All 4/18 numeric Joins are within the verification budget and checked. Every
tested key order preserves its exact pair set. The full observed FFM frontier
and Mapping identities are unchanged. Factorized index occurrences are not full
candidate rows or total memory: input payloads, costs and resources still exist.
The existing FFM streaming key-plan machinery already exploits grouped index
blocks; this is not a new factorization primitive.

Index construction totals for natural/reverse/selectivity-first ordering are
216/216/216 (2mm) and 1374/1368/1380 (3mm). The heuristic order is slightly worse
on the latter, and **no order avoids any native numeric candidate evaluation**.
Native Pandas multi-key Join already avoids combinations failing any equality.
Comparing only against a naive full Cartesian expansion would inflate the gain.

For both workloads, hard-constraint scopes give min-fill widths 3–5 with hardware
variables retained, or 2–4 after conditioning them. Including atomic cost
expression scopes gives 5–6 with hardware retained. Native-order hard widths are
4–6. These are descriptions of the chosen representation, not execution gains.

Adding a conservative whole-program cohort/Pareto-history dependency gives
widths 7–9 and removes the min-fill advantage in this representation. This does
**not** prove intrinsic high width or the impossibility of a better decomposition:
the barrier is deliberately conservative, and splitting expression DAGs through
auxiliary variables or proving weaker policy dependence could change it. None
of those decompositions has been proved or executed here.

The reported widths are **primal induced widths**, including the retained output
boundary. They are not fractional FAQ-width, generalized hypertree width, exact
treewidth minima, or an exponential runtime prediction. A smaller syntactic
width does not license a different FFM search order or guarantee small factor
domains.

## DPhyp and legal search order

The repository's 3mm is A→B→C, not two independent producers merging at C. Its
operator skeleton has seven nonempty subsets, six connected subsets and four
unordered connected disjoint pair partitions. Native reference-order FFM uses
two operator transitions, without enumerating arbitrary subset combinations.
Consequently, the computation-level count does not identify additional native
work that DPhyp-style connectivity filtering would avoid.

This small topology diagnostic is **not a DPhyp implementation**. No arbitrary
FFM binary join tree was evaluated. Directional Compatibility, remaining-tensor
liveness, resource release, permutations and cost aggregation must first be
shown equivalent for any proposed alternative tree.

The relevant DB distinction is that [DPhyp's paper](https://15721.courses.cs.cmu.edu/spring2019/papers/23-optimizer2/p539-moerkotte.pdf)
uses connected subgraph/complement structure to avoid invalid plan combinations,
while preserving operator restrictions. The inspected
[DuckDB enumerator](https://github.com/duckdb/duckdb/blob/dc325b7f318132e57768ac3be437065c1bef4664/src/optimizer/join_order/plan_enumerator.cpp)
also has applicability checks and an exact-to-approximate fallback. Neither
provides a proof that tensor Fusion joins can be arbitrarily reordered.

[FAQ/InsideOut](https://arxiv.org/pdf/1504.04044) makes legal aggregate/variable
ordering part of its formal problem; hypergraph width alone is insufficient.
FFM's ordered fallback and prefix Pareto have not been established as the
required commutative aggregation. That is why the audit reorders only completed
equality tests and labels the remaining policies opaque.

## Decision gate

| Proposed comparison | Current evidence |
| --- | --- |
| Native FFM | Real group, pair-frame and active-frontier work measured |
| DPhyp-style full Fusion composition | Not implemented; computational connectivity alone identifies no extra work to avoid |
| Alternate Tile/Mapping variable elimination | Widths inspected, not executed: semantic equivalence unproved |
| Factorized prepared interfaces | Exact equality lineage verified; index representation smaller, zero numeric evaluations avoided |
| Full architecture–mapping factor solver | Not implemented; cost/resource/policy factorization remains open |

This gate supplies no new joint-search speedup. It also does not establish that
all decision-graph approaches fail. A further implementation is justified only
by a concrete decomposition that preserves the coupled physical semantics and
avoids work **beyond existing** FFM grouping/Pareto and parametric/cache baselines.
Do not add another generic Memo or reorder operators based solely on this graph.

The follow-up [conditional-elimination experiment](CONDITIONAL_ELIMINATION.md)
tests one missing local aggregation law using native terminal resource response
functions. It reduces pairs in three 3mm cases without changing operator order;
it does not change this audit's zero-reduction equality-order result or establish
full InsideOut factorization/width bounds.

## Reproduce and raw data

```sh
python -m research.graph_coopt.decision_hypergraph_audit --n 2 --output research/graph_coopt/results/decision_hypergraph/2mm.json
python -m research.graph_coopt.decision_hypergraph_audit --n 3 --output research/graph_coopt/results/decision_hypergraph/3mm.json
python -m pytest -q research/graph_coopt/test_architecture_mapping_coupling.py research/graph_coopt/test_decision_hypergraph.py --disable-warnings
```

JSON files preserve every inspected scope, explicit elimination bag/order,
opaque barrier and numeric equality audit. The full research regression log is
saved alongside them. No cycle-accurate lifetime, calibrated area, or full
Mapspace optimality claim follows from model re-evaluation.

The shared declared regression (`research/tracking_audit`,
`research/streaming_join`, `research/graph_coopt`) passed **650 tests**, including
14 new tests; the targeted run passed those 14. These counts overlap and must
not be added. The known legacy `compatibility_util` collection issue is outside
the declared suite, which is not an all-repository regression.
