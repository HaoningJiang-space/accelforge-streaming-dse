# Partial-state interface audit after bfbb12a6

The bd39555f review predates the resumable Join engine in bfbb12a6. This change
checks the identified risks on that engine, fixes two concrete isolation/cache
issues and fills the shared-input metadata gap. It adds no optimizer, new
dominance, new graph order or cross-architecture inference.

| Reviewed issue | Resolution |
| --- | --- |
| `PmappingGroup.copy()` loses extended ledger/counts | Its historical reconstruction semantics remain. Checkpoint copying bypasses it and preserves all group fields; a test makes this method raise if the snapshot path invokes it. |
| DataFrame `copy()/update()` resets release progress | Their reconstruction semantics remain. Snapshot/resume retain `_prev_free_to_loop_index` and reservation dictionaries; a repeated release is verified to skip processing. |
| Liveness depends on the remaining workload | Already retained in PartialState's prepared continuation and strict JoinContext. A different graph, architecture, context or AF switches cannot resume the checkpoint. |
| Incomplete Compatibility equality | Unchanged and not used to decide checkpoint equivalence. Splits, loop order and full group state are retained even when equality ignores them. |
| Shared external Tensor has no producer edge | WorkloadDAG now retains all tensor users and external-input consumers. Boundary analysis includes this incidence without inventing a producer/ordering edge. |
| Compression mutates source indexes | It continues to operate on owned work copies. A regression verifies non-default source indexes are untouched when the working copy is compressed. |
| `tensor_names` becomes stale | Replaced its cached property with a live property over the mutable ledger. Addition, deletion and caller mutation of the returned set are tested. |
| Mutable objects inside Pandas cells escape `deepcopy` | New dedicated copying seeds a shared memo with all frames, then recursively copies object-dtype cells before copying group/state metadata. Source/checkpoint/resume objects are isolated while internal aliases are preserved. |

## What the tests establish

`test_state_snapshot_contracts.py` builds a representative state with:

- a ledger entry not present in live Compatibility;
- nonzero pre-pruning counts and an already executed release cursor;
- two loop positions, including a spatial loop, plus a Split;
- uint64 source indexes above 2^63;
- one mutable source object shared across rows and across left/pending groups.

The same copier also isolates GraphMemo's initial candidate snapshot and
CandidateStore's output source/decompression metadata. Copying the source and
decompression bundle together preserves intentional aliases inside a result
without allowing output mutation to reach the stored candidates. A dedicated
unit test covers a shared mutable provenance object across these boundaries.

The tests prohibit legacy reconstruction APIs during snapshot copying, verify
the already completed release does not run again, and mutate original/resumed
objects to check separation from the saved state. This unit fixture tests state
transport, not physical legality of a new Mapping. The real 2mm/3mm differential
tests separately exercise complete FFM composition and reconstruction.

Shared-input tests use a chain A -> B where both operators also read X. Only
the produced Y creates a dependency edge; both X and Y belong to the local
boundaries. Two otherwise independent consumers of X remain disconnected in the
producer DAG and are still rejected by the chain-only Memo gate. The candidate
analyzer itself is tested to include X for both local operators.

## Reproduction

```sh
python -m pytest -q research/graph_coopt
python -m pytest -q research/tracking_audit research/streaming_join research/graph_coopt
python -m research.graph_coopt.audit_resumable_join \
  --output research/graph_coopt/results/state_contracts/resumable_join.json
```

The new audit archive retains per-phase diagnostic time, source hashes, merge
call traces, complete-frontier/source-identity checks and reconstruction counts.
Earlier archives remain historical records of their stated source versions.
Copying object cells incurs overhead and is accounted for in preparation,
advance, checkpoint, resume and finalization phases. This is not a speedup claim.

The full declared research/Streaming/graph_coopt regression completed with
**615 passing tests**. The pre-existing legacy test collection failure described
in RESUMABLE_JOIN.md is outside that passing count. Current audit artifacts are
under [results/state_contracts](results/state_contracts/); earlier 609-test and
state-analysis archives are kept as historical records.

The frozen controller reference shares numeric/group helpers with the current
implementation, as before. The live `tensor_names` fix applies to both paths;
controller equivalence is not a claim that the entire old implementation was
frozen or that its stale-cache behavior is retained. No general PhysicalInterface
substitutability or independently verified hardware lifecycle model is established.
Only an unchanged complete continuation/context may be resumed.
