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
The analytic placeholder interface, specialized Fork quotient and offline C2
analysis are explicitly outside this combination; defaults stay unchanged.

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
```

Continue method work directly on `research/main`. Hardware interface validation
uses the existing `research/dnn-benchmarks` integration branch. Do not introduce
a new branch for this study or edit running experiment sources.
