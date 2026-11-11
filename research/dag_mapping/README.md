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

```sh
python3 -m unittest research.dag_mapping.test_boundary
PYTHONHASHSEED=0 python3 -m research.dag_mapping.study --out FRESH_DIRECTORY --revision SOURCE_COMMIT
```

Continue method work directly on `research/main`. Hardware interface validation
uses the existing `research/dnn-benchmarks` integration branch. Do not introduce
a new branch for this study or edit running experiment sources.
