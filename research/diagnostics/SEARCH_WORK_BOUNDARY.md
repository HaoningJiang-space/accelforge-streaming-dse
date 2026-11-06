# Search-work boundary: existing pruning avoids composition, not local evaluation

The refactored 2mm engine still constructs and evaluates **every local candidate**
before its existing pruning can act. Local Pareto and the layout theorem avoid
downstream complete-plan construction; neither reduces candidate creation or
`summarize` calls. This diagnosis does not select a new algorithm or reopen the
search-engine refactor.

The [protocol](SEARCH_WORK_BOUNDARY_PROTOCOL.md) and observation code were frozen
at `d121f6fcce7442b046c2db48220e98aa396a0113`, based on `9e1002dc`.
[Raw results](results/search_work_boundary/summary.json) contain 27 fresh-process
trials: three shapes, three existing policies, three repeats. Search/model/Oracle
and FFM sources are unchanged. There is no new candidate provider. Native 3mm
figures below are historical receipts, not newly executed measurements.

## Actual work under the same restricted grammar

All modes use the same divisor tiles, three loop orders, four materialized
properties and direct/spill alternatives, with the same normalized cost model.
"Unpruned" disables local and layout pruning; root Pareto remains necessary to
return a frontier. "Local only" enables the existing local Pareto; "default"
also enables the already-proved free-layout rewrite.

| Shape M,K,N,P | Policy | Created/evaluated producer + consumer | Retained producer + consumer | CompletePlan constructions | Root vectors | Warm median ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2,2,2,2 | Unpruned | 96 + 96 | 96 + 96 | 10,368 | 19 | 67.121 |
| 2,2,2,2 | Local only | 96 + 96 | 42 + 37 | 1,682 | 19 | 13.193 |
| 2,2,2,2 | Default | 96 + 96 | 42 + 37 | 1,426 | 19 | 11.877 |
| 2,3,4,5 | Unpruned | 144 + 144 | 144 + 144 | 23,328 | 79 | 254.385 |
| 2,3,4,5 | Local only | 144 + 144 | 72 + 52 | 4,004 | 79 | 54.111 |
| 2,3,4,5 | Default | 144 + 144 | 72 + 52 | 3,484 | 79 | 50.277 |
| 4,4,4,4 | Unpruned | 324 + 324 | 324 + 324 | 118,098 | 126 | 2,055.021 |
| 4,4,4,4 | Local only | 324 + 324 | 156 + 118 | 19,696 | 126 | 436.739 |
| 4,4,4,4 | Default | 324 + 324 | 156 + 118 | 17,120 | 126 | 410.116 |

The complete six-dimensional numerical frontiers agree across all policies and
repeats, not just best EDP. Within each policy, cold/warm and observed executions
also have identical complete source plans and entire engine statistics. Different
policies may fold equal-vector sources differently. These timings characterize
existing behavior on this host, not a new-method improvement or an architecture
co-optimization benchmark. Cold samples and all warm ranges remain in the raw
results; imports and serialization are outside the search timers.

Counts above independently reconcile actual KernelPlan constructors with local
evaluation calls, and CompletePlan constructors with `compose`, conversion and
root Pareto inputs. CompletePlan is this grammar's source object, **not** a
reconstructed native AccelForge Mapping. No architecture points are supplied;
hardware binding occurs outside this measurement.

## Per-stage evaluation and state maintenance

Default policy, one separate observation pass per case:

| Shape | Stage | Evaluation calls | Local Pareto checks | Largest single-interface frontier | Constructor ms | Evaluation ms | Grouping remainder ms | Local Pareto add/finish ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2,2,2,2 | Producer | 96 | 784 | 13 | 0.078 | 0.136 | 0.295 | 0.799 |
| 2,2,2,2 | Consumer | 96 | 647 | 13 | 0.065 | 0.131 | 0.175 | 0.483 |
| 2,3,4,5 | Producer | 144 | 2,238 | 23 | 0.102 | 0.187 | 0.259 | 1.465 |
| 2,3,4,5 | Consumer | 144 | 1,396 | 22 | 0.095 | 0.185 | 0.245 | 0.946 |
| 4,4,4,4 | Producer | 324 | 10,036 | 50 | 0.224 | 0.464 | 0.563 | 6.256 |
| 4,4,4,4 | Consumer | 324 | 6,993 | 50 | 0.249 | 0.471 | 0.585 | 4.401 |

Constructor subscopes exclude shared provider setup. The eager provider produces
both stage tuples in one call; its inclusive time is 0.413/0.548/1.653 ms. Do not
add constructor times to those inclusive values. Property grouping excludes its
nested evaluation and Pareto; its remainder includes validation/helper overhead.
Largest-interface frontier is neither the sum of retained states nor a measured
memory peak.

## Additive observed phase boundaries

All values in this table are **instrumented exclusive named-scope remainders**,
in milliseconds. They partition that observed search interval exactly before
rounding. They are not uninstrumented phase medians and must not be added to the
wall-time medians above.

| Exclusive boundary | 2,2,2,2 default | 2,3,4,5 default | 4,4,4,4 default |
| --- | ---: | ---: | ---: |
| Provider/candidate generation | 0.413 | 0.548 | 1.653 |
| Catalog control/validation | 0.136 | 0.174 | 0.389 |
| Interface grouping | 0.470 | 0.503 | 1.148 |
| Local analytical evaluation | 0.267 | 0.372 | 0.935 |
| Interface routes/layout analysis | 1.190 | 3.151 | 21.360 |
| Composition control | 3.378 | 8.446 | 42.501 |
| Conversion evaluation | 1.207 | 3.005 | 15.335 |
| CompletePlan construction | 0.932 | 2.283 | 11.564 |
| Local + root Pareto maintenance | 7.415 | 39.430 | 354.774 |
| Remaining search control/statistics | 4.031 | 10.250 | 50.414 |
| Observed search total | 19.440 | 68.161 | 500.072 |

Default root Pareto performs 8,341 / 55,895 / 533,350 dominance checks on
1,426 / 3,484 / 17,120 complete inputs. Root frontier peaks are 20 / 80 / 130
states; final sizes are 19 / 79 / 126. The observation attributes 38.1% / 57.8% /
70.9% of the observed interval to Pareto maintenance. These are descriptive
instrumented shares, not bounds on achievable uninstrumented savings.

Across all nine observation passes, observation wall time divided by that
process's uninstrumented warm time ranges from **1.24 to 3.71**. The large
perturbation makes absolute phase-time extrapolation inappropriate. Deterministic
work counts and exact output/statistics equality are the stronger evidence.
Wrappers are removed after each pass, including on errors; no production hook,
global configuration or engine interface was added.

## Correspondence with native FFM Generation

The archived [native 3mm profile](SEARCH_COST_3MM.md) reports Events + Cache RU
Generation 5.521 s and Join 0.855 s within a 6.431 s instrumented six-target run.
Generation is 85.9% of that **same observation**. Its separate warm median is
6.467 s. These historical numbers are not recomputed in this experiment.

| Restricted 2mm boundary | Native profiler boundary | Meaning and limit |
| --- | --- | --- |
| Provider/Schedule/KernelPlan construction | Part of `get_jobs`/template preparation | Concrete local plans versus symbolic Job families; counts have different units |
| `summarize` on each concrete KernelPlan | Parts of model evaluation/materialization | Scalar closed formulas; no equivalent of native symbolic reuse/latency/energy construction or tile-domain solving |
| Catalog property grouping + local Pareto | Compatibility batching, generation filtering/Pareto | No native target fallback, stage Pareto history or membership semantics |
| `compose` + conversion | Parts of numeric Join/resource evaluation | Complete materialized cut; lacks native Fusion scopes, ownership transfer/alias/free operations |
| Root Pareto | Parts of native group/final Pareto | Restricted six-dimensional state objectives versus native metric-dependent columns/policy |

**Native Generation is not just the restricted Provider.** The named provider
and catalogs together take 2.568 / 4.007 / 14.782 ms inclusively in the three
default observation passes (non-overlapping top-level scopes). This is a useful
coarse preparation boundary, with remaining engine validation accounted under
control. It is still not the same computation as `make_pmappings`.

Native Events recorded 126 model-template evaluations, 8,994 model rows and
55,394 matched Join row occurrences; the restricted engine's 192/288/648 local
candidates and complete objects are different quantities. In particular, FFM's
1.647 s symbolic-model scope has no matching expensive symbolic-construction
stage here. A cheaper restricted `summarize` does not demonstrate reduced native
model evaluation. Native observation sources are linked and hashed in the
[manifest](results/search_work_boundary/manifest.json).

The native experiment uses fused 8-bit NVDLA 3mm, six concrete hardware targets,
and RU/policy-aware search. This experiment uses normalized 16-bit materialized
2mm and no hardware target during search. No cross-system speed, quality or
candidate-coverage ratio is valid. The difference in bottlenecks is a limitation
of transferring findings between the two engines, not a reason to redirect the
research toward optimizing this toy engine's Pareto routine.

## Research boundary after this diagnosis

The stable Candidate Provider seam now has a measured baseline: one actual
construction and one evaluation per local candidate. The existing reductions
take effect after those costs. A smaller retained set or fewer complete objects
therefore cannot be reported as generation-before-evaluation elimination.

RQ2 remains open. This diagnosis provides no new safe boundary representation,
no pre-generation elimination certificate and no evidence of a graph-specific
advantage over ordinary DP. Any future mechanism must identify which measured
native generation work it avoids, with equivalent physical coverage and goals;
it cannot inherit an efficiency claim from these restricted composition savings.
No new optimizer, execution grammar or algorithm choice follows from this report.

## Reproduction and validation

```sh
python -m research.diagnostics.profile_search_work --repeats 3 --output research/diagnostics/results/search_work_boundary
python -m pytest -q research --disable-warnings
```

The [summary](results/search_work_boundary/summary.json), per-trial JSON files and
[raw logs](results/search_work_boundary/trial_logs.zip) retain all samples,
complete numerical fronts, source-plan hashes, observations and source
fingerprints. Nine focused diagnostic tests cover independent scalar
execution of the tiny grammar, exact behavior preservation, constructor/call
accounting, nested timing partition and exception-safe restoration.

The actual full research regression passed **873 tests, 29,578 warnings, in
278.09 seconds**: the previous 864 tests plus these nine diagnostics. See
[tests.txt](results/search_work_boundary/tests.txt) and the
[execution receipt](results/search_work_boundary/execution_receipt.json).
This is a research-suite result. The previously documented three legacy
`tests/test_ffm_*.py` collection failures remain outside this suite; those files
were not modified or rerun in this diagnosis. No repository-wide production-test
pass or new native FFM benchmark is claimed.
