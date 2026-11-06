# Two physical contexts: necessary distinctions, no shared-DP advantage

**Decision: no-go for expanding the current finite conditional-vector DP as the
paper's core algorithm.** Real backing contexts change safe pruning, but the
shared representation is slower and does more environment-level work than
ordinary Grounded DP with the same factor cache. This does not disprove all
symbolic resource-effect methods or Architecture–Mapping Co-Optimization.

This completes the requested A/B study, with **no additional Tile choices**.
A is [Grounded DP Ablation](GROUNDED_ABLATION.md). B's scope was fixed in
[RESIDENCY_CONTRACT.md](RESIDENCY_CONTRACT.md) before its exhaustive run; source
commit is `f14b2bbc`. Execution evidence records source SHA-256s.
The original FFM and `joint_synthesis` optimizer remain unchanged.

## A. Correct the attribution of the earlier result

| Original GB-only family | Partial combinations | Complete candidates before Pareto | Numeric frontier |
| --- | ---: | ---: | ---: |
| Cached Flat | 576 | 192 | 11 |
| Grounded DP | 81 | 33 | 11 |
| Universal Effect DP | 108 | 60 | 11 |

All exact Oracle frontiers agree. The earlier 192-to-60 candidate reduction is
not an exclusive Resource-Effect benefit. Ordinary multiobjective DP does better
once the actual T2 obligation is known. The 20 universal states' extra generality
was not exercised by new legal contexts in that experiment.

## B. Two actual physical executions

Keep the three 256x256 Matmuls, original n1 stripes {64,128,256} and all six
k/j choices in {32,64}. Array choices are 32x192 and 64x96 (both 6,144 PEs),
with j bounded by reuse_input and k by reuse_output. GB budgets are 128/132 KiB.
Legality participates in local expansion and a single global array membership
is maintained through every composition.

- **GB backed:** retain one full T2 across later producer stripes and Matmul2.
- **DRAM backed:** keep T2 in DRAM; for every Matmul1 reduction/output block,
  load the previous partial version (except the first), update a GB tile, drain
  it to DRAM, free the GB copy. Matmul2 explicitly reloads input tiles inside
  its original output-outer loop. The event interpreter checks versions and
  allocations; the native adapter emits actual backing/storage nodes.

DRAM is not modeled as setting x=0. It changes GB/DRAM actions, energy, latency
and storage together. In particular every reduction block drains partial T2,
so the extra Matmul1 GB drain reads are V/k1, not one N^2 final drain. This is
an explicit tiled materialization path with the original loop order, not an
exhaustive set of every legal DRAM implementation.

There are **192** internal decision tuples and **384** physical programs (two
backings). Across the two global arrays there are **432** legal environment
instances: 24 GB + 24 DRAM on 32x192, 192 GB + 192 DRAM on 64x96. Repeated
physical programs on two arrays are distinguished from new internal decisions.

The unchanged Tile choices make the 32x192 legal domain a subset of 64x96.
Consequently this study cannot establish an architecture-ranking reversal. We
kept that limitation rather than adding k=128 or inventing a shape penalty.
At the declared 128/132-KiB budgets, best EDP selects GB backing and 64x96;
changing capacity changes its selected stripe (128 to 256), not the winning
backing context. DRAM contributes genuine low-SRAM points to the complete
resource/energy/latency frontier; that is different from winning best EDP here.

## Context information really is necessary

Independent event execution finds **22** (shape,stripe,prefix) conditional
pruning witnesses, corresponding to **19** distinct internal prefix schedules.
In **18 scoped cases**, deleting a prefix according to the other backing context
removes at least one complete numeric frontier point. These are not 22 Jobs or
18 distinct globally best-EDP architectures.

One example, shape 32x192, stripe 64, after the first two Matmuls:

- P tiles: (32,32), (64,32).
- Q tiles: (32,32), (32,32).

| Physical context | P peak / energy / latency | Q peak / energy / latency | Safe comparison |
| --- | --- | --- | --- |
| GB backed | 89 KiB / 31.353471 uJ / 24.576 us | 89 KiB / 32.490127 uJ / 32.768 us | P dominates Q |
| DRAM backed | 26 KiB / 58.136723 uJ / 30.037333 us | 25 KiB / 89.895993 uJ / 43.690667 us | Tradeoff; retain Q |

With the unchanged suffix (32,32), Q supplies the 25-KiB complete DRAM frontier
point. Removing all completions of that prefix loses it. Prefix energies and
latencies above are not whole-program costs. All remaining suffix alternatives
were checked for the dominance claims in their declared dropped context.
[Raw witnesses](results/residency_contexts/summary.json) contain exact integer /
rational values and lost complete points.

This proves that a single context's pruned frontier cannot simply replace the
other's. It does **not** prove that sharing a conditional frontier is more
efficient than retaining the ordinary frontier for each context.

## Same preparation and queries for every algorithm

All three paths construct the same symbolic branches once and share the same
28 structural factor pairs (56 context-factor results) across all arrays and
contexts. Each may precompile its complete frontiers and reuse them for exactly
the same queries. Grounded DP is not forced to rebuild symbolic models per
context or budget. Conditional DP receives no private cache or oracle data.

| Work count | Cached Flat | Grounded DP | Shared Conditional DP |
| --- | ---: | ---: | ---: |
| Factor pairs / context-factor evaluations | 28 / 56 | 28 / 56 | 28 / 56 |
| Partial decision objects constructed | 252 | 231 | 148 |
| Scalar environment combinations | 588 | 231 | 372 |
| Complete decision objects before Pareto | 192 | 99 | 100 |
| Complete environment rows before Pareto | 432 | 99 | 240 |
| Retained root environment rows before final Pareto | 432 | 38 | 88 |
| Maximum retained intermediate objects | 64 | 4 | 12 |

A conditional object contains multiple outcomes. Counting it as one operation
would hide work: although it constructs fewer partial Python objects, it
performs **372** environment combinations against Grounded DP's **231**, and
materializes **240** complete environment rows against **99**. None of the
expensive factor evaluations is additionally avoided relative to Grounded DP.

## Timings including construction

Nine shuffled paired trials in one warm Python/Sympy process. Each invocation
starts with an empty shared factor cache, builds both branches, compiles all
four environments and runs the same four joint (shape,capacity) queries.
Memory is a separately traced Python allocation peak, not process RSS. Native
validation and independent enumeration happen after measurement.

| Path | Construction ms | Compile ms | Queries ms | Total ms | Python peak bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Cached Flat | 9.858 | 1.880 | 0.352 | 12.085 | 176,570 |
| Per-environment Grounded DP | 9.757 | 1.009 | 0.335 | 11.085 | 140,512 |
| Shared Conditional DP | 9.742 | 1.938 | 0.357 | 12.005 | 148,573 |

Shared conditional DP is **1.083x** the total time of Grounded DP
(about 8.3% slower), with about
1.92x compile time. It has no demonstrated end-to-end advantage over
Cached Flat either; its approximately 0.7% median difference is too small to
claim a practical gain from this microbenchmark. All paths are dominated by
common preparation. Raw samples are retained; these are not FFM DSE timings.

## Correctness and scope actually checked

- **384** independent full-size physical programs, 10,744,960 event/control/MAC-wave
  operations; exact resource and correlated cost agreement.
- **432** native fixed-map evaluations, **1,296** numeric phase models; all
  GB/DRAM/Register actions and MAC counts agree exactly, GB peaks agree in
  bits, E/T agree within relative 1e-12. Instrumented native validation took
  26.487 s and is not a search performance baseline.
- **512** small N=4/8 physical programs execute every dense scalar MAC, copies,
  versions, and accumulator checks against untiled arithmetic. Full-size event
  execution does not pretend to execute all 19+ billion scalar MACs.
- All four environment frontiers match independent exhaustive results. All
  three paths' joint results agree at **70** capacity thresholds, including
  every attained peak and +/-1 byte; no final-EDP-only comparison is used.
- Every shared prefix dominance is tested against legal suffix continuations.
  The contextual deletion witnesses additionally check the complete Oracle
  frontier after removing that prefix, distinguishing actual losses from ties.
- **130 tests pass:** 32 symbolic-study tests and 98 existing synthesis tests.
  The full production FFM suite was not rerun. This is equality within the
  declared grammar/model, not equivalence to FFM's unrestricted RU/fallback
  search or native floating-point tie-folding history.

## Why the algorithmic gate fails

Context dependence is real, but the expensive preparation is already shared by
an ordinary cached factor library. The conditional implementation still stores
and combines an outcome per legal environment. Pointwise dominance also keeps
states that one context could discard on its own. Fewer decision objects do not
outweigh the additional outcome computation and dominance work.

There is also a quantifier distinction. The current `covers()` test requires
**one** replacement plan that dominates Q in **every** environment carried by Q:
`exists P, forall c`. Architecture–Mapping co-optimization, however, permits a
different Mapping after selecting the global environment. Within this fixed,
sufficient-interface grammar, Q can also be dispensable when
`forall c, exists P_c` with a valid dominator in each environment. This is a
weaker requirement; the single-witness envelope can retain a plan that no
individual context needs. The retained-root-row difference (88 versus 38 before
final per-context Pareto) is consistent with that conservative representation;
it is not evidence of additional useful solutions.

This is a diagnosis, not a new theorem claimed as research novelty. For a finite
list of known environments, storing context-specific winners recovers ordinary
context-wise Pareto/membership processing. An independent method would need to
represent that conditional **selection relation** compactly without merely
enumerating a table for every environment. Neither this experiment nor the
single max-affine function establishes such a representation. No new solver is
implemented on the strength of this observation.

The two branches are manually specified and separately symbolically compiled;
this is not an automatically generated, context-parametric Physical Execution
IR. More contexts could increase both construction and envelope sizes. These
data establish no sublinear context representation or unseen-context reuse.

**Preserve the execution semantics, oracle and negative comparison; stop
expanding this conditional-vector DP as a claimed core method.** We now have
positive evidence for context-sensitive legality/quality and a negative result
for the tested shared representation. This does not prove that every compact
resource-effect representation must fail, but it does not justify adding
Graph DP, more contexts, Tile choices or optimizations to this implementation.

## Evidence and reproduce

[Summary / timings / witnesses](results/residency_contexts/summary.json),
[Oracle records](results/residency_contexts/oracle_records.json.gz),
[native records](results/residency_contexts/native_records.json.gz),
[test receipt](results/residency_contexts/tests.txt),
[execution log](results/residency_contexts/execution.log.gz).
The manifest fingerprints every saved artifact; the summary fingerprints source.

```sh
python -m pytest -q research/symbolic_fusion/tests research/joint_synthesis/tests --disable-warnings
python -m research.symbolic_fusion.residency_experiment --native --output research/symbolic_fusion/results/residency_contexts
```
