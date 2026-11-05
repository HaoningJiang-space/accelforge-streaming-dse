# G1: generation provenance and a post-hoc whole-task opportunity estimate

**Result:** there is a substantial retrospective opportunity on this native 3mm
case, even against Capacity Events + Cache. Across three diagnostic runs,
**72 of 126 Jobs** have no returned final-frontier descendant. Their evaluation
plus wholly unused compatibility-batch processing accounts for **52.3–53.7% of
generation**. This clears the proposed 40% screen under an optimistic whole-task
deletion model. It does **not** establish a safe pre-evaluation certificate, a
new algorithm, or a measured speedup.

Protocol and observation code were frozen at `2a19a501`. The native FFM, existing
baselines and `joint_synthesis/graph_dp.py` were not changed. Only G1 was performed;
G2 symbolic equivalence and G3 online certificates remain untested.

## Same search, complete returned frontier provenance

The workload remains native NVDLA `matmuls(3,256,256)`, 8-bit, with 6,144 PEs in
16×384 / 32×192 / 64×96 arrays and 128 / 132 KiB GB. We use the existing Event
enumerator, exact capacity bits, packed target membership and EnumerationReuse
under `EL|RESOURCE_USAGE`, following [the cost diagnosis](SEARCH_COST_3MM.md).

Each fresh process first warms the unchanged backend and then performs one
traced search with fresh candidate/cache scopes. All six complete numerical
E/T/exact-resource frontiers match both that process's unobserved pass and
`results/search_cost_3mm/events_ru_1.json` **exactly**. All three runs return the
same numerical fronts and the same task classifications.

The provenance chain is:

```text
native template Job UUID
    -> ordered Tile assignments / model-row IDs
    -> local Mapping rows admitted to native compression
    -> per-Einsum compressed indices in every complete result
    -> every returned source of every target's numerical frontier
```

Sidecar observations never enter native candidate columns or Pareto decisions.
After native decompression, both original Mapping object identity and Tile
assignments are checked against the recorded origins. Integer values are read
column-wise; native float promotion of sparse symbol columns is accepted only
for finite, integral values strictly below 2^53 in magnitude. Unknown/lost
origins and ambiguous Tile assignments fail the audit.

| Target array | 128 KiB returned rows | 132 KiB returned rows | Jobs with any final descendant / total |
| --- | ---: | ---: | ---: |
| 16×384 | 27 | 29 | 13 / 42 |
| 32×192 | 37 | 39 | 22 / 42 |
| 64×96 | 46 | 47 | 19 / 42 |
| Total | 110 | 115 | **54 / 126** |

Thus **225 returned complete source instances** are traced, not just six EDP
winners. They use 277 distinct generated Tiles across 54 Jobs. Native Pareto can
collapse numerically tied sources: this is all sources the frozen reference
returns, not all equivalent Mapping identities ever considered. No new scalar
execution replay of all 225 instances is claimed; this experiment checks native
source lineage and complete numerical-frontier equivalence.

## Counts are not a time estimate

| Observed stage | Count |
| --- | ---: |
| Post-enumeration physical model rows | 8,994 |
| Local rows admitted to compression/Join | 3,695 |
| Generated Tiles used by any returned complete frontier | 277 |
| Jobs with at least one final descendant | 54 |
| Jobs with local Join inputs but no final descendant | 54 |
| Jobs whose model rows never reach local Join input | 18 |
| Compatibility batches with any final descendant | 26 / 69 |
| Wholly unused batches | **43 / 69** |

Although 8,717 / 8,994 model rows (96.9%) have no returned final descendant, it
would be wrong to claim 96.9% generation savings. Symbolic evaluation, enumeration
and batch processing are shared. A Job with even one useful Tile receives **no
partial time credit**, however many other rows disappear. These model rows also
exclude intermediate prefix candidates already pruned inside native enumeration.

Of the 43 wholly unused batches, 40 produce local Join inputs; only three produce
none. This shows the opportunity is not confined to empty local output. It does
not reveal whether a branch is structurally unsupported, capacity-infeasible,
cost-dominated, or merely displaced by an equal representative.

## Measured time attribution

The following are **diagnostic attribution passes**, not new uninstrumented
benchmark medians. Measured observer bookkeeping (0.082–0.088 s per run) is
subtracted from enclosing scopes. Wrapper overhead remains. Third-run slowdown
is retained; there are three runs on one host, with one worker and requested
single-thread numerical settings.

| Run | Generation s | Unused Job evaluation s | Wholly unused batch overhead s | Combined post-hoc credit s | Fraction of generation | Fixed-other-cost total projection |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 5.639 | 1.660 | 1.368 | 3.028 | 53.70% | 1.877× |
| 2 | 5.517 | 1.697 | 1.220 | 2.917 | 52.88% | 1.853× |
| 3 | 7.071 | 2.074 | 1.627 | 3.700 | 52.33% | 1.875× |

The median generation fraction is **52.88%**. Each projection uses that same
run's observer-corrected whole-search time (6.480 / 6.338 / 7.929 s), never the
prior 6.47 s benchmark median. Independently computed medians of components need
not sum to the median of their sum.

The arithmetic is additive: batch overhead excludes all nested Job evaluation;
global setup and remaining generation costs receive zero credit. In run 1:

| Generation accounting | Total s | Credited as unused s |
| --- | ---: | ---: |
| All Job evaluation | 2.799 | 1.660 |
| Batch processing excluding Job evaluation | 1.710 | 1.368 |
| Global/unattributed generation | 1.130 | 0 |
| Total | **5.639** | **3.028** |

Within Job evaluation, symbolic modeling is 1.581 s total / 0.884 s in unused
Jobs; target dispatch is 0.614 / 0.419 s; output compilation is 0.0595 / 0.0390 s
(run 1). These are **nested components**, not additional credits. No symbolic
preparation-reuse saving is added on top.

An important distinction follows. Unused Job evaluation alone occupies only
**29.3–30.8% of generation**. The above-40% whole-task opportunity also requires
avoiding entire unused batches, including their materialization, normalization,
capacity/Pareto and compatibility processing. A mechanism confined to skipping
some Job evaluations cannot claim the full 52.9% estimate. Finer-grained
algorithms could have other opportunities; this experiment does not bound them.

## What this ideal Oracle does and does not establish

The post-hoc model grants free, perfect knowledge of which Jobs and batches have
no returned frontier descendants, then subtracts their measured costs while
holding everything else fixed. It does **not** execute a pruned search.

In particular:

- A discarded Job may supply cached compilation/prefix artifacts used later.
  Removing it can move work into retained Jobs; no dependency-adjusted savings
  are claimed.
- Local cohorts, target-specific ordered fallback and Pareto histories can
  change if generation changes. Preserving selected complete witnesses is not
  a proof that deleting these tasks from FFM preserves its reference policy.
- Equal-source folding is native. Requiring every tied Mapping identity, rather
  than the complete numerical frontier, is a different contract.
- No-final-descendant does not mean no legal consumer. This is not a structural
  support certificate and does not justify online deletion.
- The estimate is deliberately coarse: necessary Jobs and mixed batches get no
  partial credit. It is not a universal upper bound on all graph algorithms, nor
  a guaranteed achievable saving. G1 and G2 may overlap and cannot simply be added.

Consequently the 1.85–1.88× figures are **optimistic projections**, not speedups.
No production candidate, Job, batch or Join was skipped in these runs.

## Research gate

G1 is positive as a retrospective screening result: there is enough observed
whole-task cost to keep investigating generation on this case, despite the small
remaining Join. It does not reverse the earlier decision against building an
exact-state Resource Transfer Memo from the Reservation witness alone.

It still provides no reason to build a Conditional Frontier Engine yet. The next
claim would need evidence that a cheap pre-evaluation condition can reject a
material fraction of **whole candidate families**, preserving the declared target
policies or explicitly changing the search-quality contract. It must distinguish
graph-induced restrictions from ordinary local dominance/shared preparation.
The 18 already locally eliminated Jobs are a reminder that all retrospective
waste cannot automatically be attributed to missing graph reasoning.

Only after such evidence should the result become an implementation mechanism.
Neither G2 nor G3 was implemented or declared passed in this round.

## Receipts and reproduction

- [Protocol](GENERATION_PROVENANCE_PROTOCOL.md).
- [Observer and driver](generation_provenance_3mm.py),
  [six new diagnostic tests](test_generation_provenance.py).
- [Summary](results/generation_provenance_3mm/summary.json),
  [manifest](results/generation_provenance_3mm/manifest.json).
- [Run 1](results/generation_provenance_3mm/trial_1.json),
  [run 2](results/generation_provenance_3mm/trial_2.json),
  [run 3](results/generation_provenance_3mm/trial_3.json): every Job/Tile,
  compression edge, returned source edge, target vector and per-task time.
- [Raw logs](results/generation_provenance_3mm/trial_logs.zip),
  [test receipt](results/generation_provenance_3mm/tests.txt): **15 passing
  diagnostic tests**, including the nine previous tests, not 15 new production
  regressions.

```sh
python -m research.diagnostics.generation_provenance_3mm --repeats 3 --output research/diagnostics/results/generation_provenance_3mm
python -m pytest -q research/diagnostics/test_generation_provenance.py research/diagnostics/test_search_profile.py research/diagnostics/test_causal_3mm.py --disable-warnings
```
