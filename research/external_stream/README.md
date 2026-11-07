# External mapper comparison

The [STREAM paper](https://doi.org/10.1109/TC.2024.3477938) studies layer-fused DNN schedules on heterogeneous accelerators. This reproduction uses a pinned revision of the [current official implementation](https://github.com/KULeuven-MICAS/stream), which includes a license-free OR-Tools backend. It does not attribute later software capabilities to the published artifact.

From the repository root, create an isolated Windows environment and run the vendor checks:

```powershell
./research/external_stream/prepare_windows.ps1
Push-Location libraries/stream
try {
    & ./.venv/Scripts/python.exe -X utf8 -m pytest tests/test_hardware_combinations.py -k 'tpu_like_quad_core and (two_conv or swiglu)' -q
} finally {
    Pop-Location
}
```

The affine workload adapter preserves the 3mm chain and the Attention proxy's tensor ranks, affine accesses, iteration counts and 8-bit tensor precision. The STREAM `Relu` node represents one pointwise visit per score for this cost-model exercise; it does not implement softmax or prove equality of arithmetic kernels.

```powershell
$streamPython = './libraries/stream/.venv/Scripts/python.exe'
& $streamPython -X utf8 -m research.external_stream.run --workload 3mm --size 256 --output research/external_stream/results/stream_3mm256.json
& $streamPython -X utf8 -m research.external_stream.run --workload attention --size 128 --workload-only --output research/external_stream/results/stream_attention128_graph.json
```

The current runner exports STREAM's original allocation IR and costs on its example hardware. Native cooptimization uses a single 8-bit NVDLA array with common fanout, exact GlobalBuffer capacity, and fixed action costs. STREAM's optional AccelForge backend prices one tiled operator, while STREAM still accounts for its own transfers, overlap and placement. Neither a vendor smoke result nor an allocation on example hardware is a common-cost result.

On Windows with Python 3.12.12, STREAM 2.3.0, ZigZag 3.10.0, and OR-Tools 9.15.6755, both unmodified vendor tests passed (2Conv and SwiGLU). Use UTF-8 mode for the vendor's SVG writer. The official pipeline solved the 256-sized 3mm chain as one fusion group on its Eyeriss example; the original allocation is in [stream_3mm256.json](results/stream_3mm256.json).

With `--nvdla-geometry 64 96 32768 --local-objective edp --tile-search`, STREAM solved the same 3mm workload using a single array with the requested dimensions and a 32 KiB stress-test buffer, smaller than the registered native 3mm budgets. The allocation split the chain into three fusion groups and overlapped transfers with later iterations. Its local ZigZag search ranks EDP, while the outer STREAM scheduler uses its own latency objective and costs. The exported local mapping is for the final group, and the full allocation IR covers all three groups. The [intersection audit](results/stream_3mm256_projected_intersection.json) rejects the result as a native comparison; it would be wrong to ignore the overlapped schedule and compare the reported costs.

The runs at [64×96, 128 KiB](results/stream_3mm256_matched_geometry_128k_intersection.json)
and [32×192, 132 KiB](results/stream_3mm256_matched_geometry_132k_intersection.json)
use the winning geometries of the 12-point native 3mm reference. Both still
use overlapped transfers. The 128 KiB run also uses factors outside the
native perfect power-of-two space. Neither run passes common evaluation.

To enter a comparison, define a shared schedule subset before scoring. For each external allocation, export all spatial and temporal loops (including their order and tail policy), storage level and lifetime for every tensor, fusion scope, and execution order. Reject external inter-core transfers, overlapping execution, asynchronous DMA or any other scheduling decision not expressible by the native IR. If an exporter cannot recover a decision, report a rejection rather than filling it in using a native optimum. Then check the same two fanout bounds and capacity, and score every successfully translated mapping with the native evaluator. Track generated, translated, and physically feasible candidates separately. Compare both methods on this fixed subset with the same EDP objective, and charge adapter time. If translation removes the external mapper's defining capability, report the standalone reproduction separately.

The [SET artifact](https://github.com/SET-Scheduling-Project/SET-ISCA2023) was also
built and run on Windows. Its build uses an isolated Zig toolchain and replaces
two nonstandard libstdc++ bitset helpers in a build copy. The stock workload
registry ran ResNet in all three search modes. For 3mm, a build-only adapter
adds three 1×1 convolutions: `H=m=256`, `C=k=256`, `K=n=256`, one batch and
8-bit tensors. The graph has the same data dependencies and 50,331,648 MAC
iterations as native 3mm.

```powershell
./research/external_stream/build_set_windows.ps1 -Include3mm
Push-Location libraries/set-isca2023
try {
    & ./build/stschedule.exe --args native_3mm_single native_3mm 1 polar 1 1 1 24 1 12 1
} finally {
    Pop-Location
}
```

The [exported SET schedule](results/set_3mm256_ir.json) retains the first
intermediate on the same core and sends the second through DRAM. The retained
tile is 524,288 bits (64 KiB). SET uses its own Polar core's storage
hierarchy and costing; the export does not give a complete native
loop/storage/lifetime mapping. Its IR was reproduced, but there is no valid
common-cost witness from this run.

## Branched DAGs

The shared graph adapter checks dependencies, operator work and 8-bit tensor
precision for each GEMM or pointwise operator. On GLU at 48×128 and 128 KiB,
[the complete STREAM run](results/stream_dag_glu.json) finishes in 4,162 vendor
cycles, with 278 cycles of inter-iteration overlap. The local DAG calendar
issues each operator to completion for a row band. Its timing has no equivalent
for the observed inter-iteration overlap, so this export is a translation audit.

```powershell
$streamPython = './libraries/stream/.venv/Scripts/python.exe'
& $streamPython -X utf8 -m research.external_stream.dag --case glu --geometry 48 128 131072 --tile-search --output research/local_stream_glu.json
```

The next experiment uses STREAM's own evaluator for both methods. The shared
domain is a single 6,144-PE array with shapes 32×192, 48×128 and 64×96, a shared
128 or 132 KiB SRAM, a single DRAM and a fixed topological order per workload.
For each shape the search includes the original STREAM mapping generator's
default and every explicit fusion cut subset. Each call runs the vendor's
mapping, tiling, ZigZag estimation and GSCIP allocation pipeline. Both outer
searches rank the sum of group energies times the sum of group cycles. STREAM
keeps its latency objective inside the allocator. This enumerates the shared
outer domain with STREAM's chosen inner mappings.

Solving extracted subgraphs independently breaks equivalence. The
[isolation audit](results/dag_host_first.json) records 15 group disagreements
on GLU and 32 on diamond across feasibility, energy and cycles. The replacement
keeps the whole graph inside the pipeline, and reuses a successful allocation
only for matching hardware, native group graph, tensor views, mapping YAML and
solver options. The experiment rejects explicit placements and held state in
this single-DRAM domain. It keeps failed solves uncached. Compare every complete
candidate against the uncached vendor run before interpreting search time.

```powershell
$env:PYTHONHASHSEED = '0'
& $streamPython -X utf8 -m research.external_stream.dag_host --cases glu diamond residual --budgets 131072 --output research/local_stream_matched.json
```

The [128 KiB report](results/dag_host_matched_128k.json) records 129 candidate
configurations and zero disagreements in feasibility, cycles, energy, reported
tiling, placements and SRAM occupancy. A separate check confirms the requested
partition, 6,144-PE peak and exact GEMM iteration count in every successful
whole-graph evaluation. Wall times are single measurements with the same
candidate order and include graph generation, fingerprinting and the native
pipeline. The report predates the allocation-IR hashes added to the runner.

| Workload | Configurations | Full sweep | Allocation reuse | EDP reduction vs. singleton-first |
| --- | ---: | ---: | ---: | ---: |
| GLU | 27 | 28.99 s | 16.67 s | 15.08% |
| Diamond | 51 | 85.13 s | 43.45 s | 0.53% |
| Residual | 51 | 77.04 s | 52.37 s | 15.67% |

Singleton-first keeps every shape tied on the per-layer EDP and then opens
all fusion cuts on those shapes. The quality comparison is derived from the
same full STREAM evaluations and uses the same outer EDP criterion. The best
original automatic STREAM allocation ties the joint result on GLU. On diamond
and residual all automatic candidates fail allocation at this budget. The
complete configured STREAM sweep reaches the same EDP as the memoized sweep
on all three graphs. The gain against that reference is search time.

The [132 KiB replication](results/dag_host_matched_132k.json) matches all 78
configurations, including stable allocation-IR fingerprints and native solver
statuses. The full sweep takes 29.56 and 79.43 seconds for GLU and diamond.
Reuse takes 16.99 and 40.20 seconds. GLU retains its 15.08% advantage over
singleton-first. Diamond changes from a 48×128 array cut after `Merge` at
128 KiB to a 32×192 array cut after `Right` at 132 KiB. The two-stage control
also finds the latter design. On diamond, the two methods reach the best EDP
at nearly the same time at both budgets, even with the full-sweep speedup.

The 128 KiB residual result exhibits a feasibility interaction. A 64×96
array wins on the per-layer plan. STREAM rejects its `Merge`–`Y` fusion
under the shared generator and solve contract. The same fusion succeeds at
32×192 and lowers total EDP from 1.968e12 to 1.659e12 pJ·cycles relative to
the two-stage control. This is a comparison of the shared evaluator's
allocations at this budget.

The [asymmetric order audit](results/dag_host_order_128k.json) offers the
declared order and the order minimizing peak live row width, using the same
three shapes and every zero- or one-cut partition. STREAM's original automatic
generator is included for both. Ten of the 48 trials produce a partition
different from the requested one and are recorded separately. STREAM rewrites
the affine graph before assigning cuts, so an input order does not enforce an
execution order. The best accepted configuration stays on the shape chosen by
the fixed-order control. The audit therefore does not isolate the branch-order
mechanism measured by the independent calendar.

The [near-layerwise order audit](results/dag_host_order_near_singletons_128k.json)
includes the full per-layer plan and every plan that removes one cut. All 42
trials produce a different ordered partition. The pinned STREAM
[`expand_normalizations`](https://github.com/KULeuven-MICAS/stream/blob/407d373f942101895b72b3e6d2c75dbe714633a6/stream/workload/normalization.py#L250)
pass canonicalizes nodes in lexical topological order even for this graph
without normalization. The matched asymmetric experiment uses that canonical
order for both methods and checks the realized groups.

```powershell
& $streamPython -X utf8 -m research.external_stream.dag_host --cases asymmetric --budgets 131072 --extreme-cuts --output research/local_stream_asymmetric.json
```

The [matched asymmetric report](results/dag_host_asymmetric_128k.json) offers
automatic STREAM, every zero- or one-cut partition, the per-layer plan, and
each plan that removes one boundary from it. All 45 configurations match,
including 34 successful allocations and 11 vendor rejections. Full sweep and
reuse take 106.02 and 70.13 seconds. Both choose a 32×192 array, with `Merge`
and `Y` fused and the preceding operators separated. The best automatic
allocation uses 193-way splitting on a fused group, which uses less than 1%
of the peak MAC rate over that group. Its whole-graph EDP is 884.5 times the
explicit-cut winner's EDP. The per-layer-first architecture control also finds
the winner after reopening cuts. The large gap identifies a failure of the
automatic mapping choice in this case. The common complete sweep and the
two-stage control both reach the same design quality.

The bounded search uses the completed groups of a candidate inside the full
STREAM driver. Because each later group adds positive energy and cycles, the
completed groups' summed energy times their summed cycles bounds the full
candidate's EDP. Search stops on a strict loss against the incumbent. A saved
proof includes each prefix group's costs and the incumbent before the candidate.
The uncached comparison reprices the complete configuration and checks the
prefix, the incumbent and the strict inequality. It keeps ties eligible.

```powershell
& $streamPython -X utf8 -m research.external_stream.dag_host --method bounded --cases asymmetric --budgets 131072 --extreme-cuts --output research/local_stream_prefix.json
```

In the [asymmetric bound audit](results/dag_host_prefix_asymmetric_128k.json),
the three methods use the same order, starting with automatic and per-layer
allocations at every shape. The full run prices all 45 configurations. The
memoized run takes 70.36 seconds versus 104.56 seconds uncached. The bounded
run takes 69.62 seconds. It proves 14 candidates cannot win, and all 14 are
confirmed feasible but worse by the uncached run. All three reach the same
best EDP.

The [GLU bound replication](results/dag_host_prefix_glu_132k.json) verifies
13 strict prefix losses among 27 configurations at 132 KiB. The three wall
times are 29.38, 17.30 and 16.85 seconds. The default allocation at the first
shape is already the EDP winner, so this experiment tests traversal cost with
an incumbent available early.

## Native issue order and timing

The [GLU issue-order audit](results/dag_native_order_glu.json) records actual
compute slots for both legal branch orders. For already-normalized affine
graphs the adapter preserves input order during grouping and adds precedence
only to a temporary copy of the lowered scheduling graph. STREAM's tensor
dependencies, routes, tile search, allocation and cost families are retained.
The stock witness uses the original order and scheduling rules.

All three witnesses reconstruct the vendor cycle total from slots, initiation
interval, iteration count and fill, and satisfy the reported bandwidth bounds.
Repeating the representative slots at the solved initiation interval yields
overlapping bookings on the single DRAM link. Three operators also have
fractional activity in the representative iteration. These reports establish
the ordering and aggregate native costs. An exact port-event replay would
require the unamortized firings and their actual transfer intervals. The audit
therefore does not admit the allocations into the AccelForge port calendar.

The [complete canonical asymmetric sweep](results/dag_full_cuts_asymmetric_128k.json)
prices all 64 explicit cut subsets plus the stock automatic mapping on each of
the three shapes. It records 170 successful allocations, 25 native rejections
and no partition mismatches. The best configuration cuts after `Narrow` and
`Merge` on a 32×192 array. Its 6.575e11 pJ·cycles is 40.5% lower than the
earlier restricted-cut result. The tie-aware architecture-first control also
finds this same design. These are native STREAM model costs.

```powershell
& $streamPython -X utf8 -m research.external_stream.dag_host --reference-only --cases asymmetric --budgets 131072 --output research/local_asymmetric_full.json
```
