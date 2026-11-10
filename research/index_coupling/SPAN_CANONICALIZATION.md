# Ordered-span name canonicalization

This opt-in reduction addresses repeated recursive subproblems in P19. It does
not remove any partition, loop or retention choice. The default is unchanged:
`curve(..., canonical_spans=True)` enables it for exact (`grid=None`) curves.

## Equivalence and witness contract

Two ordered spans share a representative only if their first-occurrence tensor
numbering produces identical ordered operator/access lists and literal rank
dimensions. Each tensor also has the same **global** produced/consumed flags and
consumer count. These global facts affect final-write pricing and `split_shared`.
Input access order is conservatively retained, including the last/output entry.
Neither operators nor rank names are permuted. Multiwriter incidence is retained.

Before lookup, extents and ownership are projected by the existing rules.
External and owned sets are then renamed through the tensor bijection. Therefore
two calls share an entry only when extents, external reservations, ownership,
and the recursive entry kind agree after renaming. Constrained root calls bypass
canonicalization. A full-graph span has a unique length and cannot alias a proper
span, so whole-span cut restrictions cannot leak to another span.

The equivalence argument is induction on decreasing extents and smaller spans:
the bijection preserves scalar leaf sizes, every partition and shared-tensor
choice, writer/reader predicates, legality of common loop ranks, missing-rank
retention choices, and all capacity/traffic arithmetic. Corresponding children
have corresponding boundary states. Consequently each derivation has a renamed
derivation of equal cost, in both directions. Pareto frontiers are equal within
the current grammar. This does not prove that the grammar contains every legal
physical schedule or that its pricing is correct on every graph.

A cached witness names its representative's operators/tensors. Each reuse wraps
the witness in a lazy renaming node; flattening composes nested maps and restores
the caller's names. Numeric frontiers avoid this work. No complete execution tree
is copied into the cache. This witness contract is tested by independent cell
simulation, including renamed whole graphs and nested reused spans.

## Diagnostics

With `stats={}`, three marginal histograms count cache misses by ordered span,
extent tuple, and `(span length, external count, external local-output count,
owned count)`. They count misses before computation, so an interrupted active
call appears as a miss but not as a completed cache entry. Marginals do not
duplicate the full exponential set of keys. Alpha-enabled span histograms name
representatives; compare totals and residency distributions, not literal names.

## Validation and experiment plan

Before remote measurements, 21 tests pass, including 480 comparisons between
the renamed DP and enumeration over 120 deterministic small DAGs. Dedicated
checks cover same/mixed forks, residual chains, root and conditional interfaces,
multiwriter fallback through the prior suite, global-role distinctions and
independent execution of restored witnesses. These tests supplement the
equivalence argument; they do not substitute for it.

The second batch compares DP with and without canonicalization, both with the
new ownership projection and witnesses. Main timings disable profiling. Fixed
cases are six-consumer forks `(4,2,4,2)` and `(8,4,8,2)`, each with roles `kkkkkk`
and `kkkiii`. Each job gets 300 seconds including replay and 6 GiB address space;
at most four jobs run concurrently. Each arm starts a fresh process. Incomplete
curves remain incomplete, and no speed ratio is inferred from two timeouts.
Separate short profiled runs diagnose state growth; their timings are not mixed
with the unprofiled comparison. These are implementation/performance experiments,
not new frozen P-protocol predictions.
