# P0 reading: aggregation laws and required interfaces

Focused reading covers the sections/methods below, not every page of each paper.
Pinned URLs, file sizes and SHA-256 fingerprints are retained in
`results/conditional_elimination/reading_sources.json`. Third-party source bodies
are not vendored into this repository.

## FAQ / InsideOut

Read [FAQ v7](https://arxiv.org/pdf/1504.04044v7), §§1.2, 5.1.2, 5.2 and the legal
ordering discussion in §6. Elimination folds factors incident to a variable using
appropriate algebraic laws. Indicator projections let other factors restrict
which boundary entries are computed. Permissible aggregate orders and factor
representation affect the analysis; a smaller ordinary graph width alone does
not authorize a new execution order. The paper's general formulation uses
commutative semiring/product aggregates. The full version extends the PODS 2016
abstract; the inspected revision is December 2023.

**Implications for this project, derived from the local FFM code:**

- Distinguish binding an architecture variable from eliminating it. Keeping
  architecture in a factor signature is not the same as compiling it correctly.
- Local minimum EDP cannot substitute for a conditional E/T/resource frontier.
- Ordered fallback selects from a cohort, and prefix Pareto uses history. They
  cannot be treated as independent row predicates or freely reordered aggregates.
- Native FFM resource arithmetic includes ordered max/add effects. An ordered,
  monotone bucket reduction can be useful without establishing a commutative
  product for the whole search. FAQ-width complexity bounds do not follow.
- The previous equality-order audit did not implement aggregate elimination.

## Cascades and Calcite

Read [Cascades](https://15799.courses.cs.cmu.edu/spring2025/papers/05-cascades/graefe-ieee1995.pdf),
the operator interface and required/synthesized-property discussion in §§3.1–3.2,
plus enforcer rules. Physical operators translate optimization requirements to
their inputs; delivered properties can satisfy a less specific requirement.
Enforcers provide explicit conversion alternatives.

Inspect Calcite's
[RelSubset](https://github.com/apache/calcite/blob/b1308feff49c8b747b3bbb52e1519d334bc984ec/core/src/main/java/org/apache/calcite/plan/volcano/RelSubset.java)
and [AbstractConverter](https://github.com/apache/calcite/blob/c4042a34ef054b89cec1c47fefcbc8689bad55be/core/src/main/java/org/apache/calcite/plan/volcano/AbstractConverter.java).
The inspected methods separate REQUIRED/DELIVERED state, filter alternatives by
trait satisfaction and distinguish an optimized winner from unfinished search.
Abstract conversions remain pending requirements and have infinite self-cost
until implemented; they are not free physical conversions.

**Implications for this project, derived from the local FFM code:**

- A consumer requirement must be explicit. A fixed template label is insufficient
  because instantiated unit loops disappear and reservation indices shift.
- Same Compatibility is not a universal physical-interface proof. The actual
  permutation, matching fields, tensor effects, units and continuation matter.
- One scalar `bestCost` cannot replace FFM's E/T/resource alternatives.
- Unknown support/coverage remains unknown. A missing converter or candidate
  never proves that a physical mapping is impossible.
- We introduce no retile/move enforcer and no replacement for GraphMemo.

## Proposed joint variables, not an established factorization

Keep one global architecture variable `a=(Px, Py, C_GB, B)`. Local Mapping
choices `m_i`, exchanged tensor interfaces `z_e`, and resource-transfer states
`s_i` are different variables. A prospective factorization would need separate
local legality/cost factors, interface constraints and ordered resource-state
transitions. The architecture variable must remain shared across all factors;
eliminating each operator under its own preferred hardware solves a different
problem. A calibrated budget/cost model is still required for hardware selection.

Eliminating `m_i` would have to leave a conditional E/T/resource-effect frontier
over its remaining separator, rather than a single minimum-EDP candidate. For
example, `(E,T)=(1,10)` and `(4,3)` trade off, and adding a suffix with `(100,0)`
changes their EDP order. Resource effects and candidate availability add further
conditions. The existing ordered FFM executor supplies the reference semantics;
writing these variables down does not prove that its complete program admits
commutative factor multiplication or arbitrary elimination order.

## Executable obligation selected from the reading

For a **fixed terminal consumer bucket**, ask whether a producer choice can be
eliminated before pair materialization using its required fields and its native
resource response function. This exercises a concrete monotone aggregation law,
not an assumed universal equivalence of partial mappings.

See [the contract and derivation](CONDITIONAL_ELIMINATION.md). It is limited to
already generated candidates and one fixed architecture/context. The objective
remains graph-structured architecture–mapping co-optimization; terminal Join
pruning is only a small law-validation experiment for a future factor solver.
