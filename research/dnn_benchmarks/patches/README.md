# Experimental PyTorchSim repair overlay

Apply in filename order to the pinned submodule (509f4255), or the verified
runtime source f595cef7 (only README differs before patches). Preserve the
original source and binary. These are local research patches, not upstream fixes.

```
git apply /study/research/dnn_benchmarks/patches/0001-togsim-byte-addresses.patch
git apply /study/research/dnn_benchmarks/patches/0002-external-gemm-contract.patch
cmake --build TOGSim/build --target Simulator -j 6
```

The runtime image includes a configured build directory. Inside that image,
mount a writable copy at `/workspace/PyTorchSim` before building, retaining its
nested dependencies. `repaired_backend_lock.json` records the resulting source
and binary hashes. No compiler/Spike/DRAM model upgrade is included.

Patch 1 separates byte bases from element offsets, scales the combined element
index once, covers straddling/packed elements, and avoids signed intermediate
multiplication for outer offsets. Scope: direct positive-stride DMA used by the
pilot; a unit probe also covers indirect indices. This is not a general audit of
all sparse or negative-stride operations.

Patch 2 reads JSON fields by name, checks divisible geometry, and rejects partial
lane-group offsets in N/K. It does not change requested mappings or claim to
make the previously failing misaligned tuples executable. Missing-shape fallback
and three-field candidate generation retain upstream semantics; the pilot uses
an exact six-field shape guard and verifies selection and rendered code.

For the opt-in evaluation interfaces, additionally apply
`0003-evaluation-interfaces.patch` after patch 2 and rebuild Simulator. This adds
native final-statistics JSON, compiled allocation receipts, exact byte-capacity
configuration and the explicit serialized tile policy. Use
`interfaces_backend_lock.json` for this backend. Do not substitute it silently
into the frozen fidelity experiment: scheduling policies must match in timing
comparisons. See [interface results](../PYTORCHSIM_INTERFACE_RESULTS.md).
