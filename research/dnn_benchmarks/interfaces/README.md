# Versioned plain-GEMM evaluation interfaces

This branch extends the integration without changing the frozen 100-run fidelity
protocol or its hardware. The new requests explicitly select hardware capacity
and scheduling policy. Graph witnesses, cross-operator residency, arbitrary loop
orders, bias, tails, other dtypes, and energy remain unsupported capabilities.

## Request and capabilities

`contract.py` defines `CAPABILITIES` and `gemm-evaluation-request.v1`:

```json
{
  "schema": "gemm-evaluation-request.v1",
  "operator_id": "block0.projection",
  "mapping_id": "candidate0",
  "workload": {"kind": "plain_gemm", "shape": [64,128,32],
               "dtype": "float32", "layout": "row_major_contiguous"},
  "mapping": {"mode": "external", "tile": [64,128,32],
              "subtile": [64,128,32], "loop_order": ["M","N","K"], "strict": true},
  "hardware": {"sram_bytes_per_lane": 1024, "serial_tiles": true}
}
```

Unknown fields and unsupported capabilities are rejected. Hardware defaults are
materialized in the normalized request and hashed, including one core, 128 lanes,
two systolic arrays, HBM2_TPUv3 and 940 MHz core clock. Capacity is explicit bytes
per lane, a power of two from 512 B to 1 MiB. Native `heuristic` and `autotune`
modes omit tile/subtile; requests with tiles in those modes are rejected.

`operator_id` and `mapping_id` survive into receipts and results. This prevents
single-kernel evaluations from being confused when shapes coincide. The
underlying upstream multi-operator importer still uses shape keys: this interface
admits one plain GEMM per evaluation, and does not claim to solve general
same-shape operator disambiguation inside an arbitrary compiled graph.

## Mapping and memory receipts

The selected timing trace identifies the exact compiled kernel. The receipt
checks all six tile parameters, original loop order/extents, requested mapping,
source and TOG hashes. `SUB_TILE_K` is now explicitly rendered. Allocation
receipts are bound to the actual compiled ELF and assembly hashes.

The backend already checked static `.spad` extent plus its parsed kernel stack.
Patch 0003 exposes this evidence rather than substituting the three logical
array sizes. The allocation manifest includes every nonempty ELF scratchpad
object, offsets, padding, lifetimes and the kernel stack. It is emitted before
capacity rejection so a failed compilation can be classified as capacity failure.
The supported scope has X/W/Y globals and a kernel without calls. Its static
objects live for the whole kernel. The wrapper executes outside the NPU kernel;
DMA tags/queues are separate backend resources. This is a pinned backend storage
certificate, not full-chip SRAM/area accounting or a universal stack theorem.

A second limitation matters: the original timing scheduler admits two outer
subgraphs and up to four tiles without capacity-aware buffer allocation.
Static-ELF feasibility therefore does not certify its overlap schedule. With
`serial_tiles: true`, patch 0003 uses one scheduler slot and admits one tile at a
time. The certificate applies to this serialized policy. With `false`, the old
overlap policy remains executable, but the evaluator reports
`capacity_not_certified` and withholds accepted performance metrics. It does not
silently serialize a request for overlap. Compare cycles only under the same
policy. The existing frozen fidelity runs remain observations under their
original policy; this interface does not retrospectively change them.

## Structured results

TOGSim now optionally writes `togsim-final.v1` JSON after a nonempty completed
trace: cumulative transactions, request size, channels, DMA instruction counts,
cycles, launch count and scheduling policy. It writes a temporary file and renames
it only after serialization. Invalid trace commands no longer silently continue.
The pilot cross-checks this native JSON against the final log and independent
compiled-DMA ledger. Native JSON absence or disagreement rejects the evaluation.

`evaluation.json` is the single admission result. It separates subprocess exit,
validation failures, unsupported requests, capacity rejection, and unknown
capacity. Raw compiler/simulator/audit outputs remain separate evidence.
Only accepted results contain performance `metrics`; rejected runs may retain
`diagnostic_cycles`. Costs include total evaluation wall time, mapping selection,
functional simulation, gem5 compute modelling, TOG timing simulation and audit.
The residual compile/execution time is labelled as such, not pure compiler time.

```sh
python3 -m research.dnn_benchmarks.interfaces.evaluate \
  --request request.json --bundle "$RUNTIME_BUNDLE" \
  --source-overlay "$INTERFACE_BACKEND" --out "$FRESH_RESULT"
```

Apply the tracked patches in order to a writable runtime source copy and rebuild
Simulator. `interfaces_backend_lock.json` pins source, dependencies and binaries;
original runtime and repaired-pilot copies are left available for reproduction.

## Candidate evaluation

```sh
python3 -m research.dnn_benchmarks.interfaces.batch \
  --requests candidates.json --bundle "$RUNTIME_BUNDLE" \
  --source-overlay "$INTERFACE_BACKEND" --out "$FRESH_BATCH" \
  --wall-budget-seconds 600
```

Candidates must refer to the same operator, workload and hardware and have unique
mapping IDs. They are evaluated serially, with failures charged and every outcome
retained. No `(capacity, traffic)` deduplication is applied. The report contains
best-observed cycles versus elapsed time, not global latency optimality.
The budget is an admission deadline: no new candidate starts after expiry;
in-flight work can finish later and all of its cost is charged. Per-process
simulation timeouts are separate.

The independent Graph Witness-to-TOG exporter remains the next implementation
stage. Existing `sram_alloc` cache-plan attributes do not provide that semantics.

Server validation and archived evidence are in
[PYTORCHSIM_INTERFACE_RESULTS.md](../PYTORCHSIM_INTERFACE_RESULTS.md).
