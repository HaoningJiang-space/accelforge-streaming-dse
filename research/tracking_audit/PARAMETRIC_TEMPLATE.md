# Integer architecture regions for one FFM template

This is an opt-in research interpreter, not a replacement for the library mapper.
It compiles one fixed, unfused NVDLA MatMul template over an integer architecture
family **before any query points are supplied**. Queries return that template's
selected Tile assignments, complete `(Energy, Latency, GlobalBuffer bits)` final
frontier, and a reconstructable best-EDP Mapping. They do not run Tile enumeration
or the cost model. Results and break-even measurements are in
[the experiment record](results/parametric_template/README.md).

## What changes relative to finite-target enumeration

`TargetEnumerator` associates a state with a set of declared target IDs. The
new `RegionEnumerator` associates it with a union of disjoint integer boxes:

```
state = (ordered partial Tile assignments, prefix Pareto history, boxes)
box   = [Px_lo, Px_hi] × [Py_lo, Py_hi] × [C_bits_lo, C_bits_hi]
```

The program counter, symbol relations, active objective list and loop checks
are common to all states at a given step. Only bound values depend on the
parameters. No list of future architectures and no target-optimal Mapping is
accepted by `build()`.

For a fixed state's candidate values `v`, a maximum constraint `v <= p` changes
only at `ceil(v)`. A minimum constraint `v >= p` changes only at `floor(v)+1`.
These attained values split the boxes. An ordered min-usage fallback is applied
**within each resulting region**, after all earlier constraints; it is never
applied to the union of different regions' candidates. Equal ordered arrays,
dtypes and complete Pareto histories can share subsequent expansion. Adjacent
boxes may coalesce only if their other axes agree. Disconnected regions remain
disconnected.

The implementation uses FFM's existing symbol order, partial-value padding,
loop checks, symbolic goal analysis and exact-zero-tolerance Pareto helper.
It preserves the original policy's decision to skip prefix Pareto below 100
rows and its history-based skip rule. It does not replace the policy with
complete-candidate fallback or claim that this policy finds every physically
valid Mapping.

## Projection argument and its assumptions

For the supported bound-parameterized program, let `I(p)` be the independent
FFM interpreter at an integer point `p`. The intended invariant at every program
position is: the unique live region containing `p` has exactly `I(p)`'s ordered
partial assignment array, dtype and pruning history. A point with no live state
has the same empty result as `I(p)`.

1. Initially both have the same empty prefix, symbol relations and objectives.
2. Expansion and loop checks are deterministic functions of that prefix and the
   common program position, so their output is identical for the whole region.
3. Within an event box every bound predicate is constant. Thus the retained row
   mask, whether fallback is needed, and its highest reachable value match the
   independent invocation at every integer point in that box.
4. Fixed-objective constraints and Pareto have identical numerical inputs and
   history. They retain the same ordered rows. The proof requires using the
   same numerical comparison semantics, not an epsilon or rounded resource
   threshold.
5. Coalescing identical arrays **and histories** only unions their parameter
   sets; it cannot change any projected execution. Keeping only current arrays
   would be insufficient, as a later Pareto skip depends on the history.

Induction gives `query(p) == I(p)` for this interpreter's supported raw-bound
program. It is not a proof for arbitrary architecture-dependent expressions,
imperfect tiling, arbitrary FFM template generation, Fusion composition or the
complete physical Mapspace. The adapter from a physical architecture to this
program is an additional obligation, tested independently below.

In particular, a single candidate need not occupy one interval or one box.
The regression with resource `x*z+y` and ordered fallback preserves Tile
`(2,1,2)` at capacities `[5,6] ∪ [26,128]`, matching independent raw-resource
FFM at every integer capacity. That test executes actual prefix Pareto.

## Restricted physical adapter

The experiment fixes the NVDLA topology, workload, unit action costs, bandwidth,
zero leakage, 8-bit Register, storage placements and loop template. It varies
two positive fanouts and GlobalBuffer capacity. It selects the lexicographically
first canonical unfused template, without consulting query costs or winners.
Preparation at the family's upper corner stops **before Tile enumeration**;
it does not start from that corner's pruned candidate catalog.

For this perfect-tiled, power-of-two MatMul, each spatial usage constraint is a
single integer Tile extent divided by a positive fanout; min_usage is one.
The adapter uses that raw extent with an integer fanout bound. Positive scaling
preserves usage order and the set of fallback ties; equality at full utilization
is exact in the original model. GlobalBuffer already uses the original exact
bit expression, including during prefix analysis. Public capacities are integer
bytes and are converted to bits only once.

For a fixed Tile assignment the action costs and latency formula do not change
with unused array capacity in this fixed-cost, zero-leakage model. The compiled
table evaluates these formulae once for each distinct surviving assignment, then
retains per-region final frontiers and Tile provenance. It does **not** assume
the same Mapping is selected at every architecture. A new physical architecture
is separately constructed for every audit query to test both this normalization
adapter and cost invariance, rather than comparing two backends sharing a possibly
incorrect maximum-architecture resource expression.

The saved real-template run does not trigger prefix Pareto: its per-region
prefixes remain below FFM's threshold. The synthetic regression above tests that
part of the interpreter separately. Agreement of this one template is not
agreement with the optimum over all six NVDLA MatMul templates.

## Costs, limits and failure behavior

Work depends on distinct intermediate states, event cuts, region fragmentation
and unique final Tile assignments. It is not generally independent of domain
size, and may be worse than independent search for a small number of queries.
Boxes can multiply across axes. No polynomial-size or one-interval guarantee is
claimed; the archived experiment measures the actual counts.

The constructor rejects imperfect tiling, nonzero Pareto tolerance, mapspace
counting, empty symbol programs and inexact parameter bounds. The NVDLA adapter
also rejects unsupported spatial formulae, non-unit usage thresholds, fused
symbols and non-power-of-two workloads. State-row and box budgets raise an
explicit error; they do not delete candidates. These checks are **not** a process
RSS limit: an expansion occurs before its output-size check, and all compiled
states and final frontiers remain in host memory.

This prototype does not provide arbitrary bandwidth-cost functions, Fusion Copy
contracts, other topologies, an on-disk persistent Memo, or a bound on full DSE
cost. It establishes a testable separation between compiling a parameter family
and answering architectures that were not supplied during compilation.
