# PyTorchSim evaluation interface validation

The first four interface components now run on the experiment server: explicit
hardware requests, strict mapping receipts, native cumulative statistics, and
budgeted candidate evaluation. This is a **plain-GEMM** integration. The Graph
Witness-to-TOG exporter, cross-operator Keep/Spill, and energy modelling are not
implemented by this change.

The implementation is integrated into `research/dnn-benchmarks`, based on
`77b737df`. The temporary interface branch has been retired. The frozen 100-run
fidelity experiment and its backend were left
unchanged. See [the API documentation](interfaces/README.md) for supported
capabilities and invocation examples.

## Validation results

| Check | Result | Evidence |
| --- | --- | --- |
| Request, mapping, DMA, statistics and candidate unit tests | 21/21 passed | [Unit output](results/pytorchsim/interfaces/unit_tests.txt) |
| End-to-end conformance cases | 11/11 expected outcomes | [Conformance summary](results/pytorchsim/interfaces/conformance_archive/summary.json) |
| Final verifier against nine executed cases and five corrupted-evidence cases | 14/14 passed | [Evidence checks](results/pytorchsim/interfaces/evidence_check.json) |
| Two-candidate batch, including a capacity failure | Both outcomes recorded; failure charged; valid candidate completed | [Batch summary](results/pytorchsim/interfaces/batch_archive/summary.json) |

The 11 conformance cases comprise seven accepted runs and four expected
rejections. Two invalid requests were rejected before launching a process. One
compiled candidate exceeded SRAM; one requested the original overlapping
schedule, for which the new interface cannot certify SRAM feasibility.

| Case | SRAM required / lane | Result | Cycles if accepted |
| --- | ---: | --- | ---: |
| Full tile, 1 KiB / lane | 800 B | Accepted | 736 |
| Same full tile, 512 B / lane | 800 B | Capacity exceeded | — |
| Full tile, original overlap policy | 800 B static requirement | Capacity not certified | — |
| Small tile, serialized | 320 B | Accepted | 22,394 |
| Native heuristic, serialized | 800 B | Accepted | 736 |
| Native autotune, serialized | 800 B | Accepted | 736 |
| Aligned N subdivision | 480 B | Accepted | 597 |
| Aligned K subdivision | 1,392 B | Accepted | 637 |
| Misaligned N subdivision | — | Invalid request | — |
| Unsupported dtype | — | Invalid request | — |
| 128 × 256 × 3072, serialized | 38,112 B | Accepted | 13,906 |

For the last case, native cumulative statistics report **147,456 read and 4,096
write transactions**, each 32 B, matching the compiled-DMA audit. It is a valid
large-K case under this backend and policy. The earlier apparent count truncation
was a log-parser issue; it is not evidence of a simulator K limit.

The corruption checks remove native JSON, truncate it, change a transaction
count, change the allocation total, or change the applied hardware configuration.
All five are rejected and provide no accepted performance metrics. The final
verifier also checks that allocation manifests match the actual compiled ELF and
assembly, and that the requested hardware overrides occur in the applied YAML.

## What the SRAM certificate means

The full tile uses 640 B of static scratchpad extent plus 160 B of kernel stack
per lane. Reporting only the three logical arrays would miss the stack. The
allocation receipt exposes object offsets, sizes, padding and lifetimes, and
binds them to compiled artifacts.

The original timing scheduler admits multiple subgraphs/tiles without a dynamic
buffer-capacity allocator. A static single-kernel allocation check cannot prove
that overlapping execution fits SRAM. The new opt-in `serial_tiles` policy uses
one scheduler slot and one admitted tile. Only this policy currently receives
the pinned plain-GEMM backend storage certificate.

This restriction changes scheduling and can change cycles. These results must
not be mixed with the original overlapping-policy results in a speedup plot.
The certificate excludes wrapper execution, DMA queues/tags and general
full-chip resource accounting. It is not a physical optimality claim or an
independent hardware calibration.

## Candidate cost accounting

The batch compares two mappings for the same GEMM with a 512 B/lane serialized
configuration. The full tile is rejected because it requires 800 B/lane. Its
4.552 s evaluation cost is charged. The small tile requires 320 B/lane, completes
in 4.594 s evaluation wall time, and reports 22,394 simulated cycles. Total batch
elapsed time is 9.151 s, including orchestration.

These are single-run interface checks, not search-speed measurements. The best
result is explicitly labelled **best among accepted evaluated candidates**. No
candidate is removed merely because its capacity/traffic pair matches another
candidate. The wall budget stops admission of new candidates; in-flight work may
finish past the deadline and is fully charged. This does not implement a hard
wall-clock cutoff or prove globally minimal latency.

## Reproducibility

- Conformance execution: `33898513acf3a3838dc2e1a9e1256a0e19751c03`.
- Candidate batch and 21 tests: `f709f84d81c5a5ef29c59ba5da7f67d59d398dfe`.
- Final evidence verifier: `c77c1cdf748e9807515bc7aa611b7a29fb78a6ed`.
- Upstream source: pinned Git submodule `509f42554202edb29cf8d31ddf619776f465e717`.
- Runtime base: `f595cef7a367c57f4da9f1ba36d994c1f42242bf`; the pre-patch
  code audit found only the documented README difference from the source pin.
- Backend changes: tracked patches 0001–0003, dependencies and binary hashes in
  [interfaces_backend_lock.json](interfaces_backend_lock.json).
- Simulator SHA-256:
  `5a1db32be6b3f444f5415ab591f0089286b1b8f5912100c30758eac171e33a0b`.
- [Compressed build log](results/pytorchsim/interfaces/backend_build.log.gz),
  uncompressed SHA-256:
  `91e05ef0ac11b65f5959e62dc0f3c9b7989d88818e000223efd155a40317afa6`.

The archives contain 232 conformance and 40 batch evidence files, each verified
against its archive SHA-256 manifest after transfer. They retain requests,
results, source/TOG/assembly, allocation symbols and receipts, native statistics,
DMA audits and numerical evidence. They omit executables, OCI host mounts and
compiler caches. The live ELF checks therefore require rebuilding or retaining
the server execution directories; this archive alone is not a binary replay
package. Original result files retain their original evaluator revision.

Next, Graph Witness-to-TOG needs explicit per-operator identity, buffer lifetimes,
partial-sum ownership and dependencies. The current single-GEMM request IDs do
not resolve upstream shape-key collisions inside an arbitrary compiled graph.
