# State analysis before optimizer development

This experiment measures the input to a possible physical-property memo without
implementing a new mapper. All FFM generation, fallback, prefix Pareto, fusion
restrictions and original grouping are preserved. Candidate extraction occurs
**before** any Join. No candidate is deleted, combined, migrated, or re-priced.
Signatures identify observations, not the set of all legal future completions.

## Scope and reproduction

```sh
python -m research.graph_coopt.memo_state_analysis \
  --output research/graph_coopt/results/memo_state_analysis.json
python -m research.graph_coopt.summarize_memo_states \
  research/graph_coopt/results/memo_state_analysis.json \
  --output research/graph_coopt/results/memo_state_summary.json
python -m pytest -q research/graph_coopt
```

The recorded run independently generated 2mm and 3mm (each MatMul is 32x32x32)
on NVDLA 8x32, 16x16 and 32x8 arrays (256 PEs), each at 2 KiB and 4 KiB
GlobalBuffer. This is twelve workload/architecture catalogs, not twelve
independent statistical replicates. Metrics are Energy, Latency and Resource
Usage; Register is fixed at 8 bits, research switches are cleared before each
generation, one worker is used, and the conservative Fusion filter remains on.
There is no architecture ranking, area claim, joint optimum or performance
comparison. The generation and analysis times in the archive are single ordered
diagnostic runs with cold/warm effects; they must not be used as speedup evidence.

## What each signature measures

Counts always keep Einsum identity: rows for different operators never merge.

| Signature | Included information | Interpretation |
| --- | --- | --- |
| template | Actual node order, placement, fusion/backing labels, all declared fields and private labels; numeric loop tile extents erased | Loose structural overlap; binding and resource feasibility unknown |
| resolved_compatibility | Every Compatibility dataclass field, including splits, with numeric TilePattern values | More detailed than Python Compatibility equality; still incomplete copy semantics |
| observed_boundary | Resolved compatibility, all observed holders/reservations of boundary tensors, their positions, preceding loop scopes and fused loops, private labels | Diagnostic physical interface; no proof of complete copies, alias/lifetime semantics or substitutability |
| full_local_mapping | All local nodes and numeric tiles, all declared fields and private labels | Complete observed source decision signature, with evaluated component objects and derived iteration caches excluded; still not a semantic equivalence theorem |
| row_payload | Full mapping, group compatibility/bookkeeping, every non-source-ID column with its dtype and exact scalar encoding | Potential repeated representation only; different architecture capacity metadata stays distinct |

Source UUIDs, group index and row position are retained separately for every row.
Source UUIDs are omitted from comparison keys because independently generated
identical source decisions receive different UUIDs. Unknown objects/callables,
missing tile columns, nested local mappings and imperfect tiles are reported as
unsupported rather than projected into a common placeholder. No rows were
unsupported in this run. Integer/uint64 values are read column by column to avoid
mixed-Series float conversion. Array shape, layout, tile order, private backing,
persistence and fusion distinctions are not inferred away.

Neither an interface cluster nor a repeated full mapping can simply be reduced
to one plan. It may have distinct resource and cost vectors, provenance,
architecture-dependent policy membership, or unrepresented future constraints.
Every semantic merge remains uncertified. A practical memo also needs a Pareto
set of alternatives within each valid interface; interface count is not the
number of plans that such a memo must retain.

## G1: compression opportunity

The archive contains 1,374 candidate-row occurrences for 2mm and 2,966 for 3mm
across their six architectures. Within each architecture, every candidate has a
distinct full local mapping signature and distinct row payload. Merely interning
identical complete local records would remove no rows within a catalog.

At 16x16 and 4 KiB:

| Workload | Candidate rows | Existing symbolic FFM groups | Numeric Compatibility signatures | Observed boundaries | Full local mappings |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2mm | 232 | 22 | 102 | 157 | 232 |
| 3mm | 492 | 58 | 237 | 417 | 492 |

Observed boundaries retain 67.7% and 84.8% of candidate counts, before keeping
multiple alternatives per boundary or establishing future equivalence. In each
case, 23 boundary clusters contain distinct local cost/resource vectors. This
does not establish enough compression to justify a general graph memo. Existing
FFM groups are *symbolic* groups with row-dependent values; comparing their count
directly with concrete interface counts as a speed or memory ratio is invalid.
The new observation splits some already grouped symbolic interfaces; it does not
identify a hidden 100x compression.

## G2: composition correctness

The existing fixed-architecture gate remains in place: 2mm (4x8, 96 B) and 3mm
(4x8, 128 B) preserve the complete numeric FFM results and source identities under
snapshot transport; all 13 result instances re-evaluate. The independently
generated comparisons are recorded in [small_chain.json](results/small_chain.json).
New real tests verify the analyzer leaves every original candidate frame intact.
This gate exercises **original FFM composition**, not an independent memo
composition algorithm, a physical lifetime oracle, or proof of complete Mapspace
coverage. It does not license using the observation keys for pruning.

## G3: cross-architecture overlap

The archive includes all directed pairwise comparisons, both target row coverage
and distinct-key intersection. At 4 KiB, observed-boundary coverage between
different shapes ranges from 28.9% to 52.6% for 2mm and 19.8% to 36.8% for 3mm.
No complete observed local mapping signature is shared across these shapes in
this selected catalog. This is a statement about the recorded signatures and
FFM-selected candidates, not impossibility of transformation, future equivalence,
or missing a numeric optimum. The template signature deliberately erases tile
values and has substantially greater overlap.

Across the six configurations, 2mm has 691 distinct full local signatures and
3mm has 1,500. The approximate 2x overlap mainly comes from repeating capacities
within a shape. At 16x16, all 232 selected 2mm mappings recur between the two
capacities; for 3mm, the 487 selected 2 KiB mappings all recur among the 492
4 KiB mappings. Raw row payloads remain distinct because exact reference capacity
metadata changes. Matching cost/resource hashes are reported separately; matching
keys do not establish target-policy membership outside the searched configurations.
These facts support testing capacity reuse, which the project already provides,
and give no new measured reduction in cross-shape generation work.

All catalogs were fully generated: search work avoided by this experiment is
zero. G3 measures an opportunity, not a functioning shared-search mechanism.

## Decision and unresolved risks

Keep the analyzer and fixed-architecture transport tests. The present pilot does
not justify writing `optimizer.py`, introducing a generic memo, or extending to
MIP and hardware selection. This conclusion concerns these two small chains
under the declared signatures; it does not rule out all factorized algorithms or
other workloads. A next proposal needs a concrete replacement/equivalence rule
and evidence it can discard substantial work beyond FFM's existing grouping,
including the alternatives still needed within a group.

| Risk | Current treatment | Still unproven |
| --- | --- | --- |
| Reimplementing FFM | Analyze original groups and use its Join unchanged | A new conditional dominance rule with additional benefit |
| State growth | Report row counts, concrete interface distributions and cross-configuration unions | Compact, sufficient future interfaces and bounded search |
| Runtime overhead | Run analysis as an offline diagnostic; no default backend change | End-to-end improvement over FFM plus cache |
| Incomplete physical properties | Retain copy/order/private-label distinctions; unknown forms fail closed; never merge | Alias/lifetime completeness and safe substitution |
| Hardware cost model | No hardware optimum or resource-budget claim | Calibrated area/interconnect/energy model for co-optimization |
