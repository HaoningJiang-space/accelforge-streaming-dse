# Most conditional states are redundant, but not by renaming or by counts

Question: of the exact solver's completed cache entries (solve + group keys),
how many give **different** responses? If almost all differ, no exact quotient
can help and only dominance or approximation remains. If few differ, the key
over-specifies the state and a smaller sufficient statistic exists.

Exploratory census, not a frozen prediction. Sources: `redundancy_census.py`
(`13c70847`, controls `369a18c7`), `analyze_redundancy.py`. Records in
[results/redundancy/](results/redundancy/). Fresh Linux processes, hash seed 0,
exact cut DP, halving tiles, `canonical_spans` and `independent_ops` off,
90-200 s and 4 GiB per case, at most four workers. All 45 new runs complete;
the two six-consumer forks reuse the archived census
(`results/residency_states/*_serial40`). No solver source changed.

Columns:

- **keys**: completed cache entries.
- **alpha**: classes under joint tensor and rank renaming, with sizes and
  current extents carried (first-appearance canonical form, so it is not a
  full orbit canonicalization). Zero classes in any case had two different
  frontiers.
- **local**: decorations (external set, owned set) at a fixed
  (stage, span, extents) → distinct frontiers among them.
- **distinct**: distinct (stage, frontier) values over the whole graph. This is
  an oracle bound: no exact memo keyed on states can need fewer solves.

## 1. Results

| Case | keys | alpha | local: decorations → distinct | distinct |
| --- | ---: | ---: | --- | ---: |
| fork 6 consumers, same role (2222) | 106,604 | 93,833 | 106,604 → 1,586 (351 contexts) | 262 |
| fork 6 consumers, kkkiii | 106,604 | 106,030 | 106,604 → 1,600 | 263 |
| fork kkk, extents 4 | 10,264 | 8,749 | 10,264 → 2,602 | 662 |
| residual depth 24, extents 2 | 10,256 | 3,788 | 10,256 → 5,139 | 229 |
| residual (4,4,8) depth 8 | 5,097 | 4,077 | 5,097 → 2,422 | 401 |
| FFN forward 4 layers | 10,834 | 8,761 | 10,834 → 1,814 | 171 |
| FFN forward 2 layers, m8 d4 f8 | 6,176 | 6,067 | 6,176 → 3,429 | 921 |
| FFN training 1 layer | 17,095 | 17,095 | 17,095 → 2,726 | 723 |
| one-op ancestor control, k=8 | 12,866 | 12,866 | 12,866 → 2,551 | 73 |

All 47 rows are in the result directory. Larger extents raise the distinct
counts (fork kk: 63 → 292; residual depth 4: 71 → 329) but the gap to keys
persists, so it is not only small-number coincidence at extent two.

## 2. Findings

**(a) The residency decoration is the dominant over-specification.** In the
six-consumer forks, 351 (span, extents) contexts carry 106,604 decorations
but only about 1,590 distinct frontiers: roughly 300 residency/ownership
decorations per context induce about 4.5 different responses.

**(b) Renaming explains little.** Joint tensor and rank renaming removes at most 12%
of fork keys (0.5% for kkkiii) and 19% of four-layer FFN keys. Tensor-only renaming (the existing
`canonical_spans` rule) removes nothing in the FFN and attention stacks,
because each layer uses its own rank variables. The residual chain is the
exception (10,256 → 3,788 at depth 24), because it reuses I and K.

**(c) Count summaries are refuted everywhere except the symmetric control.**
Replacing *which* tensors are resident by the multiset of their (size, role)
gives classes with different frontiers in every fork, residual and stack case,
for example 329 classes in fork same6 and 1,643 in FFN training. This extends
the positional counterexample from one pair to every studied family.

**(d) Ownership was redundant in every case.** Dropping the owned set from
the alpha signature never merged different frontiers (0 violations in 47
cases). The ownership repair still matters for pricing; this says only that,
once the rest of the state is fixed, the reachable owned sets do not change
the response here. It is an empirical observation, not a proof.

**(e) The ancestor control collapses to a polynomial.** Keys grow as about
3^k (4, 14, 46, ..., 12,866), while distinct frontiers are exactly
k²+k+1 (3, 7, 13, 21, 31, 43, 57, 73). A summary keeping only per-tensor
(size, role, resident, owned) and per-operator arity, without incidence, has
(k+1)² classes and no violations. Its ranks are fully symmetric under S_k,
which first-appearance alpha canonicalization does not detect. Here an orbit
canonical form, not a new mechanism, removes the exponential.

**(f) No single tensor can be ignored, yet a per-operator profile works on
one fork.** In fork same6, every tensor in a context is relevant to some
decoration. Projecting decorations onto the relevant tensors keeps 81,644
classes and still has 4,483 violations, so the collapse is not a product of
irrelevant bits. Instead, keying each context by the per-operator sorted
(size, used-by-more-than-one-op) of nonexternal accessed tensors gives
18,865 classes with no violations (5.6×). The same summary fails on kkkiii
(143 violations, even with rank tags), so it is not yet a theorem.

## 3. Interpretation

- Exact reuse has a large oracle margin: 106,604 entries vs at most 1,600
  locally distinct responses (67×) in forks, and about 2× to 6× in chains and stacks.
- Where the margin comes from: not renaming (b), not counts (c), not per-tensor
  irrelevance (f). A response depends on residency through each operator's
  remaining occupancy and on which operators share the remaining tensors.
  This generalizes the scalar-X bridge, whose response is d = max over
  operators of nonexternal occupancy.
- Next question: what sufficient statistic of (span, R) works for both role
  mixes? Candidates must retain cross-operator sharing (which nonexternal
  tensors link which operators), which the failing per-operator profile drops.

## 4. Limits

- Equal frontiers do not by themselves give an algorithm: a cache can share a
  response only when it can recognize equivalence before solving. The distinct
  column bounds what any such rule could achieve.
- "Local" fixes extents; merging across extents is not measured.
- Serial grammar, no recomputation, halving tiles, single-writer DP; extents
  at most 8 here.
