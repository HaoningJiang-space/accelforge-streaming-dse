# Native 3mm search cost: coupling is real, a new resource-transfer search is not yet justified

This follows the [causal diagnosis](CAUSAL_3MM.md), using the **same six hardware
points and native 8-bit workload**. It measures existing backends rather than
changing FFM or extending the independent Graph DP. Protocol/code were frozen
at `90e4e77b`; [raw results](results/search_cost_3mm/summary.json) and
[manifest](results/search_cost_3mm/manifest.json) record the executed sources.

**Decision:** this case does not currently justify implementing a new
Architecture-Conditional Resource Transfer Memo/Graph DP. Existing caching
already removes exact repeated prefix expansion, and Capacity Events remove much
of the repeated complete-capacity search. Remaining Join work is a relatively
small fraction of total time. There is repeated symbolic preparation, but it is
not evidence of a graph-decomposition advantage or a new safe state-equivalence
rule. A mechanism that prevents expensive *generation* remains untested.

## Matched contracts and correctness

The original six-point witness uses EL. The native Capacity Event API requires
RESOURCE_USAGE; using it as an EL speed comparison would change the contract.
We therefore run two matched groups:

1. Independent EL and EL + existing EnumerationReuse.
2. Independent RU (`EL|RESOURCE_USAGE`), RU + EnumerationReuse, and native
   per-shape Capacity Event + packed membership + EnumerationReuse.

All six points' complete returned E/T frontiers agree within the EL group;
complete E/T/**exact-resource** frontiers agree within RU, with exact numerical
comparison. They are stable across cold/warm runs, all repeats and observation
passes. RU and EL happen to select the same best EDP at these points, but their
full fronts and amount of Join work differ. Source identities can tie; **90 warm
selected-source instances** (six per timing process) reconstruct/re-evaluate,
not 90 distinct mappings or every tied source. FFM remains a policy/heuristic
reference, not a physical-mapspace optimum or independent lifetime oracle.

The single-template/full-operator Region Compiler does not implement native
3mm Fusion. The frozen shared-architecture generator is gated to 2mm/dyadic
extents, excluding this 3mm and its non-dyadic array axes. No numbers are invented
for these unsupported baselines. Capacity Events are the strongest compatible
implemented parameterized baseline measured here; hypothetical extensions are
not ruled out by this experiment.

## Three fresh-process trials per method

One worker, requested single-thread numerical environment, serial trials and
forward/reverse method ordering. Every process runs cold then warm searches with
fresh candidates and explicit cache scopes. Imports/startup are outside timers;
spec construction, generation, Join, queries and teardown are inside. Profiling,
heavy identity tracing and source validation occur afterwards, outside timers.

| Contract | Existing method | Cold median s | Warm median s | Warm range s |
| --- | --- | ---: | ---: | --- |
| EL | independent | 22.117 | 14.254 | 14.090–14.803 |
| EL | cache | 21.162 | 13.235 | 12.966–13.987 |
| RU | independent | 22.954 | 14.892 | 14.837–21.073 |
| RU | cache | 21.757 | 13.698 | 13.621–17.097 |
| RU | Capacity Events + cache | **12.635** | **6.467** | 6.419–8.597 |

Cache is 1.077× versus independent EL by warm medians. Events are 2.118× versus
cached RU and 2.303× versus independent RU on this finite experiment. These are
**existing-method** results, not a speedup of a new search. Third-round runtime
variation is visible and all trials are retained; n=3 on one host does not
establish generalized significance or extrapolation to many architectures.

Median pre-profile/validation process high-water RSS is 0.300/0.305 GiB for the
EL methods and 0.292/0.303/0.280 GiB for RU independent/cache/Events. It includes
interpreter/imports, generic caches and cold/warm searches, not isolated search
state or a demonstrated substantial memory advantage.

## Actual work, not requested cache work

The first trial of each method has an additional warmed observation pass. Its
frontier must match the timed pass; instrumentation is not included above.

| Method | Model-template calls | Actual expansion calls | Actual expanded rows | Tile model rows | Matched Join pairs | Largest pair frame |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| independent EL | 252 | 1,320 | 89,632 | 17,841 | 44,754 | 2,772 |
| cached EL | 252 | 380 | 34,189 | 17,841 | 44,754 | 2,772 |
| independent RU | 252 | 1,320 | 89,632 | 17,841 | 110,112 | 2,772 |
| cached RU | 252 | 380 | 34,189 | 17,841 | 110,112 | 2,772 |
| Events RU | 126 | 380 | 34,189 | 8,994 | 55,394 | 2,772 |

Events reduce repeated per-capacity preparation, model materialization and Join
work. They do **not** improve on cached RU's actual expansion calls/rows. The
largest materialized matched frame is only 2,772 rows here; the total pair count
is not a simultaneous memory peak or proof of combinatorial state explosion.
The baseline already exploits important sharing on this case.

## Where warmed time remains

One instrumented pass per method is diagnostic, not a repeated timing median.
Named inclusive scopes below nest; the Pareto rows must **not** be added to their
parents. Raw files also contain additive exclusive remainders, which may include
uninstrumented helpers rather than just the named Python statements.

| Scope | Cached RU s | Events RU s | Interpretation |
| --- | ---: | ---: | --- |
| Whole instrumented six-point search | 13.841 | 6.431 | includes spec/query overhead |
| `make_pmappings` | 12.133 | 5.521 | all generation/preparation work |
| template `get_jobs` | 1.168 | 0.588 | inside generation |
| symbolic model | 3.223 | 1.647 | includes reuse/latency/energy construction |
| Tile target dispatch | 1.541 | 0.600 | includes enumeration and its NumPy Pareto |
| actual prefix expansion wrapper | 0.027 | 0.020 | includes cache lookup/dispatch |
| complete `join_pmappings` | 1.637 | 0.855 | includes compression, reservation, Pareto |
| numeric group Join pipeline | 1.052 | 0.540 | nested inside complete Join |
| NumPy enumeration Pareto | 0.289 | 0.168 | nested inside target dispatch |
| DataFrame Pareto kernel, generation + Join | 2.370 | 0.782 | overlaps both parent phases |

Events spend approximately **85.9%** of the instrumented total inside generation
and **13.3%** inside complete Join. Pure group-Join exclusive remainder is 0.235 s;
Join column-program preparation is 0.00405 s and reservation-adjust methods
0.00015 s. Scope release/capacity operations also occur outside group Join; they
cannot all be charged to its resource arithmetic.

Holding generation/other costs constant, deleting the **entire** Join from this
profile would imply only `6.431/(6.431−0.855) ≈ 1.15×` total speedup. This is an
idealized profile-based ceiling, not an achievable optimization or a bound on a
different algorithm that prevents generation. It makes accelerating only late
resource-transfer execution an unconvincing principal target on this case.

## What really repeats across hardware targets

Heavy tracing is separate and untimed; it preserves the same numerical fronts.
Prefix/formula grouping uses actual native cache-key equality (including Symbol
assumptions, dtype, ordered values/relations), not same-looking printed names.
No prefix keys exceed the 128-MiB trace payload guard in either run.

| Observation | Cached RU | Events RU |
| --- | --- | --- |
| Prefix requests / unique keys / actual computations | 1,320 / 380 / 380 | 705 / 380 / 380 |
| Exact repeated **actual** prefix computations | **0** | **0** |
| Formula requests / unique keys / compiler calls | 3,572 / 154 / 154 | 1,786 / 151 / 151 |
| Model/template observations / distinct physical symbolic output keys | 252 / 42 | 126 / 42 |
| Resource-program observations / distinct structural keys | 319 / 89 | 162 / 73 |
| Resource-program + ordered input-subframe observations / distinct keys | 319 / 234 | **162 / 162** |
| Repeated resource-input matched-pair occurrences | 26,160 | **0** |

The cached path has 85 repeated whole resource-input subframes, and Events remove
that observed repeat opportunity. Events still repeat program structures, but
not those complete resource-input subframes. This does not exclude per-row,
partial-overlap or shared-expression opportunities we did not measure.

The model observations show **84 repeated physical symbolic outputs** even after
Events. They include the same template and model DF after dropping capacity
metadata, not separately returned hardware-normalized usage constraints or the
whole Job. They are discovered *after* doing analysis, not a proven cache key
known before it. This is evidence for investigating shared preparation, not
proof of a graph-sensitive optimization or a measured 3× saving. The existing
2mm shared-preparation prototype is relevant prior engineering, although its
frozen adapter cannot run this case unchanged.

Resource-input keys omit cost/Pareto/membership history and are **not sufficient
future-equivalence interfaces**. Counts cannot justify merging full states or
claiming all those row occurrences are safely avoidable.

## Late rejection opportunity: capacity versus dominance

A separate untimed native-filter audit reproduces the timed frontiers. Counts
are row **occurrences**, not independent complete Mapping identities.

| Inside numeric group Join | Cached RU | Events RU |
| --- | ---: | ---: |
| Matched rows before capacity check | 110,112 | 55,394 |
| Capacity-rejected rows, all due to GB | 5,072 | **1,178** |
| GB rejection fraction | 4.61% | **2.13%** |
| Rows reaching group Pareto | 105,040 | 54,216 |
| Rows deleted by group Pareto | 74,287 | 38,722 |

Most of this late reduction is dominance, not capacity infeasibility. The audit
does not count NumPy-prefix feasibility pruning as a DataFrame capacity check;
it is already reflected in expansion/model work above. Nor does it prove those
1,178 pairs, let alone their upstream prefixes, can be removed earlier without
changing fallback, local Pareto cohorts, aliases or lifetime handling.

## Research decision after the causal witness

1. **Keep the causal conclusion.** Capacity, loop-scoped intermediate residency
   and array-dependent mapping choices interact in the real native model.
2. **Do not implement a Resource Transfer Memo/Graph DP on the strength of this
   case alone.** Exact repeated prefix work is already cached; the stronger Event
   baseline has no repeated whole resource-input subframe under this observation,
   and the entire Join is a small part of elapsed search.
3. **A generation-saving graph mechanism remains a hypothesis.** It would have
   to rule out expensive local solving before it happens, preserve a clearly
   declared search space/quality contract, and outperform ordinary shared
   preparation. Repeated symbolic preparation or equal program structure alone
   does not establish a non-incremental algorithm contribution.

This is a no-go for proceeding directly from the 3mm Reservation witness to an
exact-state reuse implementation. It is **not** a theorem against conditional
transfer functions, larger graphs, per-row factorization or Architecture–Mapping
Co-Optimization. A new case/mechanism should first exhibit a substantial residual
cost the strongest relevant baseline does not already remove. No model, Enforcer,
Separator or synthesis-core feature was added in this work.

## Receipts and reproduction

- [summary.json](results/search_cost_3mm/summary.json): all medians/ranges,
  matched-front checks, profiles and repetition observations.
- Fifteen per-trial JSON files: cold/warm snapshots, six selected-source checks,
  first-trial profiles/forensics and source fingerprints.
- [cached_ru_filter.json](results/search_cost_3mm/cached_ru_filter.json),
  [events_ru_filter.json](results/search_cost_3mm/events_ru_filter.json): untimed
  capacity/Pareto rejection counts and frontier checks.
- [trial_logs.zip](results/search_cost_3mm/trial_logs.zip): all 15 raw logs.
- [tests.txt](results/search_cost_3mm/tests.txt): **9 passing diagnostic tests**,
  including the 4 prior causal tests. Counts overlap, not an enlarged production
  or synthesis regression claim.
- [Protocol](SEARCH_COST_3MM_PROTOCOL.md): timing boundaries, excluded methods and
  key definitions. The production FFM, historical baselines and `graph_dp.py`
  remain unchanged.

```sh
python -m research.diagnostics.profile_3mm_search --repeats 3 --output research/diagnostics/results/search_cost_3mm
python -m research.diagnostics.resource_filter_3mm --variant cached_ru --reference research/diagnostics/results/search_cost_3mm/cached_ru_1.json --output research/diagnostics/results/search_cost_3mm/cached_ru_filter.json
python -m research.diagnostics.resource_filter_3mm --variant events_ru --reference research/diagnostics/results/search_cost_3mm/events_ru_1.json --output research/diagnostics/results/search_cost_3mm/events_ru_filter.json
python -m pytest -q research/diagnostics/test_search_profile.py research/diagnostics/test_causal_3mm.py --disable-warnings
```
