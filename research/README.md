# AccelForge research workspace

**Start here: [whole-repository overview and consolidation](OVERVIEW.md).**
It is the current priority and claim ledger, including the completed DAG gates
and the 2026-11-11 conditional separation audit. The main method entry is now
[dag_mapping](dag_mapping/README.md), with a code map, supported interfaces,
completed-study table and regression commands. The underlying grammar and
conditional-resource methods remain in [index_coupling](index_coupling/STATUS.md)
and [response](index_coupling/response/README.md).

The entries below preserve earlier native/hardware investigations; their
next-step statements are historical, not concurrent active projects.

The [native motivation pilot](motivation/README.md) compares hardware selection
under explicit per-operator DRAM materialization with graph-enabled FFM and
then remaps the selected hardware. It verifies that zero fused loops alone
does not force materialization, reports tie-aware selection regret and
near-tie shortlist controls, and diagnoses two distinct capacity thresholds
on small native matmul chains. This is not a full-model or physical-area study.

The [local DAG structure analysis](graph_structure/README.md) measures tensor
frontiers, weighted activation peaks and schedule sensitivity on 22 repository
and explicitly constructed graphs, with exact topological-prefix optimization
on 21 cases and a state-limited result on the remaining case.
The [asymmetric follow-up](graph_structure/ASYMMETRIC.md) shows that two-step
lookahead repairs the one-step greedy failure. The
[real-model extension](graph_structure/REAL_MODELS.md) exports 10 Torchvision
models successfully (one rejected multi-output case): all 10 source schedules
already minimize the declared materialized activation peak, and DenseNet-121
has a minimum live-tensor frontier of 25. These results narrow the earlier claims.

The [late-binding experiments](late_binding/README.md) compare mapping-first
certificates and exact architecture-first search using the same native candidate
banks. The [Windows runtime guide](runtime/README.md) documents the isolated
environment for running the experiments.

The [DAG runtime](runtime/README.md#executable-dag-weight-prefetch) includes the
port calendar, tensor residency, prefetch search and its replay checks.
The complete experimental history is preserved at
[the original experiment tip](https://github.com/HaoningJiang-space/accelforge-streaming-dse/tree/2cae8406929ef3c2b3d0e9c4c57860569dc96d67).
The synthesis, search-control and native-generation investigations share
[a separate history](https://github.com/HaoningJiang-space/accelforge-streaming-dse/tree/3cd0495a7267a9a4a874802aae4b581409157d1d).

The [local mapping retargetability experiment](tracking_audit/results/retargetability/README.md) found that
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
