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

```sh
python3 -m unittest research.dag_mapping.test_boundary
PYTHONHASHSEED=0 python3 -m research.dag_mapping.study --out FRESH_DIRECTORY --revision SOURCE_COMMIT
```

Continue method work directly on `research/main`. Hardware interface validation
uses the existing `research/dnn-benchmarks` integration branch. Do not introduce
a new branch for this study or edit running experiment sources.
