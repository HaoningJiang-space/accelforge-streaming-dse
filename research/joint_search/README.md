# Finite architecture–mapping shared generation: Stage 0–2

This bounded prototype keeps native AccelForge/FFM generation, Reservation,
Compatibility, numerical Join and Pareto implementations. It does not change the
reference backend. It shares their execution across **one declared finite global
architecture domain**, rather than calling a complete FFM search per point.

The first gate is `2mm(M=16, KN=16)` on NVDLA, shapes `8×32`, `16×16`, `32×8`
with 4/8 KiB GlobalBuffer, fixed bandwidth, precision, hierarchy and action costs.
All six points have 256 PEs. Different SRAM capacities are separate budget strata;
there is no calibrated chip-area model or free global hardware-size comparison.

## Execution and semantics

1. Prepare native template/model structure once at the componentwise upper
   bound. This preparation envelope can have more PEs than a legal target; it is
   **not** a candidate hardware design or an extra domain member.
2. Adapt the existing `TargetEnumerator` cohort interpreter to three finite
   bounds: spatial extent x, spatial extent y and exact GB bits. Native symbol
   order, constraint order, fallback, row order, dtype and Pareto history remain
   part of each execution state. Only identical states coalesce. Each template
   serves all domain points and returns assignments with policy membership.
3. Use native template normalization, unit-loop removal, grouping and local
   Pareto, transporting membership through the existing packed backend. Complete
   partial resource/lifetime structure is retained, not a terminal single-operator
   E/T/peak summary.
4. Invoke the original full Fusion Join once. AND-intersection of architecture
   membership requires every operator in a complete mapping to use the **same**
   domain point. Query each point with its policy bit and exact capacity, then
   recover its full E/T/resource frontier and reconstruction closures.

The old packed column schema calls its labels capacity fractions. Here a
distinct `JointArchitectureDomain` namespace transports opaque ordered domain
IDs `(i+1)/N`; those labels are **not capacity ratios**. Physical capacity is
always an independent integer-bit constraint and is rewritten to the actual
target in public resource views. No budget is inferred from a membership label.
Generation provenance includes a separate joint contract and the entire domain.

The current adapter requires perfect power-of-two MatMul bounds, dyadic PE
extents, unit NVDLA spatial min-usage, zero Pareto tolerance and zero leakage.
Fixed complete-Tile costs are reused only under this restricted fixed-cost model.
The declared six-point validation checks against independently constructed
physical architectures, including pre-model policy Tile coverage per template.
No arbitrary topology, bandwidth/cost parameter, unqueried architecture or
physical Mapspace completeness follows from this gate.

## Modules

| Module | Responsibility |
| --- | --- |
| `architecture_domain.py` | One finite hardware variable, equal-PE budget and IDs |
| `conditional_generator.py` | Adapt native cohorts to architecture-dependent bounds |
| `ffm_backend.py` | Native preparation and source/metadata packaging |
| `conditional_composer.py` | Original FFM Join and architecture-specific frontier extraction |
| `joint_optimizer.py` | One shared generation/composition request |
| `validation.py` | Independent/cached/Event references, Tile coverage, full frontier/source checks |

No consumer-requirement deletion, new resource-effect rule, arbitrary Join order,
MIP or general DAG planner is enabled. These are Stage 0–2 components, not a claim
that graph-guided demand propagation is already effective or novel.

## Acceptance and measurements

The integration gate compares the complete set of E/T/exact-resource vectors,
not just minimum EDP. Mapping provenance columns are not optimization coordinates:
different physical mappings may tie. Source identities are recorded separately,
and every returned source is reconstructed/re-evaluated by the native model.
Template-specific policy Tile sets must equal those from each physical reference
architecture; comparison of only terminal fronts would miss candidate-coverage
errors. A separate 68/96 B test covers the known capacity-boundary failure.

The initial targeted tests pass for all six points plus the boundary case.
End-to-end speed, actual numeric expansion, model rows and memory still need the
benchmark against Independent FFM, FFM + existing cache and the existing
per-shape capacity Event + Bitset search. Shared expansion counts are not a
speedup claim. Consumer Requirements remain a separate future gate.

```sh
python -m pytest -q research/joint_search/tests --disable-warnings
python -m research.joint_search.validation --output research/joint_search/results/stage02/audit.json
```
