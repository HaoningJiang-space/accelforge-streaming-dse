# AccelForge research workspace

The [Chat-supervised joint-budget experiment](joint_budget/README.md) reproduces
native 3mm across twelve architectures on Windows and tests a pre-enumeration
graph-support relaxation. It finds **zero nonlocal family-deletion certificates**;
no new BCGE optimizer or SOTA improvement is claimed. The
[native Windows runtime](runtime/README.md) records its compatibility limits.

The latest experiment is [local mapping retargetability](tracking_audit/results/retargetability/README.md):
pure spatial factor rebinding is insufficient; allowing storage tile extents to
change recovers 11/18 selected cross-shape MatMul winners but only 2/24 Attention
winners. This is a coverage diagnostic, not an end-to-end acceleration result.
The Attention scoring mismatch is repaired by applying the selected loop
permutation to numeric Join matching. The [capacity-tracking audit](tracking_audit/README.md)
contains earlier reuse experiments, correctness limits, and regression commands.

| Directory | Status |
| --- | --- |
| [retargetability](tracking_audit/results/retargetability/README.md) | Local structure coverage, actual retargeted witnesses, Attention action-level diagnosis and repair. |
| [shape_capacity](tracking_audit/results/shape_capacity/README.md) | Current architecture-selection grid, strong per-shape baseline, scoped reuse prototype and Attention failure. |
| [tracking_audit](tracking_audit/README.md) | Current capacity reuse, mapping validation and resource-tracking investigations. |
| [tracking_audit/HISTORY.md](tracking_audit/HISTORY.md) | Historical results and root-cause notes, tied to their original commits. |
| [streaming_join](streaming_join/README.md) | Streaming/partitioned Pareto implementation, captured inputs and earlier experiments. |
| [tracking_audit/legacy_p0](tracking_audit/legacy_p0/README.md) | Archived profiling/GPU scripts targeting a different upstream revision. |

Results across upstream versions, template restrictions, or correctness fixes are
not interchangeable. The old 173-second measurement is not a current tag1 baseline.
