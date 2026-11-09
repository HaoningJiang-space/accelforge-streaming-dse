# Completed P14-FFN': shared-input control

All eight amended subset outputs were retrieved and scored on 2026-11-09 using
the frozen `graph/scoring.py ffn` at `3e229762`. This is analysis of completed
runs, not a new mapping search or independent witness execution.

## Frozen rule and result

The `ffm_like_si` view leaves shared graph inputs under the normal curve rules.
For each subset of {H, Z, dH}, those intermediates are materialized; the others
must remain on chip for all consumers. All 8/8 subsets are present, with no
duplicate subset names and empty per-run error files when collected.

The union has 25 Pareto points and reaches total traffic 256 B at capacity
148 B. On the union of its breakpoints and the saved FFM breakpoints:

| Comparison to archived FFM | Breakpoints |
|---|---:|
| Model lower | 26 |
| Equal | 8 |
| Model higher | 1 |

The only higher point is the previously declared plateau offset: at capacity
147 B the model uses 320 B traffic and FFM reports 256 B; the model reaches
256 B at 148 B. At 80 B, traffic is 448 B versus FFM's 576 B (22.22% lower).
This is a modeled archive comparison, not a measured hardware speedup.

- **P14-FFN' equality: fails**, including after the permitted plateau-offset
  exception. There are still 26 lower points.
- **Weak literal "never above": fails at 147 B.**
- **Weak with the same declared 1 B plateau exception: passes.** There is no
  other higher point. Both raw and exception-qualified judgments are reported
  because the weak bullet does not separately repeat the exception.

## What changed, and what this does not establish

The original P14-FFN control forced separate copies for each graph-input
consumer and therefore imposed a 384 B compulsory floor. Allowing shared
inputs removes that incorrect restriction and restores the 256 B floor.
This directly addresses the issue identified in FFN_SHARING_RESULTS.md.

It does not make this view FFM-equivalent. It permits inputs to remain resident
across groups or be fetched once for a whole consuming group; the native
reference has explicit copy einsums and potentially different copy lifetimes
and writes. The amended protocol already allows the model to be cheaper for
this reason. Consequently, the remaining differences do not uniquely identify
one missing native sharing mechanism or prove that native FFM cannot express
the corresponding schedules. Executed witnesses and matching copy semantics
are needed for that attribution.

The full graph's previously reported 34 lower breakpoints and this view's 26
use different unions of breakpoints. Their difference is not "eight gaps
explained". Mechanism attribution must compare a common capacity set and
account for the actual transfers, not subtract these counts.

## Artifacts and reproduction

- `results/ffn_parts/ffm_like_shared_inputs.jsonl`: the eight complete outputs,
  serialized as one JSON object per line; preserves recorded points, seconds
  and peak-memory fields.
- `results/ffn_parts/shared_inputs_scores.txt`: unchanged frozen scorer output.
- `results/ffn_parts/shared_inputs_comparison.json`: all comparison rows, the
  union frontier, input hashes and raw/exception-qualified judgments.

Run the saved-data check:

```sh
python -m research.index_coupling.graph.scoring ffn \
  research/index_coupling/results/ffn_parts/ffm_like_shared_inputs.jsonl
```

The records report 127-146 s per subset and 0.05-0.06 GiB peak memory. They are
different runs and a changed control from the earlier failed jobs, so these
numbers are not an equal-work cache-speedup benchmark. P19 remains a separate
ongoing experiment; its partial records do not determine its verdict.
