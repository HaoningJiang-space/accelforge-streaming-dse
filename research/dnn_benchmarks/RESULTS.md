# First real-model island study

The frozen 39-job study completed on a Linux CPU server. It supports exact
same-grammar frontier agreement on the completed searches, but does **not**
demonstrate a search speedup, whole-model execution, or hardware latency/energy
improvement. Source: `2f8ff8b0`; limits: 30 seconds and 2 GiB per fresh worker.
The manifest records source hashes. Raw records are in `results/server`, with
the machine-readable checks in `results/score.json`.

| Outcome | Jobs | Meaning |
| --- | ---: | --- |
| Complete with exact execution replay | 21 | All 133 saved witnesses replay exactly |
| Search complete, execution unreplayed | 12 | Original tensor extents exceed the frozen 200,000 scalar-step replay limit |
| Timeout | 6 | All arms of the reduced 11-op ResNet island |

For each completed case, all requested arms within v1 agree, and all requested
arms within v2 agree. The three small v2 cases also agree with literal partition
enumeration. In the five cases with completed searches, v2 weakly dominates v1
at every capacity breakpoint. The original ViT island has 32 v1 frontier points
and 30 v2 points; this is a grammar change, not an acceleration at unchanged
mapping quality. Original-shape witnesses are saved, not counted as replayed.

## Search cost and what it says

These are single **profiled** runs on a shared machine. Times are descriptive;
no repeated timing speedup is claimed. The reuse arm combines remainder
canonicalization with the empty-group precheck. C2 and joint arms additionally
use the v2 all-kept-child lower-bound rejection.

| Case | FX / IR ops | v2 DP time (s) | v2 reuse time (s) | v2 C2 time (s) | v2 joint time (s) | DP / joint response entries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ResNet short, reduced | 3 / 3 | 0.172 | 0.200 | 0.178 | 0.193 | 1,632 / 439 |
| ResNet long, reduced | 11 / 11 | timeout | timeout | timeout | timeout | incomplete |
| ViT MLP, reduced | 4 / 6 | 0.185 | 0.306 | 0.167 | 0.278 | 1,135 / 694 |
| ViT MLP, original extents | 4 / 6 | 1.879 | 3.055 | 2.113 | 3.294 | 12,973 / 9,036 |
| U-Net head, reduced | 2 / 3 | 0.029 | 0.068 | 0.030 | 0.067 | 528 / 274 |
| U-Net head, original extents | 2 / 3 | 0.523 | 0.865 | 0.613 | 0.912 | 7,263 / 3,356 |

The response cache becomes smaller without a consistent runtime benefit.
On the original ViT island, C2 rejects 21,810 of 50,770 checked choices, but
response entries only change from 12,973 to 12,966. Bound construction and
incumbent maintenance have costs; rejected choices are not equivalent to
avoided unique subproblems. Joint search also uses more peak memory than DP
there (about 93 MB versus 49 MB). Timeout partial counters must not be used as
full-run state-compression ratios.

## Coverage and validity limits

The inventories contain actual FX graphs and original shapes for ResNet-50,
ViT-B/16, and our explicitly specified 2015 U-Net implementation. None of the
16/32/64/128-prefix audits is fully admitted by the current resource IR. General
spatial convolution, pooling, layout transformations, and attention remain
explicit boundaries. The longest admitted islands have 11, 4, and 2 FX ops.
This study is not a full-DNN scalability benchmark.

The ResNet graph retains evaluation BatchNorm as a separate operation. An
inference compiler can fold suitable BatchNorm into convolution. Before
comparing to a strong native hardware baseline, both sides need the same
constant folding and functional/in-place contract. The reduced ResNet timeout
is evidence about this raw admitted graph, not the optimized ResNet runtime.

Each island has materialized DRAM interfaces. Adding its frontier to other
islands does not establish a global optimum or end-to-end latency. All current
resource cells are float32, including accumulators; the four-byte conversion
does not apply to a mixed-precision accelerator without separate sizing.

The six focused frontend/C2 tests pass. They cover native PyTorch pointwise
and linear semantics, conditional v2 lower bounds, both partition solvers,
and independent witness replay. Numerical testing uses deterministic synthetic
inputs, not pretrained model accuracy.

## Next evidence needed

1. Run the pinned PyTorchSim GEMM import pilot and check the actual compiled
   tile choices, functional output, DMA addresses, and transaction bytes.
2. Expand operator support and vectorized execution validation before claiming
   original-shape or full-model correctness.
3. Profile canonicalization and C2 overhead on expensive states; preserve the
   current negative timing results instead of treating cache reduction as speedup.
4. Compare hardware latency at matched precision, resources, grammar, and search
   budget. Energy/EDP requires a separate calibrated model. A capacity/traffic
   frontier alone need not preserve the fastest mapping, even among tied costs.

Recompute the audit with:

```sh
python -m research.dnn_benchmarks.score_islands \
  --manifest research/dnn_benchmarks/results/island_manifest.json \
  --results research/dnn_benchmarks/results/server \
  --out /tmp/dnn-island-score.json
```
