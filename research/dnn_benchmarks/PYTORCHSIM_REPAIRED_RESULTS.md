# Repaired PyTorchSim: complete GEMM validation path

Update: the subsequent K=3072 scale-scan rejections came from our auditor
selecting interval counters. The backend completed correctly. See
[the parser correction and 15-run re-audit](PYTORCHSIM_INTERVAL_AUDIT_FIX.md).

The repaired path now executes external six-field GEMM mappings through code
selection, rendered MLIR, generated TOG, Spike functional execution and TOGSim
with an independent DMA ledger. The first matrix at `1860f851` has eight of eight
numerically correct runs, exact DMA instruction/transaction agreement, and
identical 736-cycle results for all four equivalent full-tile controls. The one-command rerun at `28dba658` also passes all eight cases, with the same
cycles and address-stream digests for each corresponding case. Thus **16/16**
GEMM runs pass; the 1,348-case object-code probe passes independently in both
rounds. These
are backend integration controls, **not a mapping-search speedup result**.

## Fixes and scope

The upstream submodule remains pinned and clean at `509f4255`. The official
runtime source is `f595cef7`; its only tracked difference from that pin was the
README. Two tracked patches are applied to a separate source copy:

1. Keep tensor byte bases separate from element offsets, and scale both loop and
   local element offsets correctly. Include all transaction blocks covering an
   element, including packed/straddling cases; use 64-bit outer-offset arithmetic.
2. Read external mapping JSON by field name and reject invalid geometry. With
   this compiler/DMA interface, split N/K subtiles must align to the 128-lane
   group. M splitting is supported. The formerly failing `(16,32,8,8,16,8)`
   tuple is **rejected**, not repaired into an executable tuple or silently
   rewritten. Legal N/K splits are tested below.

The unchanged LLVM, Spike, RAMulator and original Simulator hashes remain in
`backend_lock.json`; the repaired build is locked in
`repaired_backend_lock.json`. That lock is the pre-run build contract; validation
outcomes are separate records. The original failing runs remain in their
original result directories. The first build launch failed because it selected
`/usr/bin/cmake`; selecting `cmake` on the image PATH built Simulator successfully.

The actual rebuilt `Instruction.cc.o` passes **1,348** address checks against an
independent bit-by-bit oracle: bases above 4 GiB, unaligned bases, offsets above
2^31, 1/4/8/16/32/64/128-bit elements, three request sizes, broadcast/strided
accesses, indirect indices, and invalid-request handling. This does not certify
all sparse, negative-stride or extreme-overflow paths.

## Complete first matrix

All cases are float32, seed 0, tolerance `rtol=atol=1e-4`, with compiler
optimization `none`. Outer and subtiles are `(M,N,K)`. The hardware has one core,
two systolic arrays, 128 lanes, 128 KiB scratchpad per lane, 16 HBM2 channels and
940 MHz core/DRAM clocks. Transactions are 32 bytes. No energy model is used.

| Case | Shape | Outer tile / subtile | Cycles | DRAM reads / writes | Max absolute error |
| --- | --- | --- | ---: | ---: | ---: |
| Native heuristic | 64,128,32 | 64,128,32 / same | 736 | 768 / 1,024 | 3.82e-6 |
| Native autotune | 64,128,32 | 64,128,32 / same | 736 | 768 / 1,024 | 3.82e-6 |
| External full tile | 64,128,32 | 64,128,32 / same | 736 | 768 / 1,024 | 3.82e-6 |
| External small tile | 64,128,32 | 16,32,8 / same | 8,774 | 3,072 / 1,024 | 7.63e-6 |
| External M split | 64,128,32 | 16,32,8 / 8,32,8 | 9,233 | 3,072 / 1,024 | 7.63e-6 |
| External aligned N split | 16,256,16 | 16,256,16 / 16,128,16 | 597 | 544 / 512 | 1.91e-6 |
| External aligned K split | 16,32,256 | 16,32,256 / 16,32,128 | 637 | 1,536 / 64 | 2.29e-5 |
| Full-tile fresh repeat | 64,128,32 | 64,128,32 / same | 736 | 768 / 1,024 | 3.82e-6 |

All output elements pass. All output regions are written exactly once. The
ledger checks bounds, load-tag reuse (including rejection of tag collisions
covering different regions), emitted DMA counts, and unique request blocks per
DMA. Its transaction counts equal the actual logs in every case. For autotune,
only one candidate was available; two runtime attribute records exist, and the
selected timing trace identifies the final invocation. No claim about broad
native autotuning quality follows from that control.

Timing uses explicit, nonoverlapping tensor bases at 0x10000000, 0x20000000 and
0x30000000. This affects TOG timing metadata only; Spike still computes with its
actual data. Identical physical layouts remove ASLR as a source of variation
between mapping controls. Address placement is part of this experiment's
contract, not a hardware-calibration result.

Small-tile and M-split cases both transfer 131,072 useful bytes, yet take 8,774
and 9,233 cycles. Full tile transfers 57,344 useful bytes and takes 736 cycles.
This demonstrates why useful bytes alone are insufficient to predict latency.
These manually selected controls do not establish an advantage for our solver.
Static generated float-array reservations also include lane padding: they are
not interchangeable with the solver's logical buffers, nor a complete measured
peak SRAM including tags and overlap buffers.

## Reproduction and acceptance

Build the overlay as described in `patches/README.md`, then run on the verified
Linux rootless runtime (all paths supplied explicitly):

```sh
python3 -m research.dnn_benchmarks.run_pytorchsim_validation \
  --bundle "$RUNTIME_BUNDLE" --source-overlay "$REPAIRED_SOURCE" \
  --out "$FRESH_OUTPUT_DIRECTORY" --seconds 600
```

This runs the object-code address probe, eight fresh bounded simulator
invocations, per-run DMA audits, and equivalent-mapping cycle/address checks.
Outputs are never overwritten. Unit checks include 720 JSON field-order
permutations, illegal and legal geometry, archived compiler controls, and
injected incorrect traffic/tag collisions:

```sh
python3 -m unittest research.dnn_benchmarks.test_mapping_contract \
  research.dnn_benchmarks.test_repaired_selector \
  research.dnn_benchmarks.test_dma_ledger
```

Artifacts in `results/pytorchsim/1860f851` preserve numerical arrays, inputs,
outputs, MLIR, TOG, allocation headers, hardware configuration and logs. Raw
`result.json` files retain their pre-ledger pending status; `dma_score.json`
records the subsequent acceptance. The fresh one-command validation is in `results/pytorchsim/28dba658`; its
`summary.json` reports `passed: true`, and `archive_sha256.json` verifies all
159 copied evidence files. All eight unit tests also pass on the server. Build
logs, including the first launch failure, are preserved under
`results/pytorchsim/repaired_build`.

## Research consequence

This unblocks a trustworthy **plain-GEMM interface pilot**. Full graph
Witness-to-TOG export, cross-operator residency/fusion and calibrated energy
remain separate work. Neither a whole DNN latency result nor an EDP result is
claimed. The next useful step is to export a small solver-selected graph with
explicit buffer lifetimes and compare its traffic to independent execution;
then scale to supported DNN islands. Search correctness, backend execution
correctness and physical hardware accuracy remain separate claims.
