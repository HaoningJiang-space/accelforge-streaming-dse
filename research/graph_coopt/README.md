# Fixed-architecture FFM memo gate

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
Memo entries exist only for individual Einsums. Prefix subgraphs are identified,
but their intermediate mappings are **not** stored, shared, or optimized. All
grouping, permutations, reservations, Pareto, join order, and mapping reconstruction
remain FFM's own; this validates a transport boundary, not a new graph DP or an
independent Fusion correctness proof. No new `GroupJoinAdapter` is exposed yet:
the current FFM join's context and mutating preparation need a separate semantic
gate before intermediate states can be safely reused.

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

The next gate requires safely retaining and composing genuine intermediate
subgraph states without treating incomplete Compatibility as a complete physical
interface. Only after that gate should conditional dominance, new join order,
architecture reuse, or area-constrained hardware selection be introduced.
