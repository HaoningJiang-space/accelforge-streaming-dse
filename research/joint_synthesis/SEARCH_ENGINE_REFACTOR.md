# Search-control refactor: fixed problem, fixed execution semantics

Base: `c0f62874c9f2dba506df43ae5a2e67cd969f9998`. This change was implemented locally
from the repository because no external patch/archive was supplied. It is an
engineering separation of responsibilities, not another proposed search method.
The research question stays Graph-Structured Architecture–Mapping Co-Optimization;
no algorithm is selected on the strength of this refactor.

## Responsibilities

| Layer | Responsibility |
| --- | --- |
| `graph_dp.solve()` | Preserve the existing public signature and result/statistics format |
| `SearchPolicy` | Explicit direct/spill grammar, local/layout pruning and order seed |
| `StageCatalog` | Validate stage candidates, summarize using the existing backend, group by required/delivered Property and retain the same local frontiers |
| `TwoMMSearch` | Coordinate catalogs, enforcers, existing layout witnesses and incremental root Pareto; count every actual composition |
| `resource_demand` / `composition` | Existing physical costs, conversion legality and materialized-boundary resource rules |
| `architecture_synth` | Existing global hardware binding after graph search |
| independent execution Oracles | Unchanged scalar execution, allocations, values and hardware-grid validation |

The root frontier now consumes completions incrementally instead of retaining a
list of all complete candidates. Every original candidate is still composed in
the original order. `materialized_complete_pairs`, dominance statistics, returned
plan identities and witness resolution have the same meaning and values. There
is no new pruning, plan coverage, or measured research speedup claim.

A `candidate_provider(graph, requirements)` can supply the two finite stage
iterables to `TwoMMSearch`. Catalogs own those choices for one solve. The engine
validates the graph stage and explicit endpoint requirements, so a provider
cannot silently ignore a requested physical property. The default provider is
the unchanged `schedule_rules.generate`. A custom provider is responsible for
its declared candidate coverage; injection does not prove completeness of a
new enumeration scheme or authorize a wider execution grammar.

```python
from research.joint_synthesis.search_engine import SearchPolicy, TwoMMSearch
from research.joint_synthesis.graph_ir import TwoMM, CostModel
from research.joint_synthesis.schedule_rules import generate

engine = TwoMMSearch(TwoMM(), CostModel(), SearchPolicy(order_seed=7),
                     candidate_provider=generate)
frontier, stats = engine.solve()
```

## Pareto schema guard

One frontier now binds a concrete state class and objective-vector dimension.
A six-dimensional `KernelDemand` describes workspace; a six-dimensional `Demand`
describes complete peak. Mixing them raises `TypeError`. Different dimensions or
empty vectors raise `ValueError`, so `zip` cannot silently truncate objectives.
The same validation applies to conditioned catalogs, unpruned controls, direct
comparisons and final witness resolution. Existing homogeneous custom numerical
state classes remain supported.

This guard does not prove future substitutability or supply a complete physical
type system. The current full-Property grouping and physical composition rules
still establish the restricted 2mm contract. The fused 3mm study has different
lifetime/interface semantics and remains separate. No FFM implementation,
Candidate Generator, cost coefficient, Oracle, or architecture-binding code is
changed.

## Validation plan and scope

The new tests contain exact frozen copies of both baseline control routines,
verified against these Git blob IDs:

- `graph_dp.py`: `bc640aaa618ce47bf612b6227a5abea083260b62`
- `conditional_frontier.py`: `c69bb34d6f3a714ff5e7cb0de981d0fca1ac3770`

They are validation fixtures, not a second maintained implementation. Twenty-four
old/new combinations of enforcer/pruning/layout/ordering compare the full result
objects, complete statistics, exact local dominator pairs and layout witnesses.
Additional controls cover requirements/empty catalogs, injected iterators,
repeatability, invalid providers and Pareto schema violations.

Run the independent synthesis and symbolic suites, followed by the executable
research regression suite. Record actual results separately from historical
receipts. The legacy `tests/test_ffm_*.py` files must not be reported as passing
when they fail collection; compare the same command on the base commit to
identify pre-existing failures rather than changing unrelated tests here.

```sh
python -m pytest -q research/joint_synthesis/tests research/symbolic_fusion/tests --disable-warnings
python -m pytest -q research --disable-warnings
```

The original `research/joint-synthesis` worktree stays on its frozen research
baseline. This engineering change is reviewed on `research/search-engine-refactor`.
The unfinished physical-factorization diagnostic was preserved locally as a
named deferred Git stash; it is neither incorporated nor claimed as evidence.
