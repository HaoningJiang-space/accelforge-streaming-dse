> Update: the separately patched backend now passes the complete GEMM pilot.
> See [repaired results](PYTORCHSIM_REPAIRED_RESULTS.md). This document preserves
> the original unmodified-backend findings and failures.

# PyTorchSim runtime and GEMM import checks

The pinned image now runs without root on the designated CPU host. The first
eight actual GEMM invocations produced **five numerical passes and three
failures**. Timing acceptance is blocked: the DMA audit also found a separate
byte-address mismatch in the pinned TOGSim implementation. None of these cycles
is accepted as a mapping-quality, latency-speedup, energy or EDP result.

The upstream submodule remains `509f425`; the OCI image contains Git revision
`f595cef7`. Of 347 tracked regular files, only README differs. All five nested
dependency Git revisions match and their tracked working trees are clean.
The image digest, compiler/simulator binary hashes, seven audited source hashes,
and Torch 2.8.0+cu126 identity are recorded in `backend_lock.json` and
`results/pytorchsim/runtime_audit.json`. This is image provenance, not a claim
of having independently rebuilt every binary.

## Independent audit incorporated

The independent audit at
[`7e03ab3b`](https://github.com/HaoningJiang-space/accelforge-streaming-dse/blob/7e03ab3b/research/index_coupling/MAPPING_INTERFACE_AUDIT.md)
identified order-dependent `tile_info.values()` unpacking. The adapter now
validates six named positive integers, canonical insertion order, shape-key
presence, tile divisibility, and subtile divisibility. It validates the serialized
file again at selection and checks selected tuples and rendered tile headers.
All 720 input field permutations select the same tuple in the original upstream
selector. Sorted serialization, missing shapes and invalid geometry fail closed.
This guards the import interface; it does not certify hardware legality.

The audit branch and upstream simulator source remain unchanged. Only the
integration adapter, tests, version record and artifacts changed.

## Actual functional results

All runs use float32, deterministic seed 0, shape (M,N,K)=(64,128,32), one core,
two systolic arrays, 128 vector lanes, 128 KiB scratchpad per lane, 16 HBM
channels, and 940 MHz. Compiler optimizations are explicitly `none`; functional
and timing modes are both on. These are manual import controls, not solver
generated optimum witnesses. Each invocation has a fresh compiler cache.

| Strategy / control | Outer tile M,N,K | Subtile M,N,K | Numerical result | Maximum absolute error |
| --- | --- | --- | --- | ---: |
| Native Heuristic | 64,128,32 | 64,128,32 | pass | 3.81e-6 |
| Native Autotune | 64,128,32 | 64,128,32 | pass | 3.81e-6 |
| External, native tuple | 64,128,32 | 64,128,32 | pass | 3.81e-6 |
| External, same subtiles | 16,32,8 | 16,32,8 | pass | 7.63e-6 |
| External, split M | 16,32,8 | 8,32,8 | pass | 7.63e-6 |
| External, split N | 16,32,8 | 16,16,8 | fail, all 8192 outputs | 35.96 |
| External, split M and N, two invocations | 16,32,8 | 8,16,8 | fail in both | 35.96 |

The requested six-tuple and rendered tile parameters were retained in the failed
runs. Thus field-order repair alone does not resolve execution correctness.
In these controls, changing SUB_TILE_N from 32 to 16 isolates the failure;
the underlying compiler/functional-simulator cause is not yet established.
This is not a theorem that every N-split mapping fails. The pilot defaults to a
passing tuple; N-split trials now require an explicit diagnostic flag and never
become accepted timing results merely because they compile.

The native heuristic and autotune select the same full-tile tuple on this tiny
case. Their functional passes do not establish a useful autotuning benefit or
whole-DNN support. Functional tolerance is rtol=atol=1e-4.

## Separate DMA address issue blocks timing acceptance

`audit_compiled_dma.py` expands the saved generated TOG for the case with
unit-trip inner loops. Every intended address lies within its tensor and every
output element is written once. It compares the byte contract to the actual
backend expression; it does not guess bytes from total tensor sizes.

Let B be a tensor's byte base, O its loop offset in elements, and L a local
tile offset in elements. For float32 the intended byte address is:

    B + 4(O + L).

The parser passes `base_addr + offset` without scaling the element offset.
`Instruction.cc` then evaluates

    address = dram_addr + (address * _elem_bits + 7) >> 3;

With C++ precedence this becomes `(B + O + 32L + 7) >> 3`, which also shifts
the byte base. The metadata contains ordinary byte pointers. The audit ports
this exact expression separately and obtains the same transaction counts as
the actual simulation log:

| Numerically passing case | Intended useful bytes | Correct 32-byte read/write transactions | Logged read/write transactions | Ported expression |
| --- | ---: | --- | --- | --- |
| Full native tuple | 57,344 | 768 / 1,024 | 768 / 1,024 | exact match |
| Tile 16,32,8; equal subtiles | 131,072 | 3,072 / 1,024 | 3,456 / 1,216 | exact match |

The full-tile count happens to agree despite incorrect absolute addresses; a
matching aggregate count alone cannot validate addresses. The tiled case shows
the mismatch in actual logged counts. The DMA audit is deliberately restricted
to unit-trip inner loops; split inner loops need a separate tag-lifetime audit.

Physical allocation also differs from the logical tile sum. The three generated
float scratchpad arrays reserve 20,480 bytes for the small-tile case, versus
3,584 logical bytes, owing to lane layout. The full-tile case reserves 81,920
bytes for these arrays, versus 57,344 logical bytes. These are generated array
reservations, not a complete measurement of peak SRAM including tags/overlap.

Cycles are retained in raw logs for debugging, but no speedup is calculated.
Runtime tensor addresses also differ between invocations and have not been
fixed as a timing control. Repair and revalidate address generation, allocation,
and transaction accounting before hardware comparisons. No upstream source or
binary has been patched by this pilot.

## Evidence

`results/pytorchsim/35e1c23c` contains the initial three invocations;
`results/pytorchsim/bfe11b77` contains the five isolation controls. Artifacts
include requests, selected tuples, generated MLIR/TOG, allocation declarations,
input/output bytes, simulator logs, and numerical arrays for the isolation run.
Failures are retained. `dma_subtile_same.json` and `dma_native_tuple.json`
contain the address checks. The four adapter tests include the 720-permutation
control. These counts are separate from the independent audit's seven tests.

```sh
python -m unittest research.dnn_benchmarks.test_mapping_contract -v
python -m research.dnn_benchmarks.audit_compiled_dma \
  --run research/dnn_benchmarks/results/pytorchsim/bfe11b77/subtile_same \
  --source research/dnn_benchmarks/vendor/PyTorchSim --out NEW_DMA_AUDIT.json
```

Use `run_rootless_pilot.py --bundle ... --out NEW_DIRECTORY --mode ...` on a
Linux host with the verified runtime. Each invocation is bounded by 600 seconds.
Raw historical results retain their original `DMA ledger pending` status; the
separate audit above supplies the subsequent timing rejection.
