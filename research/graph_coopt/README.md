# Graph memo feasibility gates

The research gate remains **state analysis before optimizer development**.
See [MEMO_STATE_ANALYSIS.md](MEMO_STATE_ANALYSIS.md) for G1/G2/G3 definitions,
signature limitations and the twelve independently generated 2mm/3mm catalogs.
There is no evidence here that introducing a graph memo beats existing FFM or
its cache. A separate engineering refactor now supports actual intermediate
state pause/resume; see [RESUMABLE_JOIN.md](RESUMABLE_JOIN.md). This is a reference
equivalence interface, without new pruning or cross-architecture search.
The follow-up [state snapshot audit](STATE_SNAPSHOT_AUDIT.md) covers extended
ledgers, release cursors, object-valued source isolation and shared external inputs.

This research scaffold checks that original FFM per-Einsum candidate groups,
their provenance, exact resource columns, architecture and source mapping objects
can be retained in a graph-indexed snapshot and passed back to **unchanged FFM**
for full composition. The Join mutates its input, so each call receives a deep
copy. The snapshot has no API for binding a different architecture. Unknown
non-backing copy semantics are explicitly marked incomplete; equal traits do not
authorize merging, pruning, or cross-architecture reuse.

The graph extractor accepts an acyclic, topologically ordered workload with a
single producer for each tensor. The present gate further restricts execution to
sequential chains without skip edges. It deliberately rejects branching and
ambiguous producers rather than treating graph connectivity as Fusion legality.
Source entries exist for individual Einsums. Explicitly saved prefixes now store
real intermediate groups with their entire original continuation and Join
context. The original grouping, permutations, reservations, Pareto, join order
and mapping reconstruction remain in the shared FFM kernel. Resume is restricted
to the same context; it does not establish a new graph DP or a general physical
interface replacement rule.

Run from the repository root:

```sh
python -m pytest -q research/graph_coopt/test_graph_memo.py
python -m research.graph_coopt.audit --output research/graph_coopt/results/small_chain.json
```

The audit runs an independently generated original FFM search and then the memo
path at the same architecture, comparing every numeric result column and
re-evaluating every reconstructed result. [small_chain.json](results/small_chain.json)
records 2mm at 96 B (15 candidate groups, 44 rows, 6 output rows) and 3mm at
128 B (40 groups, 109 rows, 7 output rows), both NVDLA 4x8, M=4 and KN=8.
The 6 and 7 reconstructed mappings respectively passed the existing FFM
re-evaluation, including physical capacity and spatial fit checks. Re-evaluation
still uses the FFM model; it is not an independent proof of physical lifetimes.
These are two small correctness cases and no timing or speedup claim is made.

The decision gate is evidence of substantial state compression beyond FFM's
existing grouping. Equal observed interfaces do not authorize semantic merging;
their future substitutability and useful cost/resource alternatives still need
proof. The current small experiment does not justify a general optimizer,
conditional pruning, or a new hardware selection layer.
