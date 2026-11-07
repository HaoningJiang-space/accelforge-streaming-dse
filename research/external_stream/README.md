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
