# Reservation-scope event ledger for a restricted two-MatMul mapping

This is the first stage of the requested lifetime ledger. It emits and checks
**representative per-phase Reservation scopes**, not a cycle-accurate event trace
and not a physical proof of the producer/consumer cut. No FFM candidate is
pruned. The [previous structural audit](../fusion_cut/README.md) and
[synthetic cut bound](../graph_cut_bound/README.md) have distinct scopes.

## Representation and safety boundary

[Ledger](../../fusion_lifetime_ledger.py) accounts for explicit allocation IDs,
resource names and sizes in integer bits. It rejects duplicate allocations,
unknown releases, invalid sizes and unspecified resource capacities. An unknown
allocation stays unknown: if its known peers fit, status is `unknown`, not
`fits`; if the known peers alone exceed capacity, status is `exceeds`. Once a
peak has included an unknown allocation, the exact peak stays unknown even after
that allocation is released.

The restricted MatMul adapter walks the two root-sequential phases. It records
storage declarations (which do **not** themselves allocate), representative
loop and compute markers, untracked non-GB reservations, and GB reservation
allocations/releases. GB Reservation sizes are products of the current tile
shapes for the tensor's dense projection and its 8-bit value width. Releases
close a representative phase scope; they must not be read as evidence that a
physical copy crossing the phase boundary was freed.

The audit checks the actual FFM model inputs before invoking the adapter: exactly
two expected Einsums and tensor projections, output roles, unit instances,
8-bit data, non-persistent access, expected rank bounds and unit GlobalBuffer
bit scaling. It requires the earlier root-Sequential structural check, perfect
nested tiles, no duplicate tensor Reservation in a phase and no GB reservation
after a Spatial loop. Unsupported structures fail closed. This does not prove
that different tensor reservations cannot alias, that the assumed linear scope
interpretation describes actual time, or that all iteration-specific occupancies
are uniform on arbitrary workloads. Consequently phase peaks and capacity
statuses are **conditional** on these assumptions.

The Mapping-level entry point requires the contract metadata produced by the
model-input check. That metadata records assumptions; it is not a tamper-proof
proof token, an independent workload verifier, or authorization to prune.

At the boundary, both `globalbuffer_live_bits` and
`other_globalbuffer_live_bits` are explicitly `null`, status is `unknown`,
`cut_free_capacity_bits` is `null`, and `safe_to_prune` is false. A storage
node outside the Sequential split is not independently turned into a physical
allocation or a zero-cost transfer.

## Real mapping audit

The audit reruns `make_pmappings + join_pmappings` for the exact two workloads,
capacities and shape in the [previous audit](../fusion_cut/README.md). It matches
the multiset of reconstructed Mapping IDs, re-evaluates each Mapping at its
own target capacity, compares all per-Tensor actions and checks array/resource
feasibility. For the supported rows it compares the largest conditional
per-phase GB peak with the FFM-reported aggregate peak.

| Case | Returned rows | Phase ledger supported | Conditional phase peak matches FFM | Explicitly unsupported |
|---|---:|---:|---:|---:|
| `matmuls(2,4,8)`, 68 B | 3 | 3 | 3 | 0 |
| same, 96 B | 6 | 6 | 6 | 0 |
| same, 128 B | 6 | 6 | 6 | 0 |
| `matmuls(2,8,16)`, 512 B | 19 | 12 | 12 | 7 |
| **Total** | **34** | **27** | **27** | **7** |

The seven unsupported rows have an outer loop or other root structure outside
the current root-Sequential subset. Matching a scalar maximum does **not**
validate its implied timing, byte aliasing, or cross-cut occupancy; those remain
unknown even for the 27 matching rows. Re-evaluation uses the FFM model and is
not an independent physical simulation. Each row and each ledger event is
available in [audit.json](audit.json); code and previous-audit hashes are stored
in the file.

As one check at 96 B, a phase of a MainMemory-backed `T1` mapping accumulates
256 bits for `T0`, 256 for `W0` and 32 for `T1`, giving 544 bits (68 B). A
separate unit test enumerates the underlying dense index sets rather than using
the product expression. A GB-backed `T1` mapping reaches 768 bits (96 B) in
its representative phase. Neither value says how many bytes are available at the
inter-phase cut.

[Regression](regression.txt) reports 144 passing tests and covers explicit unknown allocations, known lower
bound overflow, duplicate/free errors, invalid contracts, perfect-tiling and
spatial-replication rejection, the cut classifier, the synthetic bound tests,
the historic Attention permutation/Action regression and fused reservations.
This is not a full repository test run.

## Reproduction

```sh
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
python -m research.tracking_audit.audit_fusion_lifetime --output /tmp/fusion-lifetime.json
python -m pytest -q --disable-warnings research/tracking_audit/test_fusion_lifetime_ledger.py research/tracking_audit/test_fusion_cut_inspect.py research/tracking_audit/test_graph_cut_bound.py research/tracking_audit/test_permuted_join.py research/tracking_audit/test_fused_reservations.py
```

Next work must resolve branch-to-branch copy identity, exact live values at the
boundary, overlapping reservations, aliasing and transfer/recomputation semantics
for supported mappings. Only then can any graph-cut lower bound be considered
for real FFM pruning or architecture-level performance experiments.
