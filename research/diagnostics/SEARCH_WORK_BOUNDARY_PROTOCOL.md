# Frozen search-work boundary diagnosis

Source base: `9e1002dca5146f58f8264fc8abb9613b3f595098`. Freeze
`SearchPolicy`, `StageCatalog`, `TwoMMSearch`, physical plans, composition,
architecture binding, Oracle, symbolic fusion and native FFM. Add diagnostic
code/tests only. This is not a new candidate provider or search algorithm.

## Questions and matched space

Where do candidate creation, local analytical evaluation, property grouping,
composition and Pareto maintenance actually occur? Which work does the existing
pruning avoid, and which work has already happened before it can act?

Use the unchanged two-MatMul, complete-materialization grammar, uniform checked
16-bit copies, default normalized `CostModel(1,1,8,1)`, no supplied architecture
points and no Oracle inside search. Shapes `(M,K,N,P)`:
`(2,2,2,2)`, `(2,3,4,5)`, `(4,4,4,4)`.

Compare three existing policies with identical divisor-tile/loop/interface and
direct/spill grammar: no local/layout pruning; local Pareto only; current default
local Pareto plus layout theorem. Full six-dimensional numerical frontiers must
agree. Each policy's own exact returned plans and complete statistics must match
between uninstrumented cold/warm searches and its observation pass. Equal-vector
source folding can make plan identities differ between policies.

This does not compare independently searched architectures or claim a wider
mapspace. Hardware binding/queries and scalar execution validation are outside
the search timers. Existing Oracle tests remain the physical correctness
reference; instrumentation equivalence does not independently prove the model.

## Measurement

Three fresh serial processes per shape/policy; alternate policy order by repeat.
One cold and one warm full search per process, fresh provider/candidates/catalogs
and frontiers each time. Imports/startup and result serialization are excluded.
Keep all raw samples and ranges; report warm medians. No performance target or
new-method speedup is inferred from these small-instance diagnostics.

Repeat 1 has one additional observation pass. Temporary wrappers observe the
existing calls in an isolated, single-thread process and restore every attribute
on exit. They are not an engine API or enabled in ordinary search. Recursive
inclusive times nest. Exclusive named-scope remainders subtract instrumented
children and partition the observed search interval exactly, but include wrapper
overhead and uninstrumented helpers. Never treat them as uninstrumented phase
medians or rescale them by the uninstrumented total. Report observation slowdown.

Count per stage: actual KernelPlan construction, `summarize` calls, candidates,
retained states, Pareto inputs/checks/pruned states and largest *single-interface*
frontier. Count actual `compose`, conversion, CompletePlan construction and root
Pareto input calls independently, then reconcile with engine statistics. Raw
alternatives are a counterfactual grammar size, not actual allocations. A complete
plan here is a `CompletePlan` source object, not an AccelForge native Mapping.
The default provider eagerly constructs both stage tuples. Its total generation
scope includes shared setup; per-stage construction subscopes do not allocate
all shared generation overhead to a stage. Local grouping includes its own
validation remainder; it does not include nested evaluation/Pareto a second time.

No candidate identities, boundary keys, graph information or lower bounds are
used to optimize the observed run. No provenance wastage is reclassified as
safe pre-generation elimination. This is not an RSS/memory benchmark.

## Correspondence with native FFM profiling

Use the archived `SEARCH_COST_3MM.md`/raw receipts as historical evidence, **not a
new run**. Restricted provider creation roughly corresponds to a portion of
`get_jobs`/template choice creation. Restricted `summarize` evaluates an already
concrete plan with scalar formulas: it is not equivalent to FFM's symbolic
reuse/latency/energy construction or tile-domain solver. Restricted property
grouping/local Pareto overlaps conceptually with generation batch filtering and
Pareto. Restricted `compose`/conversion/root Pareto correspond conceptually to
parts of native numeric Join/reservation/Pareto, but not its fused loop scopes,
alias/free operations, membership, fallback or stage policy.

Native FFM's `make_pmappings` **includes** generation, evaluation, materialization
and local Pareto. Therefore the matching coarse restricted boundary must also
include provider + catalogs, not just `generate()`. Restricted grouping keys and
whole CompletePlan counts cannot be equated with native Job, compatibility-batch
or numeric row-occurrence counts. Native symbolic-model construction has no
separate counterpart in the restricted engine.

The archived native workload is 8-bit NVDLA `matmuls(3,256,256)`, six concrete
hardware points, native Fusion and RU/target-policy semantics. The independent
2mm workload is 16-bit with normalized prices and full materialization, and
architecture is bound later. There is **no same-contract speed/quality ratio**
between these experiments. No native search rerun is required by this protocol.

## Delivery and stopping rule

Save protocol/source hashes, environment, cold/warm samples, exact-front checks,
observed counts, named inclusive/exclusive scopes and observation overhead.
Inspect the boundaries, not just retained-state ratios. A post-evaluation
reduction only demonstrates avoided downstream composition, not avoided local
generation/evaluation. Do not select a new mechanism from these numbers alone.
