# G1: retrospective generation value, native 3mm

Scope: the six native 3mm points and **Capacity Events + EnumerationReuse**, under
the same `EL|RESOURCE_USAGE`, exact-bit, ordered-fallback/Pareto contract as
[SEARCH_COST_3MM.md](SEARCH_COST_3MM.md). This is a read-only diagnosis, not a new
optimizer, G2 equivalence test, or G3 certificate. FFM and synthesis stay frozen.

## Observation and attribution

- Observe every template Job, its post-enumeration model rows (Tile assignments),
  the rows actually admitted to native compression/Join, and the compressed row
  indices used by **every returned source of every numerical frontier** of all
  six targets. Do not trace only the EDP winner.
- Use native UUIDs plus ordered, exact integer Tile assignments for provenance;
  never join origins by E/T values, a printed Compatibility, or floating row
  iteration. Compression permutations can reference the same generated Tile.
- Pareto may discard numerically tied sources. We preserve every source the
  reference returns, not all alternative source identities ever considered.
  This is a numerical-frontier contract, not exhaustive mapspace coverage.
- Record per-Job evaluation time (`make_tile_shapes`), separately nested symbolic
  modeling/target enumeration/output compilation, and per-batch non-Job overhead.
  Subtract measured observer bookkeeping from enclosing timed scopes. Do not
  assign shared setup, whole-template symbolic time, or batch Pareto cost to
  individual rejected rows in proportion to row count.
- Classify Jobs as having any retained descendant at any target, versus none.
  Classify a compatibility batch as wholly unused only if all its Jobs have no
  retained descendants. Global template construction and unattributed generation
  overhead receive **zero** avoidable credit.

## Meaning of the upper estimate

Sum time of wholly unused Jobs and wholly unused batch overhead, counting each
scope once. This is an optimistic **post-hoc whole-task deletion estimate**, not
an attainable speedup, a safe deletion rule, or a universal upper bound on other
algorithms. It grants perfect free knowledge of final results, ignores changes
in cache producers, fallback/Pareto cohorts, and task execution order, and assumes
remaining costs unchanged. A task with even one final descendant is fully charged
as necessary. Unused rows in such a task are counted but receive no estimated
time saving. Thus the task estimate can miss finer-grained opportunities.

Report both the task fraction of measured generation and the corresponding
fixed-other-cost whole-search projection. **G1 and G2 savings overlap and cannot
be added** without measuring their union. No claim that G1 is an online graph
constraint or that non-contribution implies structural infeasibility.

## Execution and checks

Use three fresh processes, single worker and requested single-thread numerical
environment. Each first warms the unchanged Event backend, then runs one traced
pass with fresh candidate/cache scopes. Compare all six complete numerical
frontiers exactly against `results/search_cost_3mm/events_ru_1.json` and that
process's unobserved warm-up. Record instrumented elapsed time and observer time;
these are diagnostic attribution passes, **not new uninstrumented benchmarks**.

Fail on unknown Job/Tile/compressed indices, lost symbols, duplicate Tile keys,
unmapped returned source rows, or negative/non-additive timing attribution.
Publish raw per-task times, generated Tile IDs, compression edges, all final
source edges and target vectors. Include unit counterexamples for shared tasks,
multiple frontier points/targets, and exact high-bit integer Tile values.
