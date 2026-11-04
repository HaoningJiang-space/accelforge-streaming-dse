# Engineering gate: resumable reference-order FFM Join

This refactor makes the original Join controller pausable at a completed Einsum
transition. It establishes an engineering interface; there is no new dominance,
reordering, graph partitioner, demand propagation or cross-architecture algorithm.
The current negative/compression findings in MEMO_STATE_ANALYSIS.md still apply.

## Core contract

`JoinContext.from_spec(spec, ...)` captures a private Spec copy, all `AF_*`
switches, the original Join flags and optional callbacks. Checkpoints are bound
to the **same context object**, not equality of Compatibility or a subset of
the graph. A new context, even from the same Spec, cannot resume them. Changed
switches, another architecture, another continuation workload, or a different
Join contract require a fresh start. Callbacks, when supplied, must remain
deterministic; capturing a callback does not freeze its external Python globals.

The new core modules are:

| Module | Responsibility |
| --- | --- |
| `join_context.py` | Captured architecture/workload/model/search context and strict reuse checks |
| `partial_state.py` | Owned current groups, processed operators, prepared remaining operators, tensor bookkeeping, ignored resources, aliases, counters and diagnostics; isolated checkpoints |
| `join_engine.py` | Original initialization, one reference-order Join transition, final consolidation; public copy-isolated APIs |

`join_pmappings()` now runs these same owned internal phases to completion.
Its existing low-level mutation contract remains: callers of the ordinary path
provide owned groups, as before. The resumable public `start`, `advance` and
`finalize` isolate working copies. Numeric DataFrame formulas, loop permutation,
Reservation operations, grouping, lookahead, Pareto and operation order have not
been changed. The common `restore_mappings()` path decompresses rows, attaches
source mappings and constructs the same public `Mappings` as full execution.

## What is actually saved

After A -> B, a state contains the combined A/B candidate groups and the prepared
remaining C groups. It also retains the union of tensors encountered, current
resource structures and all future operators used for liveness/lookahead. It is
not a standalone result for arbitrary subgraph `{A,B}`. Initialization still
prepares **all** right-hand candidates under the full original continuation.
Nothing here avoids original candidate generation or makes Join associative.

Snapshots are private, copy-isolated **in-memory** payloads. They are not immutable
NumPy buffers, a disk interchange format, or trusted input for another process.
`snapshot()` copies the working state; `resume()` copies it again and resets the
diagnostic timer so paused time is not attributed to a merge. Multiple resumes
can be advanced or finalized independently. A frozen wrapper is not evidence of
physical-interface equivalence. No snapshot is compared by its array contents or
used for conditional Pareto pruning.

## GraphMemo usage

```python
memo = generate_memo(spec)          # original complete local generation
initial = memo.start()              # compress/prepare once, select first Einsum
ab = memo.advance(initial, "Matmul1")
memo.save_partial(ab)
saved_group_metadata = memo.groups_for(("Matmul0", "Matmul1"))
resumed = memo.resume_partial(("Matmul0", "Matmul1"))
abc = memo.advance(resumed, "Matmul2")
result = memo.finalize(abc)
# Equivalently: result = join_memo(memo, resumed)
```

The memo stores real intermediate FFM groups, not only the initial source table.
Its CandidateStore retains source/decompression data and one JoinContext. Saving
or resuming a prefix never calls `make_pmappings`, redoes compression, reruns
initial grouping, or redoes an earlier transition. `groups_for` returns source
metadata for single operators and intermediate metadata for explicitly saved
prefixes. Actual continuation groups are in the owned state returned by
`resume_partial`. GraphMemo still restricts graphs to sequential chains. General
FFM continues to support its original graph inputs; new branching-Memo semantics
are not inferred from that support.

## Validation and limits

```sh
python -m pytest -q research/graph_coopt/test_join_engine.py
python -m research.graph_coopt.audit_resumable_join \
  --output research/graph_coopt/results/resumable_join.json
```

The test-only `_reference_join_bd39555f.py` freezes the **old controller** from
bd39555f, including its source hash. Its numerical/group helpers remain shared
because their implementations are unchanged. On the same generated 2mm/3mm
candidates, tests compare this reference with the new complete wrapper and the
paused/resumed path. Checks cover numeric columns and dtype, exact resource
columns, source mapping identities, total/valid mapping counts, all reconstructed
rows, and both Resource Usage and Energy/Latency controller modes.

Call tracing labels each numeric merge by the right-hand operator. Prefix calls
target Matmul1; only Matmul2 calls may occur after the 3mm resume. A patched
candidate generator raises if entered after the checkpoint. Tests also exercise
input/state isolation, repeat resumes, wrong next operator, early finalization,
changed switches, another architecture, and another graph/context.

[resumable_join.json](results/resumable_join.json) records the independent audit.
The 3mm checkpoint contains 67 candidate rows after 14 Matmul1 numeric-group
merge calls; resuming performs only 4 Matmul2 calls. The 2mm checkpoint contains
11 rows and needs only final consolidation. The final 6 and 7 mappings match
the frozen controller's complete numeric tables and source identities and all
13 result instances re-evaluate. These merge-call counts are not candidate-pair
counts or speedups.

The research/tracking_audit, research/streaming_join and research/graph_coopt
regression completed with 609 tests passing. An additional attempt to collect
`tests/test_ffm_join_pmappings.py` failed because it imports the already absent
`compatibility_util` module. That legacy test is not included in the passing
count; its collection log is retained separately. This is not an all-repository
test-pass claim.

This correctness interface intentionally pays for deep copies. CandidateStore,
snapshot, resume, public advance, and final source restoration each retain or
copy state. The audit records generation, preparation, prefix, checkpoint,
resume, continuation/finalization and validation times, including those copies.
These are single diagnostic measurements; the frozen reference runs beforehand
and warms JIT, so they are not a fair baseline comparison. This can increase
runtime and memory; no speedup is claimed. A future
performance comparison must include generation, preparation and copy costs.
Demand-driven candidate requests, architecture domains and conditional dominance
remain separate unimplemented research steps. Existing complete-FFM equivalence
also does not prove completeness of the original Mapspace or independent physical
lifetime accuracy.
