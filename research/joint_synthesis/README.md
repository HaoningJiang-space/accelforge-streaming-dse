# Independent physical-plan composition gate

The active hypothesis is **Graph-Structured Architecture–Mapping Synthesis**.
This directory starts with its mathematical/executable foundation: an explicit
finite 2mm grammar, a resource-demand composition law, and independent exhaustive
validation. It does not wrap FFM generation or Join as a new optimizer.

Read [CONTRACT.md](CONTRACT.md) first. It defines the legal programs, physical
properties, exact cost model, sufficient replacement rule and proof obligations.
The executable main path uses only Python's standard library and runs with
`python -S`; it imports no AccelForge/FFM generator, Join or cost routine.

## What is implemented

| Component | Actual role |
| --- | --- |
| `graph_ir.py` | Immutable 2mm program, physical properties, schedules and JSON-restorable witnesses |
| `schedule_rules.py` | Architecture-independent divisor tiles, spatial extents and three loop/working-set rules |
| `resource_demand.py` | Closed-form demands and bandwidth-dependent latency `c+q/B` |
| `conditional_frontier.py` | Exact dominance within a fixed physical interface |
| `graph_dp.py` | Reduce local conditional frontiers, compose through explicit conversions, retain the root demand frontier |
| `exhaustive_oracle.py` | Independent grammar enumeration and scalar allocation/address/MAC interpreter |
| `validate.py` | Local/complete summary checks, exact root-front comparison, later hardware queries and witness replay |

The generator and DP accept **no architecture point or list**. They produce
`(required_Px, required_Py, peak_SRAM, energy, latency_intercept, DRAM_bytes)`
and physical execution witnesses. A single complete plan must use one global
array/capacity/bandwidth. Validation queries hardware only after DP completes.
This is not yet architecture selection under a calibrated budget (Step 4).

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

The [raw validation](results/composition_gate.json) checks:

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

Ten targeted tests cover the exhaustive gates, all 16 conversion endpoints,
source reconstruction, rejection of unknown interface fields, forbidden FFM
dependencies and two necessary counterexamples: local minimum EDP can lose a
global winner, and conversion double residency can exceed both endpoint peaks.
The tests also retain crossing bandwidth cost functions as separate states and
verify that the Oracle stores row/column layouts in different physical packing.

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
| Global hardware synthesis | Not implemented; later validation queries are not an architecture optimizer |
| Graph scalability / strong baselines | Not implemented or claimed |

Before scaling to GLU or claiming realistic synthesis, the next
semantic gate must test whether a streaming/fused boundary can retain the same
replacement guarantee with a compact live-copy/partial-accumulator state. If
that state approaches exhaustive histories, stop expanding the graph. Global
architecture-budget synthesis, the known real shape-switch case and strong
same-model performance baselines remain uncompleted.

## Reproduce

```sh
python -S -m research.joint_synthesis.validate --output research/joint_synthesis/results/composition_gate.json
python -m pytest -q research/joint_synthesis/tests --disable-warnings
```

[targeted_tests.txt](results/targeted_tests.txt) records the ten new tests. The
existing 661-test FFM research regression was recorded at `d40a664b`; it has not
been rerun for this isolated, standard-library-only module. No production FFM
code changed in this gate. Paper mechanisms and their limits are linked in the
contract; a complete five-paper literature review is not claimed here.

## Mapping-first candidate kill test

The screen uses materialized, serial operators and AccelForge's NVDLA template.
It captures the native tile rows before cross-template Pareto, including the
enumerator's own earlier reductions. The envelope is 32 × 192 PEs, 2 MiB of
GlobalBuffer, and 8 bits per Register instance. The experiments vary PE
dimensions, GlobalBuffer capacity, and its read and write bandwidth together.
The budget is normalized as PE count / 6144 + GlobalBuffer bits / 16777216 +
bandwidth multiplier / 2 ≤ 1.5. Energy uses fixed native action prices and
zero leakage. Latency uses the native per-component costs and a maximum within
each operator, summed across operators. This scope covers the native
unfused latency column. The experiment models neither a physical area budget
nor separate graph-level fill, staging, or port calendars.

| Workload | Native tile rows | Exact signature frontier | 10% EDP boxes | Exact bound survivors | Boxes and bound survivors |
|---|---:|---:|---:|---:|---:|
| [GLU](results/kill_frontier_glu.json) | 4,442 | 3,277 | 3,257 | 4 | 4 |
| [Attention](results/kill_frontier_attention.json) | 2,466 | 1,703 | 1,697 | 3 | 3 |
| [ResNet bottleneck](results/kill_frontier_resnet.json) | 7,190 | 2,871 | 2,846 | 22 | 12 |

All 11 operators meet the 1,000-residual threshold with the exact bound alone.
The bound uses a common feasible incumbent. For each candidate, it uses the
fastest bandwidth compatible with that candidate's demand. The remaining
operators contribute separate minima of energy and latency over their own
relaxed architectures. The graph bound is the product of the energy sum and
the latency sum. The incumbent equals the relaxed bound for GLU and Attention
to reported precision. ResNet's incumbent is 0.092% above the relaxed bound.
These certificates apply to the captured candidate banks.

Exact dominance compares PE and SRAM requirements, aggregate action counts
per component and action, and the service time of each independently scaled
component. The boxes retain exact demand antichains. Costs in a box differ
by at most √1.1 per coordinate, including a separate bin for zeros. One
replacement per operator bounds serial EDP inflation by 1.1. The two-layer
oracle enumerates mapping pairs at 12 hardware points, regenerates native
tiles at each point, checks the exact and approximate fronts, and verifies the
bound against continuous bandwidth binding on the tiny bank.

The workload equations use the repository's GLU and Attention proxies. The
ResNet workload includes the residual Add and an implicit zero-padding halo.
Its convolution charges the full iteration space at the boundary. Runs used
a local Windows watchdog with per-workload limits of 240 seconds and 2 GiB
working set. The ResNet case took 108 seconds. On Linux, use the existing
watchdog from an AccelForge environment.

```sh
research/tracking_audit/run_capped.sh 2 240 /tmp/frontier.log -- \
  python -m research.joint_synthesis.kill_frontier resnet /tmp/resnet.json
python -m pytest -q research/joint_synthesis/tests/test_kill_frontier.py
```

[DOSA](https://people.eecs.berkeley.edu/~ysshao/assets/papers/dosa-micro2023.pdf)
already uses mapping-first multilayer co-search, and
[SENNA](https://doi.org/10.1145/3705731) already combines layer requirements
by a componentwise maximum. The remaining question is whether certified
search improves time to end-to-end EDP on a large shared space. This screen
measures candidate compression and does not compare optimizers.
