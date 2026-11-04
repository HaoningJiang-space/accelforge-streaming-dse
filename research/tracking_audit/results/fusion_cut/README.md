# Inspecting real two-MatMul Fusion mappings at a candidate cut

This is a **structural and action audit**, not an FFM pruning implementation.
It follows the [restricted synthetic cut experiment](../graph_cut_bound/README.md)
with real reconstructed FFM mappings. The inspector always returns
`safe_to_prune = false`: it does not infer physical spill bounds from the Mapping
tree or from peak Reservation columns.

## What is inspected

[The inspector](../../fusion_cut_inspect.py) accepts only a root-level
`Sequential` with exactly two ordered branches, one `Matmul0` and one `Matmul1`
compute, no outer loop, no nested split/pipeline/Toll and no unknown surrounding
nodes. It records storage and reservation nodes associated with `T1` outside the
split and inside each phase, plus the loop descriptions. Anything else returns
`unsupported`. This identifies a syntactic producer/consumer ordering only;
workload access coverage, physical lifetime and availability of copies, aliasing,
other concurrent reservations, recomputation and in-flight transfers remain
unproved. Storage nodes describe placement, not a complete independent
byte-level liveness trace.

The audit builds the repository's two-MatMul workload and NVDLA architecture,
uses actual FFM `make_pmappings + join_pmappings`, then reconstructs **every
returned final row**. It re-evaluates each Mapping at its own physical capacity,
checks resource and array-shape feasibility, checks Energy and Latency to `1e-6`
relative tolerance, and compares all nonzero per-Tensor Action columns. Actions
are FFM model action counts. MainMemory defaults to one bit per action in this
configuration. The re-evaluation uses FFM itself and is not an independent
physical event trace or a proof of the complete original mapspace.

## Results

Single worker, array `4x8`, NVDLA fixed model, no template limit. The small case
is `matmuls(2,4,8)`, whose YAML gives a 32-byte `T1`; the larger case is
`matmuls(2,8,16)`, with a 128-byte `T1`.

| Workload | GB capacity | Final rows | Root sequential | Other structures, rejected | All reconstructed cost/actions match |
|---|---:|---:|---:|---:|---|
| Small | 68 B | 3 | 3 | 0 | yes |
| Small | 96 B | 6 | 6 | 0 | yes |
| Small | 128 B | 6 | 6 | 0 | yes |
| Larger | 512 B | 19 | 12 | 7 | yes |

In the small case, the 68-byte run has three root-sequential mappings with a
MainMemory `T1` holder. Each reports at least one full 32-byte write and one
full read. At both 96 B and 128 B, three further root-sequential mappings hold
`T1` in GlobalBuffer across the split, with **zero MainMemory T1 actions**.
At 96 B, the best re-evaluated EDP among MainMemory-holder rows is
`2.6308608e-16 J s`; among GB-holder rows it is `1.9103744e-16 J s` (about
27.4% lower). These mappings also differ in other decisions: this is an
observation, not a causal ablation of placement alone.

The larger case has nine root-sequential rows with a MainMemory `T1` holder,
three with a GlobalBuffer holder and no MainMemory `T1` actions, and seven rows
rejected because of an outer loop/other root structure. Those seven have zero
MainMemory `T1` actions in this model. In particular, neither a large whole-tensor
size nor the mere existence of a producer/consumer split proves a DRAM spill.
The inspector does not label the rejected rows with a validated streaming or
Fusion category.

GlobalBuffer's reported peak includes resource usage across lifetimes; it is
**not** a certified amount of unrelated occupancy simultaneous with `T1` at the
candidate cut. In particular, subtracting the tensor size from that peak would
not establish `C_free`. An action already counted as compulsory cannot also be
added as a separate spill lower bound without showing the traffic is disjoint.

Raw results include the Mapping structures, loop and copy context, each
per-row action count and validation result, and source hashes:
[small](audit.json), [larger](larger.json). All 34 returned rows re-evaluate
successfully. The 132 passing tests in [regression.txt](regression.txt) include
negative tests for loops outside the split, wrong order, additional compute,
trailing nodes and pipeline, the synthetic byte-level checks, and the earlier
Attention permutation and action regression. This is not a full repository test
run or a sampled proof over all physical configurations.

## Reproduce

```sh
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
python -m research.tracking_audit.audit_fusion_cut --output /tmp/fusion-cut-small.json
python -m research.tracking_audit.audit_fusion_cut --dimensions 8 16 --capacities 512 --output /tmp/fusion-cut-large.json
python -m pytest -q --disable-warnings research/tracking_audit/test_fusion_cut_inspect.py research/tracking_audit/test_graph_cut_bound.py research/tracking_audit/test_permuted_join.py
```

The next step is an independent per-event lifetime/occupancy account for the
actual mapping semantics, plus a proven branch-level cut contract. Until then,
no graph-bound certificate should prune FFM candidates or claim an EDP guarantee.
The four-way FFM/cached/retarget/bounded performance experiment remains open.
