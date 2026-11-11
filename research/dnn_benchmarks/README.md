# DNN relevance and hardware-validation branch

This branch starts a real-model coverage audit and bounded mapping study. It
does not yet supply whole-DNN latency, energy, or a general scalable optimizer.
The prior P19 remainder experiment is separate, pinned to `4a91b6f4` / grammar
v1. This branch starts from `b69bf02e` and compares v1 and v2 explicitly.

## Model provenance and coverage

`frontends.py` uses PyTorch FX and meta shape propagation, without downloading
trained weights. ResNet-50 and ViT-B/16 use Torchvision 0.25.0 with PyTorch
2.10.0. The U-Net is our implementation of the original valid-convolution
2015 geometry (572x572 one-channel input, 388x388 two-class output,
64..1024 channels and cropped skip connections), not an unspecified modern
U-Net variant. Sources: [Torchvision ResNet](https://github.com/pytorch/vision/blob/v0.25.0/torchvision/models/resnet.py),
[Torchvision ViT](https://github.com/pytorch/vision/blob/v0.25.0/torchvision/models/vision_transformer.py),
[U-Net paper](https://arxiv.org/abs/1505.04597).

The inventory preserves every FX node, shape, parameter shape and unsupported
boundary. The resource IR admits linear contractions, ungrouped stride-one
1x1 convolutions, evaluation BatchNorm, addition and elementwise ReLU/GELU.
Evaluation Dropout/Identity are aliases. All admitted computation is given
an explicit **functional, out-of-place** execution contract. General spatial
convolutions, pooling, reshape/crop/concat, normalization reductions and opaque
MultiheadAttention remain barriers. Softmax is not replaced with a copy.

| Model | Parameters | FX nodes | Computational FX nodes | Barrier nodes | Longest admitted contiguous island |
| --- | ---: | ---: | ---: | ---: | ---: |
| ResNet-50 | 25,557,032 | 177 | 175 | 23 | 11 |
| U-Net 2015 | 31,030,658 | 127 | 53 | 34 | 2 |
| ViT-B/16 | 86,567,656 | 236 | 117 | 55 | 4 |

FX computational counts depend on leaf-module granularity: an opaque attention
module is one node, not one arithmetic operation. Linear bias adds an extra IR
operation. These counts must not be presented as comparable fused-kernel counts.

The 16/32/64/128-prefix audits record missing sizes and barriers. **None of
these tested prefixes is fully admitted by this IR.** Thus this milestone
cannot support a 128-operator real-DNN exact-search claim. MobileNet-v2 and
BERT/Llama are follow-up coverage targets, not measured models in this audit.

## Bounded first study

`run_islands.py` freezes six cases: a three-FX-op ResNet fragment and its
eleven-FX-op parent island, the first longest ViT MLP/residual island, and the
U-Net output island. The latter two use both original extents and explicitly
labelled extent-at-most-two controls; ResNet uses reduced extents here.
Reduced shapes are correctness/structure controls, never real-model latency
measurements. All island interfaces materialize inputs/outputs via DRAM;
their curves cannot be added naively to claim a whole-model optimum.

Two v1 arms compare DP with/without remainder+empty-group rules. Four v2 arms
compare DP, remainder+empty-group rules, C2, and their combination. Small reduced
cases additionally use literal partition enumeration. Equality is checked
**within** a grammar; across grammars the check is v2 weakly dominating v1.
Each worker gets 30 seconds and 2 GiB, with profiling enabled. These one-shot
shared-host measurements are not a search-speedup headline.

`c2.py` implements the all-kept-child lower-bound rejection from
`../index_coupling/GRAMMAR_V2.md`, as an opt-in AST adapter without editing the
shared core. It requires explicit v2 and exact frontiers, verifies source
anchors, and records bound queries and rejected choices. A lower-bound curve
never becomes a feasible witness. It maintains a Pareto incumbent while
checking masks, so timing effects include that maintenance cost. This study
does not combine C2 with the order-complete unified certificate wrapper.

`replay.py` executes the actual admitted pointwise semantics on deterministic
synthetic inputs, checks all arithmetic iterations, dependencies, allocation,
loads, stores and final outputs against untiled execution. A native PyTorch
linear+bias control also checks arithmetic semantics. Large original-shape
witnesses above 200,000 scalar steps are saved but explicitly **unreplayed**;
their search completion must not be counted as execution validation.

All current IR tensors and accumulators use float32; solver units are scalar
cells and traffic elements. Multiplication by four produces byte counts for
this contract only. Mixed-precision hardware needs separate accumulator,
operand and DMA sizing, not a blanket conversion factor.

## Reproduction

Use an isolated environment containing torch 2.10.0 and torchvision 0.25.0
for extraction. The server-side mapping/replay scripts use only Python's
standard library. They do not require torch or model weights.

```sh
python -m research.dnn_benchmarks.frontends --out NEW_INVENTORY_DIRECTORY
python -m unittest research.dnn_benchmarks.test_c2 research.dnn_benchmarks.test_frontends -v
python -m research.dnn_benchmarks.run_islands --prepare --manifest NEW_MANIFEST.json
python -m research.dnn_benchmarks.run_islands --manifest NEW_MANIFEST.json --out NEW_RESULTS_DIRECTORY
```

Preparation currently consumes the committed `results/fx_inventory` corpus.
It records source/inventory hashes and refuses source mismatch. New attempts
use new output directories. Frozen failures and unreplayed cases remain visible.
Hardware evaluation requirements and backend choice: [EVALUATION.md](EVALUATION.md).
The completed first study, including timeouts and unreplayed original shapes,
is reported in [RESULTS.md](RESULTS.md).
The separate grammar-v1 P19 timing rounds are reported in
[P19_SERVER_RESULTS.md](P19_SERVER_RESULTS.md), including all memory failures.

## Pinned simulator source

PyTorchSim is a Git submodule at `vendor/PyTorchSim`; its exact upstream commit
is recorded in the parent gitlink and `backend_lock.json`. Initialize it with
`git submodule update --init research/dnn_benchmarks/vendor/PyTorchSim`.
Adapters, configurations, source/image digests, and small result records belong
in this repository. Container layers, compiler caches, and large runtime builds
remain outside Git. `pull_pytorchsim.py` verifies the public OCI image blobs;
`--download-only` permits direct download on a different machine before copying
the verified layout to the execution host. The image source and binary identity
must still be checked before claiming a run uses the pinned source revision.
Optional `--range-mib 1 --range-workers 8` uses resumable bounded HTTP ranges
for slow large-blob transfers; final whole-blob SHA-256 verification is mandatory.
`pytorchsim_gemm_pilot.py` performs separate functional/timing GEMM runs with
native heuristic, native autotune, or explicit manual tiles. Eight actual runs
are archived in [PYTORCHSIM_RESULTS.md](PYTORCHSIM_RESULTS.md), including three
numerical failures. Independent checks of the generated DMA regions exposed a
backend byte-address mismatch, so hardware timing acceptance remains blocked.

The repaired PyTorchSim GEMM path and one-command validation are documented in
[PYTORCHSIM_REPAIRED_RESULTS.md](PYTORCHSIM_REPAIRED_RESULTS.md). P19 is finalized
separately in [P19_SERVER_RESULTS.md](P19_SERVER_RESULTS.md).
