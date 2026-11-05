# Architecture–mapping coupling, RQ1

See [protocol, budgets and conclusions](../../ARCHITECTURE_MAPPING_COOPT.md).

- `2mm.json`, `3mm.json`, `glu.json`: 27 independently searched hardware points
  and nine nominal-shape zero-fused-loop controls each; selected structures,
  tied returned mapping sets, exact resources, full numeric frontiers and frozen
  anchor feasibility/cost evaluations are retained.
- `summary.json`: primary-grid aggregation, not a new joint-search speedup.
- `coupling.png`, `coupling.pdf`: rendered and visually inspected figure.
- `known_shape_reversal.json`: separate native EL reproduction of six prior
  6,144-PE shape/capacity points; all six selected results pass re-evaluation.

The 108 primary/control selected instances are not 108 unique mappings. Primary
selected identities are 10, 10 and 12 respectively. Equal PE/SRAM/bandwidth
strata prevent free hardware-resource upgrades, but no calibrated area, clock
or bandwidth-port energy tradeoff is modeled. The known shape reversal uses a
different PE count, workload size and EL contract; it is not pooled into the
primary RU grid. Exhaustive architecture enumeration with complete inner
optimization is mathematically the joint reference, not a quality-losing method.

The optional bandwidth argument added to the existing shape validation helper
is checked in the shared regression. Logs are in
`../decision_hypergraph/{targeted,regression}.txt`.
