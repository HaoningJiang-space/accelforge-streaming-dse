# DAG mapping research entry

The target is graph-structured mapping search with shared data, resource limits
and cross-operator fusion. Existing Cut DP, symmetry and exact conditional
responses are tools; small Chain/Fork results do not establish scalability for
general DNN DAGs. M8 is retained as a conditional-solver microbenchmark.

The first bounded study is [D1](PROTOCOL.md): compare closed region boundaries
with a shared loop around producer/body/join regions, against complete native
search on six small supported graphs. `boundary.py` implements the exact fixed
region building block. `study.py` records its limits; it is not a new scalable
optimizer, dynamic topological-order DP, or complete DNN frontend.

[D1 results](RESULTS.md): six completed cases, 642 exact boundary-policy checks
and 146 exact root replays. All three restricted arms lose complete-frontier
points on every case. The concrete missing witness has nested I and L loops
with different operator scopes; a single common outer loop is insufficient.

[Conditional separator plan](INTERFACE_PLAN.md) distinguishes closed subtree
interfaces from interleaved event protocols, gives a restricted substitution
lemma, and specifies the representation/substitution/work gates before a new
optimizer. [Primary-source notes](RELATED_WORK_CHECK.md) avoid treating D1 as
a counterexample to Welder or Crane; PolyMage 2020's full recurrence remains
unverified because publisher/repository retrieval failed.

The plan's derivation review makes the solve/group/Hold grammar explicit,
separates prefix-response reuse from continuation equivalence, and records a
single-whole-region scalar corner not covered by D1's three-region protocol.

[Gate 1 results](RESULTS.md#后续-gate-1带类型的层次表示通过验证): the typed hierarchy
roundtrips and independently executes 146 archived plus 60 freshly generated
witnesses; all six complete native frontiers agree and 24 tests pass. The scalar
whole-part corner is repaired. This is representation/certification, not a new
search algorithm, arbitrary-yield interface, or speedup result.

[Gate 2 results](RESULTS.md#后续-gate-2跨顺序闭合响应复用正确但未通过效率门槛): identical
closed responses can be shared across global-order parents, with 13,102 exact
conditional checks and 1,554 root replays. The frozen efficiency criterion
fails: only 0.44%/4.69% improvement on the two primary DAGs and a 2.30% mixed-DAG
regression, with higher memory. This bounded cache application is stopped;
neither order enumeration nor Residency-mask growth is removed.

[Gate 3 results](DOWNSET_RESULTS.md): downset recursion preserves all 11 tested
full frontiers and 84 root executions, but fails its frozen efficiency criterion
against symmetry plus prefix sharing. This separate experiment is also stopped.

[Existing-optimization integration protocol](INTERFACE_PLAN.md#9-existing-optimization-compatibility-audit-and-composition-study)
audits which old reductions were actually enabled. The opt-in prefix adapter
now accepts exact infeasibility checks, conditional independent-op splitting
and ordered remainder isomorphism together. It keeps native rank/tensor witness
restoration and checks numeric child feasibility before constructing the prefix.
This is integration of existing reductions, not a new DAG equivalence theorem.
The specialized Fork quotient and offline C2 analysis remain separate;
defaults stay unchanged. The first matrix did not combine analytic placeholders.

```python
from research.index_coupling.response.prefix import make_kernel

kernel, _ = make_kernel(frames=True, composition='numeric', reductions=True)
points = kernel(graph, partitions='dp', scalar_leaf='v2', witness=True,
                prune_infeasible_groups=True, independent_ops=True,
                canonical_remainders=True)
```

This demonstrates the available combination, not a recommendation to enable
every flag: matching and representation costs must be included in the comparison.

[Composition results](RESULTS.md#已有优化组合审计可以接通但收益依赖结构): all 336 server tasks,
1,210 per-order frontier comparisons, 2,240 root executions and 56 tests pass.
Independent splitting adds 1.026–1.043× on the three DAGs; infeasibility adds
about 1.39× over prefix alone on tiny stacks, while the existing analytic arm
still has a lower median. Remainder normalization gives about 5.7× on the
rank-symmetric single-op control but slows the tested DAGs. All-on is not best;
the complete eleven-arm matrix and costs are retained, and defaults stay off.

[Analytic follow-up protocol](INTERFACE_PLAN.md#10-analytic-responses-with-transported-witnesses)
extends the opt-in interface: a renamed analytic placeholder retains its source
registry key and accumulated operator/tensor/rank map. Recovery constructs the
source witness, then maps it to the caller. It supports p/i/r together with the
existing Unit-M and scalar-separator providers under exact unlimited v2 default
costs. The shared-response pool remains outside this combination.

```python
from research.dag_mapping.reuse import RegionSession

session = RegionSession(graph, unit=True, certificate=True, reductions=True)
points = [(c, q, session.recover(notes))
          for c, q, notes in session.query(prune_infeasible_groups=True)]
```

`recover()` produces native executable notes; its work belongs in complete
mapping-generation time. The compiled experimental adapter handles placeholder
transport, while production `curve.py` stays unchanged.

[Analytic composition results](RESULTS.md#解析响应组合续验见证接口接通收益没有继续叠加):
330 server tasks, 1,365 per-order frontier comparisons, 2,310 root replays and
63 tests pass. There are 200 transported analytic placeholders in saved root
plans, including actual DAGs. No new combination beats the fastest declared
old configuration on these cases. In FFN-4, analytic substitution has already
removed every empty transition that the precheck could skip: 1,526 checks yield
zero skips. The interface works, but the two separate gains do not multiply.

```sh
python3 -m unittest research.dag_mapping.test_boundary
python3 -m unittest research.dag_mapping.test_hierarchy
PYTHONHASHSEED=0 python3 -m research.dag_mapping.study --out FRESH_DIRECTORY --revision SOURCE_COMMIT
PYTHONHASHSEED=0 python3 -m research.dag_mapping.check_hierarchy --out FRESH_RESULT.json
python3 -m unittest research.dag_mapping.test_reuse
python3 -m research.dag_mapping.summarize_reuse research/dag_mapping/results/reuse --out FRESH_SUMMARY.json
python3 -m unittest research.index_coupling.test_prefix_reductions
python3 -m research.dag_mapping.bench_composition run --out FRESH_DIRECTORY --revision SOURCE_COMMIT
python3 -m research.dag_mapping.summarize_composition research/dag_mapping/results/composition --out FRESH_SUMMARY.json
python3 -m unittest research.index_coupling.test_analytic_composition
python3 -m research.dag_mapping.bench_analytic_composition run --out FRESH_DIRECTORY --revision SOURCE_COMMIT
python3 -m research.dag_mapping.summarize_composition research/dag_mapping/results/analytic_composition --out FRESH_SUMMARY.json
```

Continue method work directly on `research/main`. Hardware interface validation
uses the existing `research/dnn-benchmarks` integration branch. Do not introduce
a new branch for this study or edit running experiment sources.

[Resident-separated interval audit](CONDITIONAL_SEPARATION_RESULTS.md) examines
the remaining work under the strong Prefix+i baseline. The restricted solve
factorization is proved in [the protocol](CONDITIONAL_SEPARATION.md); all 10,539
eligible conditional frontiers and 157 oracle-substituted root executions agree.
Different parent responses can reuse unaffected branch responses (5,395 paired
examples), but optimistic DP-work ceilings are only 11.58%/13.31%/6.99% on the
three DAGs. These are not speedups; no timed implementation or default change is
introduced. An archived L-loop with three non-scalar obligations X/V0/V1 makes
the remaining coupled decision and its order sensitivity concrete.
