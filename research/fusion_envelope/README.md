# Parametric native-cost lower envelopes

Experimental, Chat GPT-6 Extra High supervised research. **External SOTA remains
unverified.** This route extends geometry-only pruning with actual native mapping
costs, storage capacities and correlated E/T bounds. It does not enable the failed
shared Tile-policy prototype.

## Declared search and mathematical inclusion

The global master selects physical array dimensions and SRAM under the common PE
and SRAM ceilings. A conditional mapping relaxation supplies lower bounds for that
same hardware; the native oracle supplies feasible complete mappings. Every
incumbent is independently evaluated on its original physical hardware before it
can eliminate other hardware. Reference data is opened only after the search.

For each raw ordinary-compute template, intercept native `_make_tile_shapes`
immediately before numeric enumeration. Retain its native symbolic E/T, hard
memory constraints and rank-factor relations. Drop min-usage preferences,
ordered fallback, loop-count limits, Pareto history and inter-operator compatibility.
Thus every local native candidate remains represented. The captured costs already
include each template's storage/fusion choices; no compulsory intermediate DRAM
traffic is invented. Additional copy operations have nonnegative costs and can be
omitted by the relaxation.

Costs sum across operators in the frozen FFM model. Taking independent template
minima is a relaxation of a *common* hardware's complete graph: it permits
inconsistent fusion choices, rather than equating raw Compatibility matches with
composed-prefix semantics. This can be loose. It is not an exact fusion-lifetime
solver or a proof of all-physical-mapspace optimality.

For perfect power-of-two ranks, write every tile as `s=2^x`, where native x is an
integer. The LP relaxes x to a real variable in its full finite range. For every
integer z and k:

```
2^k (z-k+1) <= 2^z.
```

Use those discrete secants as epigraph inequalities for positive Laurent
monomials. All native integer assignments satisfy every inequality. Negative
monomials use the upper chord over their entire exponent range, so their cost
contribution is weakened downward. `Max` costs use epigraph inequalities. Memory
constraints use the same underestimator, making them necessary rather than
sufficient constraints. Unsupported expressions contribute zero, never exclusion.

Spatial bounds are derived exactly from the mapping's product of spatial loop
iteration factors, with `sum(exponent*x) <= floorlog2(physical fanout)`. They do not
depend on floating normalization by a virtual preparation architecture.

The LP solver is a proposal mechanism. For `Aq<=b`, nonnegative variables with
known native upper bounds U, and any rational dual y<=0, check the bound:

```
c0 + b'y - sum_j max((A'y-c)_j,0) U_j.
```

This residual correction makes dual checking exact without trusting solver
tolerances. Phase-I duals must yield a strictly positive exact contradiction
before a template can be declared infeasible. Since hardware appears only in
the RHS (SRAM bits and spatial log bounds), checked duals become cheap parametric
functions reusable at other physical hardware. Cache sharing includes tensor and
loop structure, backing/fused flags, rank bounds and actual component cost fields.

For the frozen NVDLA hierarchy, raw template generation reads cumulative component
fanouts; all factor pairs with product 6144 have identical raw grammar. The
implementation pins that source directory before using a shared raw catalog.
**This shares no numeric Tile set, fallback decision or Pareto history.** Each
visited hardware's complete mapping search still runs its own native policy.
The first 96-point experiments independently generated each raw catalog and
observed the same 32 Attention model identities at all 24 shapes.

## Correlated objective

Besides E and T, minimize `E + lambda*T` for five frozen nonnegative lambda values.
Each graph-wide support value is the sum of its operator's minimum checked bound.
Minimize E*T over the upward polygon defined by these lines and the E/T axis
bounds. The product is concave along each descending boundary segment, so the
minimum is at a vertex. `correlated.py` enumerates those vertices with rational
arithmetic. This preserves the joint cost tradeoff that multiplying independent
E/T minima loses.

Both objective kinds retain the deliberately conservative 0.99 numeric weakening.
That is **not a universal floating-point error theorem**. All used bounds and
support lines must additionally pass a finite audit against every full reference
frontier vector. Certificates concern the declared native-policy experiment.

`check_certificate.py` independently replays serialized rational matrices/duals,
infeasibility contradictions, bound aggregation, polygon minima, physical
incumbent provenance, complete reference vectors and global optima. It uses the
standard library only, without SciPy, SymPy, NumPy or the mapper. The separate
native-to-relaxation inclusion argument above remains a model proof obligation.

## Diagnostic evidence, before formal repetitions

| Attention128 native experiment | Native shape solves | Skipped hardware | Diagnostic seconds |
| --- | ---: | ---: | ---: |
| Original-policy Event+Bitset+global cache | 24 | 0 | 102.793 |
| Independent E/T LP, first version | 22 | 22 | 101.224 |
| Correlated E/T LP + adaptive separation | 17 | 48 | 87.139 |

All four global EDP optima match the exhaustive original-policy reference exactly.
The standalone checker verifies 1,981 dual functions, 96 bounds, all 4,188 full
native vectors and all 48 incumbent cuts for the correlated run. These versions
precede the exact spatial-factor derivation and catalog-family shortcut; they are
diagnostics, not five-run medians for the current implementation. Source hashes
and complete rational LPs are retained in each report.

A separate counterexample experiment removes only the mapper's spatial minimum
usage *preference*, preserving every physical fanout, SRAM and action cost.
All chosen mappings reconstruct on the original physical spec. Across the 12
Attention128 points, per-point EDP improves by up to 1.651x. Across the full
12-point domain, the four budget optima improve from
`1.6277982e-10 / 1.0745157e-10 / 7.7192463e-11 / 4.0618267e-11`
to `1.4112041e-10 / 9.7083215e-11 / 7.6584027e-11 / 4.0618267e-11`.
This broadens the searched mapping policy. It must not be presented as original
policy frontier equivalence, and both competitors must receive this same broader
policy in the next fair comparison.

## Reproduction

Use the documented Windows runtime wrapper. `search` supports `events`, `shape`,
`lp` and `correlated`, on original or relaxed mapper preferences. The same shape
order, capacity query code, Event+Bitset+cross-shape cache, physical costs and
incumbent reconstruction apply to each control. All LP/model/dual work is timed.
First-shape anchors and the 2/3 adaptive-refinement ratio are frozen without
reference access. Source changes during a run reject that repetition.

```
./research/runtime/run_windows.ps1 -PythonArguments @('-m','research.fusion_envelope.search','--method','events','--policy','relaxed','--workload','attention','--domain','factors96','--output','research/joint_budget/results/envelope_attention96_relaxed_events_1.json')
./research/runtime/run_windows.ps1 -PythonArguments @('-m','research.fusion_envelope.search','--method','correlated','--policy','relaxed','--workload','attention','--domain','factors96','--reference','research/joint_budget/results/envelope_attention96_relaxed_events_1.json','--output','research/joint_budget/results/envelope_attention96_relaxed_correlated_1.json')
.venv/Scripts/python.exe -m research.fusion_envelope.check_certificate --report research/joint_budget/results/envelope_attention96_correlated_1.json --reference research/joint_budget/results/region_attention96_events_1.json
```

Do not call downloaded DOSA/DiGamma code a reproduced external SOTA baseline.
Those comparisons still need an implemented common evaluator and explicitly
matched mapping space; their native Gemmini/MAESTRO costs are not interchangeable
with NVDLA native costs here.
