# Stage 0–2: the declared six-point 2mm gate

Core implementation: `93cdb93e`. Reference FFM source is unchanged from
`87866410`. The case is `matmuls(2,16,16) @ NVDLA`; the domain contains
`8×32`, `16×16`, `32×8`, each at 4/8 KiB GB. PE count is 256, with fixed
bandwidth, topology, precision, unit action costs and zero leakage.

## Correctness and coverage

The [frozen audit](audit.json) independently constructs each physical reference
architecture. Across all six points and all 24 templates:

- Every template's pre-model, policy-selected Tile **set** equals the target's
  subset of the shared enumeration. This checks candidates before terminal
  selection; comparison of best EDP alone would not establish coverage.
- The complete set of E/T/exact-resource frontier vectors is exactly equal,
  without numeric tolerance. Source/provenance columns are not optimization
  coordinates and are recorded separately.
- All **80 returned source instances** reconstruct and re-evaluate successfully
  on their actual physical architecture. They are not 80 distinct mappings.
- Mapping ID sets differ at four points with tied frontier vectors; they agree
  at the two `32×8` points. The result is numerical-frontier equivalence and
  validated sources, **not identity of every tie-selected physical Mapping**.
- The separate 68/96 B regression also matches target Tile sets and full numeric
  frontiers. Membership labels are not used as capacity thresholds.

`16×16` wins EDP in both SRAM strata. Each shape has the same EDP at 4 and 8 KiB.
This deliberately small gate contains no capacity-induced winner switch; it is
not evidence of rich graph/hardware coupling or global area-optimal chip design.

## Three fresh-process trials per variant

Every trial runs in a fresh process with **one worker**. A first complete search
records cold search time, then a second complete search records warmed time.
Each search creates fresh candidates and a fresh `EnumerationReuse` scope;
prepared candidate caches do not survive between the two searches. Generic
Python/JIT/formula caches can be warm on the second search. Interpreter startup
and imports are outside both timers; architecture/spec preparation, model
construction, generation, Join and all six queries are inside. Full source
validation is outside the timers. Every cold run is separate from other trials.
The initial default-worker attempt was rejected by `EnumerationReuse`; it is
excluded. The twelve archived trials below explicitly use the corrected serial
protocol, alternating variant order between rounds.

| Method | Cold median s | Warm median s | Warm range s | Process peak RSS median GiB |
| --- | ---: | ---: | --- | ---: |
| Independent FFM | 11.154 | 6.331 | 5.954–9.637 | 0.278 |
| FFM + existing cache | 12.461 | 6.861 | 5.444–7.221 | 0.277 |
| Existing per-shape capacity Event + Bitset + cache | 7.289 | 3.623 | 2.734–4.298 | 0.264 |
| Shared architecture-domain generation + native Join | **5.727** | **1.215** | 1.168–1.268 | 0.265 |

Relative to the strongest existing Event baseline, this gate is **1.27× cold**
and **2.98× warm**. Relative to the cache-only baseline it is 2.18× cold and
5.65× warm. These are small-case single-host measurements with visible variance,
not a general DSE speedup. In particular, the cache-only warm median is slower
than independent FFM despite doing less expansion, so cache work counts cannot
be substituted for time. RSS is the process high-water before validation,
including interpreter/imports and the first cold search, not incremental search
allocation. The experiment establishes no meaningful RSS advantage over Events.

## What work actually changes

Counts are identical across each variant's three trials. `Expanded rows` counts
actual `_compute_symbol_choices()` results, including only cache misses; model
rows count final Tile bindings passed to model materialization. A model-template
call performs the native symbolic model setup once, not once per model row.

| Method | Model-template calls | Actual expansions | Expanded rows | Model rows | Generated group rows | Join pair rows | Largest pair frame |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Independent | 144 | 744 | 9,152 | 2,240 | 580 | 1,008 | 100 |
| Cached | 144 | 206 | 2,872 | 2,240 | 580 | 1,008 | 100 |
| Events + cache | 72 | 206 | 2,872 | 1,120 | 290 | 504 | 100 |
| Shared domain | **24** | 262 | 3,650 | 1,120 | 290 | 1,671 | 555 |

One shared conditional generation and one native full Fusion Join serve all six
points. This reduces repeated symbolic-template preparation. The shared method
has **27.1% more numeric expansion rows** and **3.32× as many Join pairs** as
Events; some pairs have empty architecture intersection and are handled by the
existing late-membership path. It does not reduce model or generated-group rows
further than Events. The observed time improvement is consistent with eliminating
repeated preparation; a phase-isolated ablation has not established exact causal
time attribution. It is not evidence that a new graph decomposition reduced the
important combinatorial search space.

## Gate decision

| Obligation | Current evidence |
| --- | --- |
| Preserve native reference backend | No production FFM changes; declared Tile sets and full numeric fronts match |
| Six-point reconstruction | 80/80 audit instances pass; all returned instances in every timed trial pass |
| Architecture genuinely enters generation | Shared three-bound cohorts and one domain-intersection Join execute |
| Reduce work beyond strong Event baseline | Symbolic template preparation decreases; numeric expansion and Join work increase; final model/group rows tie |
| Consumer Requirements provide extra safe reduction | **Deferred**, not enabled in Stage 0–2 |
| End-to-end cost beats cache and Events | Pass on this finite small gate, including preparation; broader scaling untested |

These results justify retaining the bounded architecture-conditional generation
component. They do **not** justify a general Hypergraph Optimizer, a novel
Graph-Structured Joint Search claim or automatic progression to arbitrary DAGs.
No consumer-driven reduction or architecture-family proof has been measured.

## Files and reproduction

- [audit.json](audit.json): six physical references, policy Tile coverage, complete
  frontier vectors, Mapping IDs, source re-evaluation and implementation hashes.
- [targeted_tests.txt](targeted_tests.txt): three initial integration/contract tests.
- [benchmark/summary.json](benchmark/summary.json): medians, work counts and
  per-variant cumulative validity flags.
- `benchmark/{variant}_{1,2,3}.json`: every trial's cold/warm timings, source
  validation, exact full-front checks, work, reference checksum and source hashes.

```sh
python -m research.joint_search.validation --output research/joint_search/results/stage02/audit.json
python -m research.joint_search.benchmark --repeats 3 --output research/joint_search/results/stage02/benchmark
python -m pytest -q research/tracking_audit research/streaming_join research/graph_coopt research/joint_search/tests --disable-warnings --maxfail=1
```

Archived correctness/timing are model-level checks. Re-evaluation reuses FFM and
does not independently validate physical copy lifetimes or real-chip area/cost.
