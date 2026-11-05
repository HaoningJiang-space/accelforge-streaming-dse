# Initial decision-hypergraph feasibility audit

See [scope and interpretation](../../DECISION_HYPERGRAPH.md).

`2mm.json` and `3mm.json` retain real symbolic template scopes, explicit primal
elimination bags, conservative policy barriers, connected-subgraph diagnostics,
actual native numeric Join work and exact equality-order checks.

The native multi-key pair sets already exclude equality-incompatible candidates.
Factorized index blocks and different equality-test orders preserve full FFM
results, but do not avoid any native numeric candidate evaluation. Full
Reservation/cost/policy decomposition and arbitrary Fusion join-tree or Tile
variable elimination remain unproved and unexecuted. Widths describe the chosen
syntactic representation; they are not intrinsic minimum widths or a performance
guarantee. The policy clique is conservative, not an impossibility proof.

`targeted.txt` and `regression.txt` contain the actual test outputs. `summary.json`
aggregates the observed metrics without treating the index representation's
smaller payload as a full search-memory or speedup result.
