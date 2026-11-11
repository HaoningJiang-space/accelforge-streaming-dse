# ResNet heuristic DMA rejection: declared bounds versus validation allocation

This is a post-hoc diagnosis of the two excluded heuristic runs from the
`77b737df` fidelity experiment, reported at `fcd8f1c6`. No simulator rerun,
backend patch, new timing result, or change to the frozen H1–H4 scores is made.

**The rejection is correct for the declared logical-tensor contract.** The
heuristic chooses a row-padded full tile. Its DMA actually includes the extra
rows, rather than clipping them. The functional validation wrapper allocates
approximately twice each tensor's logical storage, so these particular DMAs
fit inside that enlarged allocation. This is neither evidence of an allocation
overrun in these two validation runs nor an explicit padded-storage contract
for the timing interface.

## Evidence chain

The archived artifacts in `results/resnet_tail/` include the generated MLIR,
TOG, validation wrapper, logical address-layout receipt, static SRAM arrays,
runtime attribute, and completed timing log. `diagnosis.json` records SHA-256
hashes of every input artifact and is reproducible without PyTorch or a server.
The original simulator binary hash and backend lock remain in each result.

| Case | Logical M | Heuristic TILE_M | Extra input read | Extra output write |
| --- | ---: | ---: | ---: | ---: |
| ResNet stage 2, (3136,256,64) | 3136 | 3200 | 16,384 B | 65,536 B |
| ResNet stage 3, (784,512,128) | 784 | 896 | 57,344 B | 229,376 B |

1. The original MLIR declares **logical** argument lengths. For stage 3 these
   are X=100,352, W=65,536, and Y=401,408 float32 cells. SRAM buffers and DMA
   subtiles instead contain 896 rows. `padding=0` supplies no new DRAM storage
   contract; the argument lengths remain unchanged.
2. The emitted TOG has dense, origin-zero DMA rectangles of `(TILE_M,K)`,
   `(K,N)`, and `(TILE_M,N)`. Each occurs once: two loads and one store. The
   diagnostic verifies this structure before applying its full-tile formula.
3. TOGSim's completed transaction counters match the **full padded rectangles**
   exactly, and disagree with hypothetical clipped rectangles. Request size is
   32 B; all these ranges are aligned. This rules out unobserved tail clipping
   as an explanation of the timing logs.

| Case | Observed / full-tile read transactions | Clipped reads | Observed / full-tile writes | Clipped writes |
| --- | ---: | ---: | ---: | ---: |
| stage 2 | 27,648 | 27,136 | 102,400 | 100,352 |
| stage 3 | 22,528 | 20,736 | 57,344 | 50,176 |

4. The generated `validation_wrapper.c` allocates `2 * ceil(logical_bytes/64)
   * 64` per argument, matching `MLIRKernelCallerCodeGen.generate_args_define`
   in the pinned frontend. For stage 3, X gets 802,816 B and Y gets 3,211,264 B,
   while their full DMAs cover 458,752 B and 1,835,008 B. Both fit the enlarged
   malloc. The wrapper loads only the logical input prefix and dumps only the
   logical output prefix. It does not initialize the extra input rows in the
   generated wrapper, nor check the output tail for modification.
5. Both frozen runs report `numerical_equal=true` and zero wrong logical
   elements. GEMM rows are independent: extra M rows need not alter the valid
   output prefix. Thus numerical equality does not certify the DMA contract.
   We did not instrument functional memory accesses or run a canary test; the
   byte-exact full-tile traffic evidence is the TOG plus timing counters.

The SRAM lane-padding formula and these DRAM row extensions describe different
storage. A larger SRAM array cannot authorize accesses beyond a DRAM tensor.
Likewise, the timing harness's separated virtual base addresses prevent aliasing
between arguments but do not establish ownership of bytes beyond their receipts.

## Resolution and scope

Keep the two heuristic runs excluded. `audit_repaired_dma.py` still fails closed,
now with tensor, DMA node, direction, tile, loop indices, and exact enclosing
cell/byte interval. It checks affine extrema before constructing the per-cell
ledger. `run_rootless_pilot.py` preserves these details in new rejection records.
Existing archived records and experiment scores are not rewritten.

The separate diagnostic intentionally never returns `timing_accepted=true`.
Its full-tile counter match is explanatory evidence, not a relaxed acceptance
mode. Regression checks cover both archived cases and strided interval bounds;
the five existing accepted compiled controls remain accepted.

A future backend change must choose and implement an explicit contract:

- **Tail DMA:** carry logical extents through lowering/TOG and clip or mask tail
  loads and stores consistently in functional and timing execution.
- **Padded DRAM:** allocate and declare the padded input/output storage, initialize
  required padding, and count its transfer, footprint, and any conversion work.

Neither fix is implemented here. Silently accepting the wrapper's spare malloc
space or rounding the auditor's tensor size would hide the interface mismatch.
For the next timing-model holdout, keep this acceptance gate and declare the
tested tile legality domain; do not train a timing predictor on rejected runs.

## Reproduction

From the repository root, use a new output path:

```sh
python3 -m research.dnn_benchmarks.audit_gemm_tail \
  --runs research/dnn_benchmarks/results/resnet_tail --out /tmp/resnet-tail.json
python3 -m unittest research.dnn_benchmarks.test_dma_ledger \
  research.dnn_benchmarks.test_togsim_statistics -v
```

This closes the cause-of-rejection question; it does not open another mapper
optimization branch or change the pinned simulator used by the fidelity study.
