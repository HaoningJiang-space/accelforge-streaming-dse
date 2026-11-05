# Independent physical-plan composition gate

The active hypothesis is **Graph-Structured Architecture–Mapping Synthesis**.
Development continues on the isolated **`research/joint-synthesis`** branch;
[DEVELOPMENT.md](DEVELOPMENT.md) fixes the active/core/reference boundaries.
This directory starts with its mathematical/executable foundation: an explicit
finite 2mm grammar, a resource-demand composition law, and independent exhaustive
validation. It does not wrap FFM generation or Join as a new optimizer.

The next [global architecture-binding gate](ARCHITECTURE_RESULTS.md) is now
executable under explicit normalized hardware prices. It produces one global
Architecture–Mapping frontier from the graph demands and supports later budget
queries without rerunning the graph DP. This remains the restricted barrier
model, with no calibrated area or FFM-performance equivalence claim.

Read [CONTRACT.md](CONTRACT.md) first. It defines the legal programs, physical
properties, exact cost model, sufficient replacement rule and proof obligations.
The executable main path uses only Python's standard library and runs with
`python -S`; it imports no AccelForge/FFM generator, Join or cost routine.

For one graph and one normalized hardware family:

```python
from research.joint_synthesis.graph_ir import TwoMM, CostModel
from research.joint_synthesis.hardware_ir import GridAxis, HardwareEnvelope, NormalizedPrices
from research.joint_synthesis.architecture_synth import solve_joint

envelope = HardwareEnvelope(GridAxis(1, 3), GridAxis(1, 5),
                            GridAxis(4, 48, 4), GridAxis(1, 9))
family, work = solve_joint(TwoMM(), CostModel(), envelope,
                          NormalizedPrices(4, 1, 3), budget_ceiling=128)
best = family.best_edp(64)
assert best.resource_cost <= 64
print(best.hardware, best.energy, best.latency)
```

The same `family` answers other budgets up to 128 without new Mapping generation
or DP. It does not rebind a different envelope or price function automatically.

## What is implemented

| Component | Actual role |
| --- | --- |
| `graph_ir.py` | Immutable 2mm graph, tensor identities and normalized model parameters |
| `physical_plan.py` | Required/delivered properties, schedules and JSON-restorable witnesses |
| `schedule_rules.py` | Architecture-independent divisor tiles, spatial extents and three loop/working-set rules |
| `resource_demand.py` | Closed-form demands and bandwidth-dependent latency `c+q/B` |
| `composition.py` | Explicit conversion demands and materialized-cut resource composition |
| `conditional_frontier.py` | Exact dominance within a fixed physical interface |
| `graph_dp.py` | Reduce local conditional frontiers, compose through explicit conversions, retain the root demand frontier |
| `exhaustive_oracle.py` | Independent grammar enumeration and scalar allocation/address/MAC interpreter |
| `validate.py` | Local/complete summary checks, exact root-front comparison, later hardware queries and witness replay |
| `hardware_ir.py` | Global hardware envelope, integer grids and positive normalized resource prices |
| `architecture_synth.py` | Demand-driven hardware binding, joint cost/E/T frontier and budget queries |
| `architecture_oracle.py` | Independent full-grid hardware binding and frontier comparison |
| `validate_architecture.py` | Full joint-front, all-budget and selected-source verification |

The generator and DP accept **no architecture point or list**. They produce
`(required_Px, required_Py, peak_SRAM, energy, latency_intercept, DRAM_bytes)`
and physical execution witnesses. A single complete plan must use one global
array/capacity/bandwidth. Validation queries hardware only after DP completes.
Hardware selection under normalized budgets is implemented; a calibrated budget
and realistic cost model remain unimplemented.

The independent Oracle does not use the analytical demand/composition/pruning
routines to calculate results. It allocates real copy records, interprets
row/column physical addresses and counts contiguous DRAM runs, performs scalar
integer MACs, releases temporaries and checks the full result against ordinary
scalar 2mm. Analytical comparisons occur only after its observations exist.

## First recorded gate

Both cases use two-byte bounded integer data and the declared normalized model.
Physical properties comprise four full-X interfaces: row/column-major ×
SRAM/DRAM. Nonidentity connections use explicitly costed copies/staging.

| Case `(M,K,N,P)` | Raw local alternatives, each side | Retained prefix / consumer states | Raw complete pairs | DP complete pairs | Root demand vectors |
| --- | ---: | ---: | ---: | ---: | ---: |
| (2,2,2,2) | 96 / 96 | 42 / 37 | 9,216 | 1,554 | 19 |
| (2,2,4,2) | 144 / 144 | 70 / 47 | 20,736 | 3,290 | 54 |

The [modular replay](results/composition_gate_modular.json) checks the same
numerical results as the [initial a986b381 validation](results/composition_gate.json):

- **480 local summaries** against independent action/occupancy traces;
- **29,952 complete plans**, including every declared conversion, against the
  resource-composition law and numeric 2mm result;
- exact equality of the complete root **six-dimensional demand frontier**;
- **1,760 hardware queries**, created afterwards at integer Px/Py, C−1/C/C+1
  around every observed peak, and bandwidths 1,2,3,5,8; full E/T fronts agree;
- all **73 retained source witnesses** through JSON round-trip and execution
  under three additional input seeds. Instances are not additional unique plans.

The reduction in complete pair materialization is 83.1% / 84.1% **in this
grammar**. It follows from interface-conditioned componentwise dominance and
does not establish a novel algorithm or a general separator-width bound.
Timing fields are proof-gate diagnostics, not an FFM/DSE speedup comparison.

Eleven targeted tests cover the exhaustive gates, all 16 conversion endpoints,
source reconstruction, rejection of unknown interface fields, forbidden FFM
dependencies and two necessary counterexamples: local minimum EDP can lose a
global winner, and conversion double residency can exceed both endpoint peaks.
The tests also retain crossing bandwidth cost functions as separate states and
verify that the Oracle stores row/column layouts in different physical packing.
A separate fresh `python -S` process blocks imports of FFM and all production
cost/composition/search modules, then directly executes the Oracle.

## Boundaries and next decision

This proof is for **complete materialization barriers**. It excludes streaming
Fusion, partial tensor channels, overlapping execution, arbitrary aliasing and
early releases. Omitting those choices restricts the search grammar; it does not
prove they are physically illegal or inferior. Full tensor ownership and the
absence of hidden live tensors make this separator sufficient. Neither condition
can be assumed for an FFM fused cut or a branching graph.

The cost model is normalized and deliberately simple: fixed per-byte/MAC energy,
unbounded SRAM service rate, fluid DRAM bandwidth and no compute/DMA overlap. It
is **different from NVDLA/FFM**. No EDP, runtime or quality ranking against FFM,
Cache, Events, SENNA or other co-design methods is made. The previous
[`joint_search`](../joint_search/README.md) results remain strong engineering
references, not comparable timings for this toy model.

This passes an initial **restricted instance** of the Steps 0–3 composition gate.
It does not complete their general versions or the roadmap:

| Roadmap obligation | Scope reached |
| --- | --- |
| Problem/model | Finite integer grammar and normalized service; calibrated budget/model pending |
| Physical-plan IR | Full materialized X and explicit converters; no streaming or arbitrary graph importer |
| Demand frontier | Analytical local rules checked against execution for this grammar |
| Independent DP | Two fixed-cut 2mm cases equal exhaustive demand/E/T fronts |
| Global hardware synthesis | Normalized-cost binding and budget queries pass independent grids; calibrated model pending |
| Graph scalability / strong baselines | Not implemented or claimed |

Before scaling to GLU or claiming realistic synthesis, the next
semantic gate must test whether a streaming/fused boundary can retain the same
replacement guarantee with a compact live-copy/partial-accumulator state. If
that state approaches exhaustive histories, stop expanding the graph. Global
calibrated architecture-budget synthesis, the known real shape-switch case and strong
same-model performance baselines remain uncompleted.

## Reproduce

```sh
python -S -m research.joint_synthesis.validate --output research/joint_synthesis/results/composition_gate_modular.json
python -S -m research.joint_synthesis.validate_architecture --output research/joint_synthesis/results/architecture_gate.json
python -S -m research.joint_synthesis.validate_oracle --output research/joint_synthesis/results/oracle_shape_gate.json
python -m pytest -q research/joint_synthesis/tests --disable-warnings
```

[ORACLE_REVIEW_RESULTS.md](ORACLE_REVIEW_RESULTS.md) describes the strict
View/Allocation/precision checks and three new cross-shape/nondefault-cost
exhaustive cases. [oracle_shape_tests.txt](results/oracle_shape_tests.txt) records
62 tests after those review fixes. The 54-test hardening and earlier 19-test
[architecture receipt](results/architecture_tests.txt) and 10/11-test receipts
remain historical and overlap this set. The
existing 661-test FFM research regression was recorded at `d40a664b`; it has not
been rerun for this isolated, standard-library-only module. No production FFM
code changed in this gate. Paper mechanisms and their limits are linked in the
contract; a complete five-paper literature review is not claimed here.
