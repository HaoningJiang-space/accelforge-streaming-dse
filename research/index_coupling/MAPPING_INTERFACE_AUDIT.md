# Independent PyTorchSim mapping-interface audit

The pinned external JSON selects GEMM tile candidates; it does not import an
execution witness. A pilot must verify the actual selected tuple and generated
execution, including loop order, residency, allocation, partial sums and DMA.

This source-only audit reads the existing integration branch's vendor tree
without modifying that branch, its runtime or its jobs. The audited upstream
revision is `509f42554202edb29cf8d31ddf619776f465e717`; seven source files are
checked byte-for-byte against that commit and their SHA-256 hashes are saved.
The original `select_tile` function is executed in isolation with a recording
kernel stand-in. This tests selector behavior, not compilation or TOGSim.

## 1. Eight reproducible selector probes

The shape is (M,N,K)=(64,128,32). The requested named values are
(TILE_M,TILE_N,TILE_K,SUB_TILE_M,SUB_TILE_N,SUB_TILE_K)=(16,32,8,8,16,8).

| Probe | Observed selector behavior |
|---|---|
| Six fields in the expected order | Returns exactly that six-tuple |
| Same named values, TILE_K before TILE_M | Returns (8,32,16,8,16,8) |
| Serialize with `sort_keys=True` | Also changes the returned tuple |
| Shape key absent | Calls the heuristic fallback |
| Three fields, subtile option enabled | Returns two candidates: full subtiles and computed subtiles |
| Six fields with TILE_M=0 | Returns the zero tile without validation |
| Six fields with SUB_TILE_M>TILE_M | Returns the oversized subtile without validation |
| Four fields | Raises UnboundLocalError |

The causes are directly visible in the pinned
[selector](https://github.com/PSAL-POSTECH/PyTorchSim/blob/509f42554202edb29cf8d31ddf619776f465e717/PyTorchSimFrontend/mlir/mlir_gemm_template.py#L311):
it unpacks `tile_info.values()`, and the six-field path returns before the
later candidate/subtile processing. Later compiler stages may reject invalid
geometry; this audit does not claim those invalid candidates execute.

`canonical_request` in the audit script provides a conservative pilot serializer:
all six named integer fields, canonical insertion order, positive dimensions,
tiles dividing dimensions and subtiles dividing tiles. These are pilot scope
restrictions, not a claim that the backend never supports tails. They do not
certify SRAM fit, array utilization, fusion choices or execution equivalence.
The JSON writer must preserve that order. A missing shape must be treated as
an audit failure even when upstream intentionally permits fallback.

The file key is M_N_K, with no operator identity. Two same-shape GEMMs requesting
different mappings cannot be expressed in one such mapping file. The pilot
should isolate them or explicitly check consistency; silent last-write-wins
construction would lose one request.

## 2. What the template commits to

In the plain no-bias, no-fusion
[GEMM template](https://github.com/PSAL-POSTECH/PyTorchSim/blob/509f42554202edb29cf8d31ddf619776f465e717/PyTorchSimFrontend/mlir/mlir_gemm_template.py#L14),
the outer loops are M, then N, then K. X and W loads occur inside K; Y is
initialized before K, accumulated through it and stored afterwards. The
reduction-epilogue template has a different outer order. External tile numbers
do not choose arbitrary loop permutations or cross-operator retention scopes.

Before transformations, for divisible tiles and b-byte elements, the plain
template implies

    MACs = M N K,
    Q_useful = b [M K (N/T_N) + K N (M/T_M) + M N],
    C_logical = b [T_M T_K + T_K T_N + T_M T_N].

The symbolic K loop has no partial-sum DRAM reads/writes. At the probe shape,
tiles (16,32,8), and b=4, the source ledger gives 262,144 MACs, 131,072 useful
bytes, 3,584 logical buffer bytes, and 144 source-level DMA operations.
These are analytic counts of the template, **not simulator measurements**.

The distinction matters even at tiny sizes: a 2x2x2 GEMM with unit tiles
transfers 20 useful elements in this template, although the three full tensors
contain only 12 elements. A unique-tensor-size sum would miss repeated input
loads. Conversely, compiler reuse passes could change the generated traffic;
the source ledger must then be reconciled with the transformed execution.

Logical occupancy also is not the physical allocation. The pinned
[buffer allocator](https://github.com/PSAL-POSTECH/PyTorchSim/blob/509f42554202edb29cf8d31ddf619776f465e717/PyTorchSimFrontend/mlir/mlir_codegen_backend.py#L1432)
uses lane-dependent sizing and a minimum of two elements per lane. Layout,
padding, precision and any additional in-flight buffers must be counted at
the actual allocation level before claiming a capacity match.

## 3. Acceptance contract for the integration owner

The existing integration branch's EVALUATION.md already separates search
quality, hardware quality and energy evidence. This audit adds concrete checks
to its pilot, without starting a second integration implementation:

1. Save the six-field request and verify the selected candidate tuple. Detect
   shape misses, ambiguous same-shape requests, and unexpected templates/fusion.
2. Save generated IR/TOG, layout/byte addresses and allocation ranges. Compare
   loop order and trip counts, not merely tile extents or the shape-key hit.
3. Reconcile each DMA region with useful tensor cells, padding and repeated
   accesses. Keep useful bytes, DMA bytes and DRAM transaction bytes separate.
4. Trace output initialization, each K contribution, residency through K and
   the final store. Verify dependencies and numerical outputs before timing.
5. Charge real SRAM allocations, including lane padding and any overlap
   buffers. A serial graph witness does not implicitly authorize extra buffers.

The [TOG generator](https://github.com/PSAL-POSTECH/PyTorchSim/blob/509f42554202edb29cf8d31ddf619776f465e717/AsmParser/tog_generator.py#L90)
has explicit DMA addresses, tile/loop strides, element sizes, async flags and
wait tags. A witness-to-TOG translation must supply these semantics and their
dependency relations. An aggregate traffic count cannot supply them.

The current capacity/traffic frontier also is not an exact latency frontier:
discarded or tied witnesses may have different hardware utilization or overlap.
A pilot may report the best of evaluated candidates; hardware-optimality claims
require an objective-compatible dominance rule or a broader candidate pool.
This is already stated by the integration contract and remains essential.

## 4. Evidence and reproduction

[mapping.json](results/independent_contract_audit/mapping.json) contains all eight
input files, selected tuples/exceptions, fallback counts, the stand-in's exact
behavior and source digests. Seven local controls also test the source-independent
serializer, ledger and scheduling oracle. This audit produces no compiled
binary, TOG execution, latency, energy, EDP or measured speedup.

```sh
python3 -m research.index_coupling.audit_mapping_interface \
  --source PATH_TO_PINNED_PYTORCHSIM --out NEW_MAPPING_AUDIT.json
PYTHONHASHSEED=0 python3 -m unittest research.index_coupling.test_independent_contract_audit
```
