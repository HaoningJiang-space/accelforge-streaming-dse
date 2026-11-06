# Symbolic Fusion subfamily: feasible representation, cautious research decision

**A and B pass in the declared finite family. C shows actual candidate avoidance
there, but does not establish reduced Generation or an end-to-end speedup in the
original FFM/Capacity Events search. Do not expand a general optimizer yet.**

This is the bounded experiment requested after `4baf7459`. Its source contract
was committed before exhaustive validation. Executed source is `792d38ab`;
[summary.json](results/summary.json) also fingerprints every experiment module,
the contract, native model source and NVDLA coefficients. No coefficients were
fit to native results. Original FFM and the existing `joint_synthesis` engine
remain unchanged. See [CONTRACT.md](CONTRACT.md) for the exact plan grammar,
service model, sufficiency proof, and native adapter boundary.

## A. Construct effects before enumerating concrete Tiles

The family consists of 192 plans for three 256x256 Matmuls: shared **n1** stripe
s in {64,128,256}, six reduction/output spatial Tile choices in {32,64}, fixed
64x96 configured array and native 8-bit NVDLA primitive action coefficients.
The rank is n1, not m; the old causal report's rank label is corrected.

Before evaluating any Tile, derive the producer's scoped response
`max(N*s+N*k0+k0*j0+x, y, z)` when s<N; the producer x term disappears at s=N.
The first consumer contributes `N*s+k1*j1+x`, and the last contributes
`N*j2+k2*j2+x`. Construct action polynomials from declared loop multiplicities,
then instantiate only needed local factors. Construction/search call neither
native Mapping generation, Symbolic Model, nor Join. This is a manually derived
restricted grammar, **not** an automatic extractor for arbitrary FFM templates.

For k=j=64 and x=64 KiB:

| Shared n1 stripe | Scoped GB peak | Energy, microjoules | Latency, microseconds |
| --- | ---: | ---: | ---: |
| 128 | 116 KiB | 32.217497600 | 13.312 |
| 256 | 132 KiB | 28.378136576 | 12.288 |

The interpreter reconstructs this from allocations and frees, not the peak
formula. In the striped case, T2 allocated during the first consumer remains
live beside later producer workspaces. At s=N there is no later producer stripe,
but full T1/T2 coexist in the consumer. The native adapter preserves fused W1
storage-scope syntax; it cross-checks the effective weight tile, rather than
claiming a literal one-to-one correspondence of every frontend Storage node.

## B. Preserve the response function, not a single sampled peak

Internal states retain `effect(x)=max(p,r+x)` (or constant p), correlated E/T,
and one plan witness. They are compared **pointwise for all x>=0**. Equality at
x=64 KiB alone is explicitly insufficient. A crossing-function regression and
exhaustive finite continuation checks validate that distinction. The contract
proves pointwise dominance by the intercepts and x=0 value, and monotonicity of
max/add composition. This proof is limited to this grammar's fixed physical
interfaces and ownership/lifetimes; it is not arbitrary-continuation equivalence.

| Work/state measure | Flat | Cached flat | Effect elimination | 128-KiB pushdown |
| --- | ---: | ---: | ---: | ---: |
| Local factor evaluations | 576 | 28 | 28 | 20 |
| All partial composition operations | 576 | 576 | 108 | 56 |
| Complete candidates actually materialized **before Pareto** | 192 | 192 | 60 | 24 |
| Complete conditional states retained | — | — | 20 | 8, budget-specific |
| Numeric frontier at x=64 KiB | 11 | 11 | 11 | 8 |

The universal conditional frontier has **20** correlated effect/E/T points,
not 11. Binding the known T2 obligation at the root leaves 11 numeric points.
The maximum retained intermediate frontier for any separator is 12. Complete
candidate avoidance is 192 to **60**, not 192 to 20: the latter would confuse
post-Pareto states with work avoided. The symbolic factor cache alone gives no
composition reduction, as the equally cached flat baseline demonstrates.

A 128-KiB query rejects all s=256 plans using the simultaneous-live lower bound
`N*s+N*N+min(k1*j1)>capacity` before evaluating that subfamily. It does not reject
an original FFM Job and is not a budget-universal compilation result.

## Independent checks actually executed

- Every one of the **192** full-size plans: independent event interpreter,
  5,358,848 allocation/control/MAC-wave events, exact per-phase action
  counts, scoped effects, GB peaks, energy, latency. Full-size enumeration is
  event execution, not billions of individual scalar MAC evaluations.
- Every fixed full-size plan also re-evaluated with the native model: **576**
  phase models. All GB/DRAM/Register actions and MAC counts match exactly; GB
  peaks match in bits; energy/latency agree within relative 1e-12. Native
  observation/evaluation took 11.169 s; this includes diagnostic
  overhead and is **not** a matched native search timing baseline.
- Independent exhaustive canonical effect/E/T frontier equals the conditional
  result before binding x. Independent exhaustive numeric frontier, flat,
  cached-flat, elimination, reversed order, and compiled-frontier reuse agree
  for **35** capacity queries, including every attained peak and +/-1 byte.
- **256** additional small plans (128 each at N=4/8) execute every scalar MAC,
  copy, and accumulator check using nonsymmetric inputs and distinct permutation
  weights, with an untiled arithmetic reference. There is no sparse-MAC skip.
- **117 tests passed**: 19 new experiment tests plus 98 existing synthesis tests.
  This is not a rerun of the entire production FFM regression suite.

These checks establish exact finite-grammar frontiers. They do not establish
identity of native floating-point tie-folding/fallback history or equality to
the unrestricted native RU frontier. x<N*N tests concern algebra only, not a
physically valid smaller allocation of an unchanged full T2.

## C. Count preparation and compare with the cached baseline

Nine shuffled paired trials in one warm Python/Sympy process; each invocation
rebuilds the symbolic family and starts with an empty factor cache. Table entries
are separately measured medians; construction is included in total. Python
startup/library import time is outside this warm protocol.

| Same-grammar path | Construct, ms | Search, ms | Total, ms |
| --- | ---: | ---: | ---: |
| Flat symbolic enumeration | 5.258 | 4.030 | 9.277 |
| Same factors cached; full combinations | 5.288 | 1.721 | 7.018 |
| Universal-effect elimination | 5.247 | 0.588 | 5.842 |
| Budget-pushed 128 KiB | 5.271 | 0.277 | 5.549 |

Including construction, elimination is **1.20x** faster than
cached flat, versus 1.59x versus uncached flat. The
search-only ratio of 2.93x must not replace the total. About
89.8% of elimination time is construction. Python-traced peak allocations
are about 127-129 kB across paths; there is **no material measured memory gain**.
These are small same-grammar microbenchmarks, not an FFM search speedup or a
scalability result. Raw trials and separately traced memory are in the summary.

No native Generation job/batch was skipped in the unmodified six-architecture
FFM experiment. The 576 native phase evaluations here belong to independent
fixed-map validation; dividing their time by the symbolic search time would be
an unfair speedup claim. Nor has the 53% G1 opportunity been converted into an
online certificate. Factor reuse is shared preparation; only 192 to 60 measures
additional complete-candidate avoidance from decision elimination.

## Decision

**Cautious: a sufficiently small correlated effect representation exists for
this specific real Fusion subfamily, but a new general search method is not yet
justified.** The pre-enumeration formulas, universal-effect dominance, and
independent event/native checks are useful positive evidence. The model still
fixes tensor residency, scope skeleton, ownership and service semantics; the
construction was manually derived; array shape is fixed. We have not shown cheap
automatic coverage of varying Fusion/residency/open-scope families or a benefit
over Capacity Events + Cache in the full six-architecture search.

Keep this bounded component and its evidence. Do not add Enforcers, general
Graph DP, or claim arbitrary subplan substitutability. A proposal to generalize
must first show that genuinely different native scope families share cheap,
sufficient symbolic summaries; success of this separable finite family does not
prove that proposition. No new optimizer expansion is authorized by these data.

## Reproduce

```sh
python -m pytest -q research/symbolic_fusion/tests research/joint_synthesis/tests --disable-warnings
python -m research.symbolic_fusion.experiment --native --output research/symbolic_fusion/results
```

Evidence: [summary](results/summary.json),
[event records](results/event_records.json.gz),
[native fixed-map records](results/native_records.json.gz),
[test receipt](results/tests.txt), [execution log](results/execution.log.gz).
