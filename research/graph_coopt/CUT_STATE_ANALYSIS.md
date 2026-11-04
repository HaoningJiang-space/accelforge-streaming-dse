# Cut-state sufficiency experiment

This is a **counterexample and opportunity audit**, not a new Memo, optimizer,
cross-architecture reuse algorithm, or safe substitution theorem. The FFM
generation, numeric Join, reservations and Pareto implementations are unchanged.

## Protocol

Use real `matmuls(N,4,8)` on the fixed NVDLA topology, 8-bit values, and
Energy | Latency | Resource Usage with zero Pareto tolerance. Prepare each
architecture independently. Pause 2mm after Matmul0 and 3mm after
Matmul0 → Matmul1, save/resume the checkpoint, and retain exactly one prepared
suffix Einsum. Independently continue every cut row against that **same** suffix
catalog. Row isolation preserves the extended tensor ledger, release cursor,
resource-level dictionaries, source indices, context and remaining candidates.
It never reconstructs a partial state through the historical copy/update APIs.

Observe the native final numeric merge at two different boundaries:

1. Actual Pandas matched pairs, before resource/cost composition.
2. Composed, capacity-checked rows immediately before the merge's Pareto call.

The observer always invokes the original Pareto. It rejects a changed pipeline
with other than one pair-materializing merge and one terminal Pareto call per
numeric group merge. Streaming, row callbacks, multiple suffix Einsums and
parallel observation are outside this experiment. The CLI clears AF switches,
uses one worker and rejects nonzero tolerance.

A supported suffix means that its prepared source row has at least one
capacity-checked completion in this one-step continuation. Also retain its
effective, permuted numeric Compatibility as a binding ID. These are **not** all
physically legal mappings: upstream FFM generation and preparation have already
pruned candidates. Final Pareto suffixes are recorded separately and never used
as the feasibility oracle. Full and incremental E/T/resource responses are
compared separately; incremental E/T subtract inherited prefix cost. Cost
response comparisons use relative 1e-6, with complete-cost scale to avoid
subtraction cancellation. Exact resource bits remain integers, including above
2^53. Empirical dominance comparisons use non-relaxed componentwise comparisons.

## Interface ladder

Each level retains earlier fields. Keys are scoped to **one architecture and
one prepared continuation**. Equal hashes in different files do not establish a
shared context or cross-architecture plan.

| Level | Additional information |
| --- | --- |
| legacy_compatibility | FFM's equality tuple, with arbitrary symbolic column labels cleared as in native grouping; not all dataclass fields |
| numeric_compatibility | All Compatibility fields, including splits, with numeric TilePattern values |
| observed_copy_declarations | Extended tensor ledger and source storage/reservation declarations touching live tensors |
| boundary_loops | Source boundary loop prefixes, including unit loops, and current fused-loop numeric columns |
| resource_state | All reservation/capacity columns and tensor sizes |
| execution_contract | Release cursor, level dictionaries, aliases, continuation/liveness, generation provenance, tolerance and effective Join settings |
| cost_state | Remaining non-provenance row payload, including E/T |

Source IDs are retained for reconstruction but excluded from interface keys.
Copy declarations are observations of the FFM representation, **not** an
independent physical-copy/lifetime proof. Join has no RegionEnumerator-style
prefix-Pareto history list; the audit records the actual operation state and
upstream generation contract. This ladder is deliberately conservative and is
not claimed to be a minimal sufficient interface.

Every diagnostic run checks that observation leaves the complete ordinary
numeric frontier and Mapping identities unchanged. All distinct observed
completion cost/resource responses are reconstructed and re-evaluated on their
own architecture. Re-evaluation uses the existing FFM model, not an independent
physical simulator. Stored cut data and ledgers remain unchanged, and generation
is forbidden during row-isolated continuation probes.

## Results

Raw files and a compact summary are in [results/cut_state](results/cut_state).
Each architecture is a separate finite experiment. The primary 4×8 cases give:

| Cut / interface | 2mm, 96 B: groups / 30 rows | 3mm, 128 B: groups / 67 rows |
| --- | ---: | ---: |
| Legacy Compatibility | 11 | 4 |
| Numeric Compatibility | 15 | 5 |
| Add observed copies | 19 | 21 |
| Add boundary loops | 27 | 35 |
| Add full resource state | 30 | 67 |
| Add execution contract / cost state | 30 | 67 |

Numeric Compatibility alone has 3 and 198 same-key row pairs with different
supported suffix sets. Even after adding observed copies, there are 1 and 24
counterexample pairs. After loops, 3mm still has 20 such pairs. These are pair
counts, not numbers of unique bad mappings. Once the entire resource vector is
included, every group is a singleton. Zero counterexamples at that level are
therefore **vacuous**, not evidence of universal sufficiency.

One concrete 2mm witness is `g4r3` versus `g4r4` in
[2mm_4x8_96B.json](results/cut_state/2mm_4x8_96B.json). Their numeric Compatibility
and observed copy projection match. The first has GB right reservations 512/768
bits at levels 0/1 and no capacity-checked suffix completion; the second has
0/512 bits and supports suffix source rows 6 and 7. Lower prefix energy does not
make the first row a valid substitute for the second. Full typed interface
documents and exact source indices are retained for the witnesses.

The strict key becoming unique is negative evidence for **exact state
interning**, not a proof that conditional dominance is impossible. In the 3mm
4×8 case, for example, `g0r12` has historical GB left peak 640 bits and current
right demand 512 bits; `g0r8` has 576 and 768 bits. The prefix resource vectors
are incomparable. Yet for their shared prepared suffixes 6/7 the first completes
at 640 bits versus 768 bits, with lower energy and equal latency. It additionally
supports suffix 9. This is a specific finite continuation witness; it does not
prove the relation for an arbitrary future consumer or architecture.

## Post-hoc ceiling, not a deployable pruner

After paying for **all** row-specific continuations, an oracle-only ablation uses
the observed responses. Within the boundary-loop projection, every completion
of a removed row must have a same-suffix, same-effective-binding completion of a
retained row with no worse E/T/resource vector. Keep explicit witnesses and never
delete a witness used by another removal. Dead rows are not counted as dominance
wins. Resume the native engine once with this reduced cut and compare its whole
numeric frontier and source identities, not just best EDP.

For 3mm at 4×8/128 B, this removes 11 cut rows, of which 2 were already absent
before the ordinary numeric Join. Actual final matched pairs decrease from
130 to 107 (17.7%); capacity-checked occurrences decrease from 102 to 87. The
four numeric group merges, 17 post-local-Pareto occurrences, seven final rows,
numeric frontier and Mapping identities are unchanged. This is a small,
measured **remaining opportunity**, not an end-to-end speedup. Its witnesses
require target suffix enumeration; no search cost has been avoided by a usable
new algorithm. It cannot license dropping these states under other consumers.
The raw report's `actual_search_work_skipped = 0` refers to the ordinary
observational path; the separately labeled oracle ablation records its actual
post-hoc pair counts.

The audit also identifies empirical dominance pairs whose targets FFM already
removes before numeric Join. These are reported separately so native
consolidation/Pareto work is not attributed to a new method. Candidate row counts
or signature compression are not translated into speedup estimates.

The independent 8×4 check also finds only singleton groups after adding resource
state. Across the four cases, all **174** cut rows are analyzed and **410** distinct
completion cost/resource responses pass reconstruction and re-evaluation.

| Case | Cut rows / resource-state keys | Native final matched pairs | Post-hoc matched pairs | Removed rows entering native numeric Join |
| --- | ---: | ---: | ---: | ---: |
| 2mm, 4×8, 96 B | 30 / 30 | 48 | 48 | 0 |
| 2mm, 8×4, 96 B | 14 / 14 | 50 | 44 | 2 |
| 3mm, 4×8, 128 B | 67 / 67 | 130 | 107 | 9 |
| 3mm, 8×4, 128 B | 63 / 63 | 180 | 132 | 14 |

Every executed ablation retains the complete numeric frontier and exact Mapping
source identities. All still execute four numeric group merges. The 8×4 3mm
pair decrease is 26.7%; candidate generation has already been paid for and is
unchanged. These are independently checked point results, not one shared proof
over the two shapes or a measured improvement over the cross-architecture cache.

## Decision

The tested strict representation offers no exact state compression in the two
primary cases. A general GraphMemo or cross-architecture pruner is not justified
by these results. The useful remaining question is narrower: can the actual
reservation transfer operations prove the observed resource tradeoff safe for a
declared family of continuations **without enumerating them**? Any such rule must
then be compared against native consolidation/Pareto and the strong FFM cache,
including all analysis and candidate-generation costs.

Do not infer a universal interface theorem, complete physical Mapspace coverage,
cross-architecture correctness, or practical speedup from this experiment.
The row-by-row audit intentionally repeats work to detect counterexamples.

## Reproduce

From the repository root, with the same installed environment as the other
tracking audits:

```sh
python -m research.graph_coopt.cut_state_analysis --n 2 --capacity 96 --output research/graph_coopt/results/cut_state/2mm_4x8_96B.json
python -m research.graph_coopt.cut_state_analysis --n 3 --capacity 128 --output research/graph_coopt/results/cut_state/3mm_4x8_128B.json
python -m research.graph_coopt.cut_state_analysis --n 2 --shape 8,4 --capacity 96 --output research/graph_coopt/results/cut_state/2mm_8x4_96B.json
python -m research.graph_coopt.cut_state_analysis --n 3 --shape 8,4 --capacity 128 --output research/graph_coopt/results/cut_state/3mm_8x4_128B.json
python -m pytest -q research/graph_coopt/test_cut_state_analysis.py --disable-warnings
```

Per-case phase totals are diagnostics, including copies, signatures, repeated
continuations and reconstruction. They are not fair benchmark measurements.

The declared research regression (`research/tracking_audit`,
`research/streaming_join`, `research/graph_coopt`) passed **636 tests** in
207.04 seconds, including nine new audit checks. The log is retained in
`results/cut_state/regression.txt`. This is not an all-repository test claim;
the previously documented legacy `compatibility_util` collection issue is
outside that set. The raw artifact hashes match the saved implementation.
