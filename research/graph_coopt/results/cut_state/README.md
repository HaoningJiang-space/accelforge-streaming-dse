# Cut-state audit artifacts

See [the protocol and interpretation](../../CUT_STATE_ANALYSIS.md).

- `summary.json`: compact aggregation of four independent architecture points.
- `2mm_*.json`: actual cut after Matmul0; one prepared Matmul1 continuation.
- `3mm_*.json`: actual cut after Matmul0 → Matmul1; one prepared Matmul2 continuation.
- `regression.txt`: actual research regression output, including the new tests.

Each JSON retains source SHA-256, environment, typed counterexample documents,
every isolated cut-row response, measured final pair materialization counts,
reconstruction counts and explicitly oracle-assisted deletion witnesses.
Arbitrary symbolic labels are cleared in the legacy projection; all actual
Compatibility fields and numeric values enter the next projection.

The four runs inspect 174 cut rows and re-evaluate 410 distinct completion
cost/resource responses. Exact state interning has no demonstrated benefit under
the strongest observed interfaces. An oracle ablation reduces final matched pairs
in three cases, preserving all ordinary numeric frontier rows and source IDs.
It uses already enumerated target suffix results, so its pair decrease is an
opportunity ceiling, not an algorithmic or end-to-end speedup. The experiment
neither changes the FFM default path nor proves a general substitution rule.
