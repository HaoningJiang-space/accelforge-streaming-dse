# Local mapping retargetability and Attention permutation repair

This experiment tests a narrower claim than an architecture-parametric mapper:
can a source shape's **retained local candidate catalog** construct the selected
winner of a different shape by changing a small, specified set of loop factors?
It does not measure search speedup, prove optimality, or implement a Memo.

Code base: `ef779da6` plus the numeric Join-permutation repair and audit scripts
in this commit. Both workloads use NVDLA, one worker, three 6,144-PE shapes
`16x384`, `32x192`, `64x96`, 8-bit Register, unchanged unit costs, exact resource
bits, and the existing conservative Fusion-template filter. No template count
limit. The extracted Attention softmax remains an elementwise cost proxy.
Timing in the raw files is an incidental single run, not a performance claim.
Regression: [369 passed](regression.txt), including exact per-tensor action
checks for both previously failing Attention selections.

## What was abstracted

The audit keeps the original local template, including unit loops. It compares:

1. `physical`: every numeric loop tile, storage/reservation position, tensor,
   fused-loop label and backing-copy label retained.
2. `spatial_only`: erase only Spatial-node tile values.
3. `factor_split`: allow an unfused Temporal/Spatial factor pair to change in
   a pure loop band; no storage or reservation may lie between the pair.
4. `storage_retile`: also allow that pair to straddle storage/reservation nodes.
   This changes the memory tile extents and therefore requires fresh resource
   and cost evaluation. Storage positions and all fused-loop values stay fixed.
5. `template`: erase all numeric loop tile values, including fused values. This
   is a structural overlap diagnostic **only**, not a safe-substitution key.

For NVDLA, a frequent representation is `T n=128 -> S n=1`: spatial extent is
128, so erasing only the Spatial-node number misses the changing decision.

Binding alternatives enumerate perfect divisors using source structure and
target per-dimension fanouts; they do not read target tile choices. The target
winner is subsequently used to identify a witness. This is an **oracle-assisted
retrospective experiment**, not an algorithm that discovers the winner cheaply.
Every successful witness is reconstructed from transformed **source** locals and
re-evaluated on the target architecture, including exact capacity and separate
spatial-dimension checks. Source model costs are not reused.

## Results

MatMul is a three-layer 256x256 chain, queried at 128, 132, and 256 KiB, from
one complete GlobalBuffer/energy/latency search at 256 KiB per shape. Attention
is QK -> QK_softmax -> AV with 128 tokens, one head and head width 64; query
capacities are 8, 24, 32, and 128 KiB, generated at 128 KiB.

| Transformation | MatMul cross-shape winners recovered | Attention recovered |
|---|---:|---:|
| Pure-band `factor_split` | 0 / 18 | 0 / 24 |
| `storage_retile` | 11 / 18 | 2 / 24 |

Each denominator is six directed source/target pairs times the workload's
capacity count; these are not independent or necessarily unique mappings.
Identity controls recover all 9 MatMul and all 12 Attention picks, in both modes.

`storage_retile` matrix (row = source, column = target; diagonal is control):

| MatMul | 16x384 | 32x192 | 64x96 |
|---|---:|---:|---:|
| 16x384 | 3/3 | 2/3 | 0/3 |
| 32x192 | 3/3 | 3/3 | 1/3 |
| 64x96 | 2/3 | 3/3 | 3/3 |

| Attention | 16x384 | 32x192 | 64x96 |
|---|---:|---:|---:|
| 16x384 | 4/4 | 0/4 | 2/4 |
| 32x192 | 0/4 | 4/4 | 0/4 |
| 64x96 | 0/4 | 0/4 | 4/4 |

Across directed pairs, ignoring all numeric tiles yields template overlap of
86.8–100% of target local rows for MatMul and 91.9–99.8% for Attention. This high
overlap is **not** equivalent to high optimal-plan coverage: storage extents,
fusion tiles, and spatial factors remain coupled choices within a template.

Limits: catalogs are post-pruning; loop order is preserved literally; only one
selected optimum per target is checked, and earlier tie pruning may select a
different identity. Failure to recover that identity does not prove a quality
gap or impossibility of another transformation. `storage_retile` is not a general
retile/copy enforcer and does not change storage placements or fusion boundaries.

The evidence favors testing shared **symbolic constraint subproblems** before
shape-specific pruning. It does not yet justify building a general Memo engine
or claim that a common template eliminates per-shape optimization work.

Raw results: [MatMul](matmul.json), [Attention](attention.json).

## Attention failure: exact action-level explanation

The previous 8/24 KiB, 64x96 failures first diverge during `_merge()`, before
copy elevation or reservation propagation. Structural grouping chooses a loop
permutation, but the old numeric Join used the original, unpermuted
compatibilities. It matched different axes' tile values, accepting QK `p64,m32`
against QK_softmax `m64,p32`. Reconstruction then co-iterated the wrong ranks.

For each failed mapping, re-evaluation adds these QK actions relative to search:

| Component / tensor / action | Extra transferred bits |
|---|---:|
| MainMemory / K / read | 65,536 |
| MainMemory / Q / read | 131,072 |
| GlobalBuffer / K / write | 65,536 |
| GlobalBuffer / Q / read | 131,072 |
| GlobalBuffer / Q / write | 131,072 |

Thus the DRAM discrepancy is exactly 24 KiB, contributing 0.640 microseconds
at 38.4 GB/s. DRAM plus GlobalBuffer energy accounts for approximately 1.472397
microjoules. It is not evidence of an extra QK_softmax materialization.

The repair passes the selected permutation to numeric matching too, without
mutating groups reused by other Join tasks. It does not drop problematic
templates or disable permutations. Both repaired picks retain the same reported
Energy/Latency as before, but now reconstruct into matching actions and costs.
All per-tensor action counts agree exactly; floating costs use the pre-existing
1e-6 relative re-evaluation criterion. No tolerance was relaxed.

The legacy replay is scoped to search, using the former unpermuted numeric
matching. Stage-by-stage reconstruction is then measured with the repaired
evaluator. See [legacy trace](attention_actions_legacy.json) and
[fixed trace](attention_actions_fixed.json). This repairs the demonstrated
permutation bug; it does not resolve every Fusion Copy completeness issue.

## Reproduce

```sh
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
python -m research.tracking_audit.audit_attention_actions --legacy-matching --output /tmp/legacy.json
python -m research.tracking_audit.audit_attention_actions --output /tmp/fixed.json
python -m research.tracking_audit.retarget_local_mappings --output /tmp/matmul.json
python -m research.tracking_audit.retarget_local_mappings --workload attention --params 128,1,64 --capacities-bytes 8192,24576,32768,131072 --output /tmp/attention.json
python -m pytest -q --disable-warnings research/tracking_audit research/streaming_join
```

## Interpretation of the proposed Memo direction

[Cascades](https://15721.courses.cs.cmu.edu/spring2019/papers/22-optimizer1/graefe-ieee1995.pdf)
separates equivalent expressions from required physical properties. For this
project, a common expression/template should not imply one cached answer:
optimization contexts still need architecture constraints and required tensor
interfaces. [MPQO](https://www.vldb.org/pvldb/vol8/p221-trummer.pdf) requires safe
subplan replacement for its pruning argument. The missing domain-specific step
is showing which mapping boundaries permit that replacement or a priced
conversion. Template overlap alone does not establish it.
