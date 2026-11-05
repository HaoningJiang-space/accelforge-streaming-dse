# G2: cheap three-tier certificates do not recognize the G1 opportunity

**Result:** the tested Local, Architecture and Graph necessary-condition
certificates each reject **0 / 126 shared Jobs and 0 / 69 batches** on native 3mm.
Graph information provides **zero additional certified coverage**. Three fresh
processes agree; two additional dense 2mm/3mm shapes also have zero coverage.
This certificate class does not pass G2. It does not refute stronger correlated
cost/resource or loop-scoped future-obligation certificates, which were not
implemented or proved here. No new optimizer is justified by this result.

Protocol and executable study were frozen at `1ef39d92`; G1 labels/times are from
`6d53760c`. Native FFM, existing baselines and the independent synthesis engine
are unchanged. All original Jobs execute. This round uses the revised **G2 =
three-tier certificate feasibility** definition, not the older proposed
symbolic-preparation reuse experiment.

## What was actually tested

| Tier | Pre-evaluation information and rejection rule |
| --- | --- |
| Local | Dense operand/rank shapes, template loops/storage, positive Tile intervals; reject an interval contradiction |
| Architecture | Local plus exact GB/Register capacities and spatial fanouts; reject an integer resource lower bound exceeding a hard limit |
| Graph | Architecture plus all raw neighbor template interfaces and required tensor edges; reject lack of relaxed support after conditioning on the Job and propagating constraints |

All tiers use the same extracted IR and fixed native NVDLA action coefficients
for a separately labeled cost-bound diagnostic. Local rejection does not use a
target capacity, PE shape, or downstream information. Minimum-utilization goals
and fallback are never converted into hard constraints.

The supported grammar is one-instance, linear dense MatMul with direct
two-dimensional projections, distinct logical operands, and the frozen native
perfect-tiling model. Unknown grammar/initial-Tile patterns retain the family.
The main case and both holdouts have **no unknown template facts**.

The storage abstraction counts minimum projected extents at each storage node.
Multiple copies of the same tensor use the maximum lower bound, while distinct
tensor occupancies add within one native stage. Across stages we use **max of
lower bounds**, never a sum of peaks or a claim of exact global capacity.

For compatibility, every unit-loop deletion is allowed, including impossible
ones. Backing resource/persistence and surviving temporal/spatial loop counts
form a necessary interface. Rank/order, numeric Tile matching, aliases and joint
consistency are relaxed. Missing/unknown information cannot justify rejection.

This deliberately cheap relaxation does **not** derive the causal case's
52 + 64 -> 116 KiB scope transfer. Applying that concrete Tile's resource
obligation to every instance of its raw template would require an additional
proof that this experiment does not possess.

## Safety scope, blindness, and execution checks

For the declared direct native template-completion space, any legal plan induces
locally feasible templates and supported interfaces on mandatory edges. The
intervals contain their Tile choices. Each support deletion lacks a necessary
neighbor; inductively, a legal completion cannot be deleted by the relaxed
consistency closure. This is an infeasibility argument, not a conditional
dominance theorem or a theorem preserving FFM's historical policy under removal.
Plans with new Retile/Copy/recomputation operations are outside that scope.

Analysis runs at `_allocate_jobs`, before `run_model`, Tile enumeration and
model-row construction. Runtime guards reject attempts to invoke expensive
model/enumeration functions during analysis. A decision digest is frozen before
evaluation and checked afterwards. The analyzer receives **no G1 label, saved
Tile, frontier or timing**. G1 matching and cost credits happen in a separate
post-evaluation function using exact pre-evaluation template identity.

The five observed passes check **28,402 generated model rows**:

| Case | Hardware targets | Repeats | Model rows checked per observed pass |
| --- | --- | ---: | ---: |
| Native 3mm(256,256) | 16×384 / 32×192 / 64×96, 128/132 KiB | 3 | 8,994 |
| Holdout 2mm(4,8) | 4×8 / 8×4, 128/256 B | 1 | 398 |
| Holdout 3mm(8,8) | 4×8 / 8×4, 128/136 B | 1 | 1,022 |

Integer GB/Register lower bounds do not exceed any observed native reservation.
Real-arithmetic E/T candidates pass numerical sanity checks with an explicitly
declared floating tolerance. Every observed complete RU frontier exactly matches
the corresponding unobserved native backend pass. The main case also exactly
matches the frozen six-point reference from the preceding cost study.

Because there are **zero real exclusions**, zero observed false deletions is
vacuous; frontier equality is not a positive pruning demonstration. Eight new
diagnostic tests exercise non-vacuous synthetic counterexamples, including a
locally feasible but unsupported family that only Graph rejects, loop
degeneration, unknown support, hard spatial limits, shared copies, non-additive
stage peaks and the full RU dominance requirement. They do not constitute a real
workload speedup. In total **23 diagnostic tests pass**, including 15 older tests.

## Coverage, avoided cost and overhead

All counts below are identical across three native runs. A target member is one
Job at one capacity: there are 252 members but only 126 shared Jobs. Only an
all-capacity exclusion can credit a whole Job or its whole batch.

Local hard-infeasibility cannot explain the G1 waste: all 126 Jobs already
generated nonempty model rows in G1. Whole-Job Architecture infeasibility is also
expected to be absent when each Job has a valid largest-capacity instance. These
are controls, not surprising new negative discoveries. The relevant additional
tests are smaller-target membership, Graph-conditioned support and the strength
of cost/resource bounds; none yields a usable exclusion here.

| Tier | Rejected members / 252 | Whole Jobs / 126 | Whole batches / 69 | G1 local-waste Jobs / 18 | G1 Join-input-waste Jobs / 54 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Local | 0 | 0 | 0 | 0 | 0 |
| Architecture | 0 | 0 | 0 | 0 | 0 |
| Graph | 0 | 0 | 0 | 0 | 0 |

| Tier | Preanalysis median ms | Range ms | Gross generation credit | Net projection before any new engine overhead |
| --- | ---: | --- | ---: | ---: |
| Local | 16.120 | 15.861–16.274 | 0 s | −16.120 ms |
| Architecture | 16.191 | 15.933–16.343 | 0 s | −16.191 ms |
| Graph | 34.141 | 33.580–34.414 | 0 s | −34.141 ms |

These are attribution timings in a common instrumented pipeline, not independent
optimized implementations of each tier. Shared IR/accounting work is charged
conservatively to every tier; Graph adds support preparation and conditioned
queries. Graph's full timing equals measured preanalysis, including otherwise
unassigned bookkeeping. Post-hoc appraisal, row validation and result writing
are diagnostic work and excluded. No engine was built, so any hypothetical new
engine overhead is unknown. With zero gross credit, the measured positive
analysis cost already makes this candidate mechanism unattractive.

The prior G1 52.9% estimate is not added to these zero credits. It describes work
an ideal final-result Oracle could identify, not work these rules identify.

## Why even a free incumbent does not rescue these bounds

We separately construct optimistic **real-arithmetic** E/T candidates from
mandatory MACs and full-tensor DRAM backing transfers, dropping all other
nonnegative costs. Per-stage latency uses the maximum of compute/read/write
service lower bounds. Graph sums minimum supported stage E/T bounds and takes
max of minimum stage resource bounds.

**Cost candidates never issue rejection certificates.** No floating-point
roundoff proof is claimed, and there is no free online incumbent. Only after
all decisions and searches finish do we screen against the entire saved
reference frontier as a deliberately unrealistic free-incumbent Oracle.

On each native run:

| Post-hoc bound diagnostic | Result |
| --- | ---: |
| Target members screened | 252 |
| Some reference point dominates E/T bounds when resources are ignored | **54** |
| Some reference point dominates all E/T/GB/Register bounds | **0** |
| GB lower bound smaller than every returned point's GB | **240 / 252** |
| Graph GB lower-bound range | 3–65,793 B |
| Graph energy lower-bound range | 22.657–37.400 µJ |
| Graph latency lower bound | 12.288 µs |

The 54 here are **target members**, not the 54 G1 Join-input-waste Jobs. Treating
E/T or EDP dominance as sufficient would ignore the RU contract. These post-hoc
figures are not actual certificates and receive no time-saving credit.

There are two concrete failures of abstraction strength:

1. Raw templates leave broad Tile domains. Their minimum storage fits both
   architectures, and allowing all loop-deletion patterns leaves relaxed
   neighbor support. A concrete Mapping's 132 KiB threshold is not a mandatory
   lower bound for its entire template family.
2. Separately minimizing E, T and storage loses their correlation. Tiny storage
   and minimal traffic may require different Tile choices. The resulting
   optimistic vector is too strong an adversary for a feasible reference plan
   to dominate, even when all reference plans are supplied free.

Thus a stronger candidate would need a justified **correlated** bound on a
well-defined subfamily or a genuine nonlocal resource obligation. Neither this
experiment nor G1 proves that such a bound can be computed cheaply. Merely adding
more independent bounds, a scalar peak, or a Memo does not resolve this gap.

## Gate decision

- **G1 remains positive:** retrospective costly non-contribution exists.
- **This tested G2 relaxation fails:** cheap, but no coverage and no Graph-only
  savings on the native case or two holdout shapes.
- **The broader G2 question remains open:** context-dependent dominance and
  correlated future-obligation certificates have not been proved or tested.
- **G3 remains unstarted:** no Conditional Frontier Engine or new Join mechanism
  should be implemented on the strength of these results.

In particular, G1's 54 Jobs with local Join inputs remain **unclassified** as
local dominance versus context-dependent dominance. Nothing here rebrands them
as demonstrated graph-specific waste. The holdouts are still small dense chains;
they do not establish behavior on GLU, branching DAGs or arbitrary workloads.

## Receipts and reproduction

- [Protocol](PREGEN_CERTIFICATE_PROTOCOL.md), [rules](pregen_certificates.py),
  [driver](pregen_certificate_study.py), [tests](test_pregen_certificates.py).
- [Summary](results/pregen_certificates/summary.json),
  [manifest](results/pregen_certificates/manifest.json).
- [Native run 1](results/pregen_certificates/native_1.json),
  [run 2](results/pregen_certificates/native_2.json),
  [run 3](results/pregen_certificates/native_3.json): every pre-evaluation fact,
  per-member decision/bound, decision digest, cost and post-hoc G1 appraisal.
- [2mm holdout](results/pregen_certificates/2mm_holdout_1.json),
  [3mm holdout](results/pregen_certificates/3mm_holdout_1.json).
- [Post-hoc bound gaps](results/pregen_certificates/posthoc_bound_gaps.json),
  [five raw logs](results/pregen_certificates/trial_logs.zip),
  [23-test receipt](results/pregen_certificates/tests.txt).

```sh
python -m research.diagnostics.pregen_certificate_study --repeats 3 --output research/diagnostics/results/pregen_certificates
python -m pytest -q research/diagnostics/test_pregen_certificates.py research/diagnostics/test_generation_provenance.py research/diagnostics/test_search_profile.py research/diagnostics/test_causal_3mm.py --disable-warnings
```
