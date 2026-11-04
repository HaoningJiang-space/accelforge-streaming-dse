# AccelForge research workspace

The latest experiment is [array shape × SRAM DSE](tracking_audit/results/shape_capacity/README.md):
the MatMul architecture switch is reproduced, simple cross-shape reuse has limited
benefit, and low-capacity Attention exposes an unfixed score/reconstruction mismatch
also reproduced on the clean `e76e66bf` base. The [capacity-tracking audit](tracking_audit/README.md)
contains earlier reuse experiments, correctness limits, and regression commands.

| Directory | Status |
| --- | --- |
| [shape_capacity](tracking_audit/results/shape_capacity/README.md) | Current architecture-selection grid, strong per-shape baseline, scoped reuse prototype and Attention failure. |
| [tracking_audit](tracking_audit/README.md) | Current capacity reuse, mapping validation and resource-tracking investigations. |
| [tracking_audit/HISTORY.md](tracking_audit/HISTORY.md) | Historical results and root-cause notes, tied to their original commits. |
| [streaming_join](streaming_join/README.md) | Streaming/partitioned Pareto implementation, captured inputs and earlier experiments. |
| [tracking_audit/legacy_p0](tracking_audit/legacy_p0/README.md) | Archived profiling/GPU scripts targeting a different upstream revision. |

Results across upstream versions, template restrictions, or correctness fixes are
not interchangeable. The old 173-second measurement is not a current tag1 baseline.
