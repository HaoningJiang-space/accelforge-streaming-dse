# Compiling all single-operator templates

This extends the [one-template interpreter](PARAMETRIC_TEMPLATE.md) to the
complete six-template catalog generated for one 256x256 MatMul on the configured
NVDLA model. It compiles a family before query points exist, including the
**cross-template terminal Pareto union**. A query performs neither enumeration,
cost-model evaluation nor Pareto. [Results](results/parametric_operator/README.md)
include the negative performance result against the existing cache at 256 queries.

## Construction

`prepare_all()` calls the normal template generator once and captures every
template's symbolic model immediately before Tile enumeration. There is no
template count limit or selection using query costs. The benchmark requires all
six distinct identities and compares them to independently constructed physical
FFM searches. The underlying perfect-tiling, fixed-cost NVDLA adapter is unchanged.

Each template is compiled with `CompiledTemplate`. Its integer-bit capacity
boxes are converted to inclusive integer-byte boxes using `ceil(lo/8)` and
`floor(hi/8)`; an interval containing no integer-byte query is discarded.

The joint execution partition starts with the entire family. Introducing a
template refines each cell by its local leaf regions. Intersections have the
corresponding local leaf ID; uncovered pieces have `None`, meaning that this
template has no selected candidate there. Box subtraction keeps these holes
explicitly: another template may still serve those architectures.

A joint cell is identified by a vector of six local leaf IDs (or `None`). All
selected Tile sets are constant inside it. At this terminal single-operator
boundary, compare the full `(Energy, Latency, GlobalBuffer bits)` vectors across
all available templates and retain their Pareto frontier. There is no future
consumer or Fusion interface to distinguish here. Local terminal frontiers may
be reduced first because `Sky(union A_i) = Sky(union Sky(A_i))` under this common
exact comparison relation.

Every retained row has a source `(template index, Tile row index)`. Equal vectors
keep a deterministic available source. Finally, cells can merge only when they
retain the **same source-ID frontier**, not merely the same numeric costs. This
prevents a Mapping valid only in one region from being substituted into another
region with equal-cost but differently available candidates. Disconnected boxes
remain representable. Queries outside the declared integer family fail.

## Conditional projection argument

Assume that the template catalog is complete and stable for the supported family,
each local region projection matches the corresponding independent FFM template
program, and fixed assignments have architecture-independent costs in this model.
For any supported integer architecture:

1. Joint-box refinement preserves exactly one containing cell, including empty
   template portions, by disjoint intersection and subtraction.
2. That cell selects each template's exact independent candidate set.
3. All complete mappings are comparable using the common terminal objectives.
   Reducing the union therefore yields the independent whole-operator frontier.
4. Its source ID refers to a candidate actually present in that cell. Merging
   cells with identical source frontiers preserves this property and reconstruction.

The independent physical audit checks the template set, every template's complete
selected Tile set (canonical array digest including dtype and symbols), the full
terminal frontier, and reconstruction of every returned frontier row at sampled
targets. It calls the normal `make_pmappings + join_pmappings` route, without
replacing its templates or enumerator. Separate tests compare literal Tile arrays.

This is equivalence to the configured FFM policy. It is not exhaustive enumeration
of every physically possible Mapping, nor a proof that FFM's ordered fallback and
prefix Pareto policy is globally optimal. The local parameter adapter still has
its stated restricted scope. Unit costs, bandwidth and zero leakage remain fixed.

## Representation and scope

On this family, the six local compilations end with 2,394 boxes in total. Their
common refinement has 1,382 cells. Final source-aware Pareto grouping retains
255 frontiers in 255 boxes, referencing an 8,004-row template/Tile cost catalog.
The implementation also retains local choices and execution cells for coverage
audits; this is not a minimum-memory serialized representation.

Final compactness does not imply cheap construction. Two templates reach 715,873
and 859,854 rows across their live regional states. Across six templates, 901
prefix Pareto calls are executed; the earlier real one-template experiment had
none. State limits still fail explicitly and are not a process-wide memory bound.
Joint refinement likewise raises on its box budget; it never silently returns
a partial catalog.

**This terminal three-objective frontier must not be used as a Fusion partial
frontier.** Two connected operators require full FFM compatibility, component
latency, live Tensor copies and Reservation/lifetime semantics before any safe
composition or dominance. Neither matching regions nor adding the three terminal
scalars establishes legal Fusion. That next stage is deliberately not implemented
by this class. Parameter-dependent bandwidth/energy costs are also still absent.

## Entry points

- `parametric_operator.py`: complete preparation, box overlay, terminal Pareto
  and source-preserving queries. Construct with the full `prepare_all()` catalog.
- `benchmark_parametric_operator.py`: regions, prepared per-query FFM, and
  prepared FFM with the existing bounded `EnumerationReuse` cache. Each method
  runs in its own process; validation occurs after all timing and cache scopes.
- `audit_parametric_operator.py`: one independent projection per joint cell,
  then normal physical FFM searches and all-frontier Mapping re-evaluation.
- `summarize_parametric_operator.py`: rejects mismatched candidates/frontiers,
  including earlier repeats, before reporting costs and producing the query curve.

The API is an in-memory research representation. Source IDs are local to its
compiled catalog; saved benchmark JSON is not a loadable persistent Memo.
