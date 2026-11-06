# Native generation entry: a precise late certificate is not an early one

The existing evidence does not yet justify skipping any native `run_model`, Tile
enumeration or model-row construction. This audit fixes the **information and
side-effect contract at that entry**, using the existing G1/G2 and Consumer
witness archives. It adds no observer, provider, solver, cache or pruning rule.
The search-work boundary study, SearchEngine, physical models and FFM remain
frozen at `67e9a1f8`.

There are two concrete findings. First, the observed `126 -> 42` physical-model
output grouping omits part of the model's result and mutations; it is not a safe
replacement key. Second, the original Consumer `217/209` reversal admits a very
specific resource-equality condition, but its premises are currently known only
after numerical evaluation and Join preparation. We can identify exactly which
information is missing from the earlier cheap facts, without adding another
candidate mechanism.

## What exists before each expensive boundary

| Boundary | Already available | Not established there | Existing source |
| --- | --- | --- | --- |
| `_allocate_jobs` | Raw mapping/storage/loop skeleton; rank domains; evaluated hardware/action model; constraints; tracked/fusable tensors; target-capacity requests; compatibility batches | Actual Tile assignments, quantitative resource/cost relations, target-specific kept membership, legal numerical completions | [`make_pmappings`](../../accelforge/mapper/FFM/_make_pmappings/make_pmappings.py#L429), [`Job`](../../accelforge/mapper/FFM/_make_pmappings/pmapper_job.py#L55) |
| Immediately before `run_model` | Constraint loop indices set; terminal Tile set to one; remaining raw Tile decisions | Full SymbolRelations/objectives; symbolic reuse/action/reservation/latency expressions; complete model post-state | [`_make_tile_shapes`](../../accelforge/mapper/FFM/_make_pmappings/make_pmappings_from_templates/make_tile_shapes.py#L1616) |
| After `run_model`, before enumeration | Five returned model objects and mutated mapping; SymbolRelations, objectives and utilization goals can now be constructed | Target-specific fallback history and retained Tiles; which loops become unit and disappear | [`run_model`](../../accelforge/mapper/FFM/_make_pmappings/make_pmappings_from_templates/run_model.py#L39), [`target dispatch`](../../accelforge/mapper/FFM/_make_pmappings/make_pmappings_from_templates/make_tile_shapes.py#L954) |
| After enumeration/local batch processing | Concrete Tiles, target membership, materialized numerical columns, populated compatibility and surviving loops | Complete downstream obligations and final dominance | [`batch processing`](../../accelforge/mapper/FFM/_make_pmappings/make_pmappings_from_templates/make_pmappings_from_templates.py#L222) |
| Prepared terminal Join | Closed numerical resource program and actual compatible input rows | An early derivation covering every completion of a raw family | Existing [counterfactual/effect study](COUNTERFACTUAL_EFFECT_RESULTS.md) |

"Not established" is a computational distinction, not missing information in
principle: the deterministic model's inputs specify its outcomes. The unresolved
question is whether a sufficient relation can be derived more cheaply than the
work it would avoid. This ledger is not an impossibility theorem for doing so.

The fast reservation insertion used for structural compatibility does not itself
compute the quantitative occupancy/cost analysis. Full reuse subsequently walks
per-tensor mappings and their loop/storage effects. A raw loop can disappear when
its evaluated iteration count is one; batch processing then drops/renames loops
and shifts resource scopes. Thus the archived closed program's scope indices
cannot simply be assumed constant over every Tile completion of its raw Job.

G2 already runs at `_allocate_jobs` with expensive calls guarded. Its three tiers
reject zero Jobs/batches. Moving the same predicates closer to `run_model` or
changing a Python iterator would not strengthen their mathematical content.
Conversely, a rule placed after `run_model` could avoid later work, but must not
claim to have avoided the symbolic model itself.

## The complete model contract is larger than its physical table

The caller unpacks **five** objects:

1. Ordered Symbols, including their assumptions.
2. The symbolic numerical-column dictionary.
3. Per-memory usage formulas used in capacity objectives.
4. Spatial usage formulas used in target utilization/fallback.
5. Per-tensor physical mappings used by later reconstruction/evaluation.

The call also has observable mutations. Reuse analysis replaces `job.mapping`
with reservation-bearing structure; symbol insertion changes Loop Tile/initial
Tile/iteration fields; `run_model` sets `job.resource_capacities`. See
[`analyze_reuse_and_add_reservations_to_mapping`](../../accelforge/model/_looptree/reuse/symbolic/symbolic.py#L490)
and [`insert_sympy_symbols`](../../accelforge/model/_looptree/reuse/symbolic/symbolic.py#L1372).
These are examples of relevant effects, not a proof that the list exhausts every
transitive dependency.

The earlier [repetition observer](search_repetition.py) groups a post-call key
containing the mapped structure and **only the second returned object with
capacity metadata removed**. It does not establish equality of objects 1/3/4/5,
pre-call inputs or post-state. In particular, hardware fanout normalization can
affect usage while the physical cost expressions agree. General latency formulas
read architecture actions, component fields and `spec.variables`; energy can
include leakage and utilization. A key omitting those dependencies cannot be
declared safe from the NVDLA output-equality count alone.

This is not a discovered wrong-cache bug: no such model-result cache exists in
the frozen search. It identifies what a proposed replacement would have to
prove. Existing immutable formula/prefix caches retain their own proven keys and
are not changed. A conservative full-object key might avoid false sharing, but
its repeat rate and construction cost have not been measured here; no new key
or reuse saving is claimed.

## Reconnecting the real Consumer 217/209 witness

The archive replay verifies a unique `(shared target, einsum, compact template)`
crosswalk for all **126 families** between G1, G2 and the counterfactual trace,
with identical returned-source labels. UUIDs and `task:N` identifiers are run-local
and are not used as cross-run keys. This is an archive linkage check, not a proof
that a compact string is a sufficient physical/model-equivalence key.

The selected trace is shape **32x192**, capacity **128 KiB**, prepared bucket 68.
It closes scope 2 to -1, with zero Allocation/Free/Alias operations. Both Prefixes
match both Consumer rows. Their prepared fields differ only in one GB column,
energy and Matmul0 source ID; all other recorded context fields agree.

| Role | Archived source | Raw Job | Concrete Tile | GB lower bound known to G2 before model |
| --- | --- | --- | --- | ---: |
| Q's Matmul0 | 53 | task:48 | stride=(128,256,32,128,128) | 3 B |
| P's Matmul0 | 57 | task:49 | stride=(256,128,128,32) | 3 B |
| Shared Matmul1 | 78 | task:55 | stride=(16,128,1,1,128,32) | 258 B |
| Consumer 217 | 217 | task:68 | stride=(16,128,1,1,32,128) | 258 B |
| Consumer 209 | 209 | task:67 | stride=(16,128,128,1,128,32) | 513 B |

Each stride tuple follows that Job's archived ordered Symbol list; they are not
the same variable vector across different templates. Full templates, assignments,
G2 decisions and G1 lineage are in the [replayed evidence](results/native_generation_entry/audit.json).
The lower bounds above are local necessary conditions, not exact demands.

The selected cohort label `task:55` is **shared by Q and P**, while the changed
upstream candidates are in Matmul0 Jobs 48 and 49. Job 48 has a returned frontier
descendant; the other four listed Jobs do not. Therefore a reversal attached to
Job 55 is not a certificate that its whole family, or all of Job 48, can be
discarded. Job-level incidence and the internal decision that changes rank are
different objects.

## Exact conditional equality, with its timing limitation

Reuse the existing `compile_closed` and independent scalar resource interpreter.
Let `x2`, `x3` be this bucket's incoming Consumer GB reservations at scopes 2 and 3,
measured in KiB. The two already-prepared Prefix responses are:

```text
H(x2,x3) = max(32 + x3, 32.25 + x2)
GB_Q    = max(44, H)
GB_P    = max(68, H)
```

Their Register responses are identical. Hence their GB responses are equal
**if and only if `H >= 68`**. For `H < 68`, Q has strictly smaller GB. This follows
directly from the two constant floors; it is an exact statement about this
closed numerical resource program, not a theorem for arbitrary Fusion.

| Consumer | x2 KiB | x3 KiB | H KiB | GB_Q KiB | GB_P KiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| 217 | 32 | 32.15625 | 64.25 | 64.25 | 68 |
| 209 | 36 | 36.125 | 68.25 | 68.25 | 68.25 |

In both recorded completions P has lower energy and equal latency. Thus the
second context permits P to cover Q, while the first preserves their E/GB
tradeoff. All **four** native pre-capacity resource/cost vectors are rechecked
exactly; resource results also agree with the existing scalar interpreter.
This is a new replay of old numerical evidence, not new native execution or an
independent scalar MatMul replay.

The predicate `H >= 68` is not available from the G2 bounds in the preceding
table. Its constants, actual scope program, exact matching Tiles and associated
costs have already passed through expensive analysis. An early certificate would
need to prove the relevant inequality and cost relation over a specified
unexpanded subfamily, under the same physical requirements. Observing it for
Consumer 209 cannot justify applying it to all completions of Consumer Job 67.
Nor may a minimum from incompatible rows replace the minimum over the required
interface. No such correlated family proof is supplied by these archives.

## What can actually be avoided at the native entry today?

| Proposed basis | Evidence available | Current decision |
| --- | --- | --- |
| Cheap hard-feasibility/relaxed support | G2 zero coverage on native and holdouts | No skipped generation justified |
| G1 final-descendant labels | Retrospective 54 useful / 54 Join-input unused / 18 locally eliminated Jobs | Post-hoc screening only; not a safe branch decision |
| 126 calls / 42 physical outputs | Partial post-call equality | Insufficient complete-call replacement contract |
| Closed Consumer-dependent coverage | Exact conditional resource region for prepared Prefixes | Correct late evidence; no pre-model family proof |
| Existing prefix/formula/event sharing | Already in the strongest compatible baseline | Retain; do not count it as a new Graph advantage |

The actual newly avoided work in this audit is **zero**: no native Job runs,
model calls, enumerations or candidates are skipped. Offline archive reading,
decompression, linkage, existing-effect compilation and verification take about
0.30 s in the saved execution. That is diagnostic cost, not an online certificate
cost or a speed comparison. Historical G1 task timings are retained only for
lineage; none is credited as a new saving, including unused-batch overhead.

The explicit bridge now needed is a family-level proof supplying the same
physical contract, resource/cost correlation and scope cases **before** their
expensive evaluation, at lower total cost. Model replacement additionally needs
all outputs and relevant post-state; policy-preserving deletion must account for
target fallback and batch histories. This audit establishes neither bridge and
does not authorize a new provider/filter implementation. RQ2 remains open; the
research question, strong baselines and execution contracts stay fixed.

## Reproduction and scope

```sh
python -m research.diagnostics.audit_native_generation_entry --output research/diagnostics/results/native_generation_entry/audit.json
python -m pytest -q research/diagnostics/test_generation_provenance.py research/diagnostics/test_pregen_certificates.py research/diagnostics/test_counterfactual_classification.py research/diagnostics/test_scoped_effect.py --disable-warnings
```

The audit fails on ambiguous archive identities, mismatched family catalogs,
changed source labels, unsupported scope operations, incompatible selected rows,
or disagreement with native/scalar numerical records. It does not import/call
native mapping generation or add a tracing hook. The
[execution receipt](results/native_generation_entry/execution_receipt.json)
records exact archive/source hashes and unchanged frozen paths. The **26 existing
tests above passed in 1.03 seconds**; see [tests.txt](results/native_generation_entry/tests.txt).
The prior 873-test research result remains historical; this round does not claim
to rerun it or the legacy production suite, or to rerun a native DSE benchmark.

## Contract clarification and a shared-work elimination condition

The research correctness target is an independent, explicitly declared physical
plan space, not replication of all FFM fallback/Pareto histories. FFM policy
reproduction remains a separate baseline/regression contract. A physical-space
theorem must specify supported loops, copies, scope transitions, target hardware
and objectives; it cannot import historical policy membership as physical law.
This clarification does not supply the missing native Fusion grammar or extend
the existing independent Oracle. Those remain unproved parts of the bridge.

Before implementing even a sound early capacity test, account for the strong
baseline's sharing. Fix **one PE shape**, its declared capacity targets A, and
the baseline's per-target retained assignments P_a. No nesting or monotonicity
of these policy sets is assumed. The unique physical assignments materialized
after target enumeration are U = union_a P_a, with a separate membership relation.

**Unique-output condition.** Suppose a prefilter only removes target/assignment
pairs that cannot legally execute and the matched baseline already excludes
those pairs. Preserving each P_a therefore preserves U. Such a filter cannot
reduce the count of materialized unique output assignments merely by making
their already-empty target memberships known sooner.

**Proof.** Every removed pair is absent from its P_a, so subtracting those pairs
leaves every P_a unchanged. Taking their union leaves U unchanged. In particular,
an assignment still needed at any other target remains in U. This argument does
not replace target-specific fallback with largest-capacity filtering.

This set argument is not a proof that deleting an infeasible **partial state**
preserves FFM policy. Such a change can alter fallback/Pareto histories and hence
P_a; that requires its own proof if policy reproduction is the chosen contract.

The corresponding *atomic Job* condition follows directly from the current
evaluation schedule: `_make_tile_shapes` calls `run_model(job)` once **before**
`get_tile_shape_choices_for_targets`. If some target still requires that Job's
evaluation and the model evaluator is left unchanged and indivisible, removing
only other targets cannot eliminate its one shared model call. A cheaper model
replacement or a different, proved decomposition is outside this condition.

These are work-accounting propositions for this sharing/evaluation model, not
lower bounds on every possible optimizer. Identical final U can coexist with
fewer unsuccessful intermediate prefixes, fewer policy operations, or a cheaper
evaluation algorithm. Those effects must be proved and measured separately;
output cardinality alone cannot establish or rule them out.

### Applying the condition to the actual 128/132-KiB witness

Consider the restricted family whose Matmul1 execution reserves disjoint full
T1 and T2 buffers simultaneously, plus positive distinct W1 scratch. Conditional
on those explicit physical premises, every member requires at least
`65,536 + 65,536 + w` bytes, with `w >= 1`. Thus the family is impossible at
128 KiB. This is a family-wide arithmetic implication of the premises, not an
inference from top-level Storage labels. Independent execution coverage of every
completion under those premises is not established here. In particular, the
three observed 4-KiB scratch Tiles do **not** prove a 4-KiB minimum over that family.

The saved high-capacity native mappings have w=4,096 bytes and need exactly
135,168 bytes. Their Mapping IDs also occur as the high-capacity selected sources
in the archived **Events + Cache RU** run:

| PE shape | C=132 KiB Mapping ID in both records |
| --- | --- |
| 16x384 | `20eae11943d378b4` |
| 32x192 | `cdb9a8ad3cc0e9b3` |
| 64x96 | `2ccc239546c9eb78` |

The causal records reject each fixed mapping at 128 KiB and accept it at 132 KiB.
The [archive check](results/native_generation_entry/shared_target_check.json)
verifies IDs, exact native Matmul1 reservation sums and both migrations. This
cross-check uses stored native-model results; it is not a new independent
physical-lifetime proof, new DSE run, or assertion that every selected source is
the unique representative of its numerical point.

Consequently, an early rule that *only* rejects the low-capacity instances cannot
remove these already-shared high-capacity evaluations or their required physical
assignments from a source-preserving replay. It has not shown new `run_model` or
unique-output savings against this baseline. For a numerical-frontier contract,
different sources could replace them, but that would require a separate coverage
proof rather than this capacity argument. Whether an earlier test saves failed
enumeration-prefix work remains unmeasured.

This rejects implementing that capacity-only idea on the strength of the
132-KiB example alone. It does not reject correlated physical decision
elimination in general. The research gap is now two proof obligations, not one:
**the eliminated family is safely covered, and the expensive shared work needed
by the retained targets actually disappears or becomes cheaper.** Neither follows
from the other. No new pruning rule, observer, optimizer or benchmark is added
by this contract clarification.

This section is a source-level argument and archive cross-check only. No test
suite, native mapping evaluation or search was rerun; prior execution receipts
remain historical. The location of work in the current `run_model` is not a
theoretical lower bound on constructing a different sufficient representation.

## Candidate examined: retain an already-full GB copy

One concrete candidate was examined before implementing any optimization. It
targets the DRAM round trip of an internal edge in a sequential 3mm program:
the producer already has a full GB output copy, and the consumer would allocate
and load an identical full GB input copy. This uses a graph edge and ownership,
not a free layout change or a new capacity threshold.

**Conditional trace law.** Assume a linear, single-consumer edge; no external
observation of the intermediate's DRAM copy; identical full logical regions,
versions, precision and GB physical properties; no aliases/input writes; and
sequential kernels with barriers, no cross-stage fused loops or overlapping DMA.
Other stage-owned buffers are released before the next stage starts. Replace
writeback/free/reload of the intermediate by retaining its producer allocation
and giving its full read-only view to the consumer. Release it at the consumer's
last use. Internal kernel Tiles, loop orders and spatial assignments stay fixed.

The consumer sees identical values at every read, so its computation trace and
output are unchanged for **every** kernel schedule satisfying these premises.
During each kernel, live allocations match the original execution after
identifying the two boundary copies. Between kernels, only a buffer already
present in an original kernel is retained; no unrelated work occurs in the gap.
The global peak cannot increase. PE/Register demand is unchanged. The rewrite
only removes copy actions. With nonnegative action costs and monotone component
service functions, E/T cannot increase. The frozen NVDLA model has zero leakage,
positive copy costs and monotone read/write service expressions.

This is a standard copy-forwarding argument under a narrow physical contract,
not a new optimizer theorem or proof for arbitrary native Fusion. It does not
apply to a tiled consumer input, another consumer needing the DRAM instance,
different physical properties, asynchronous execution or an open shared scope.
The prior causal fixed-map controls give three native examples of the reverse
transformation: adding 262,144 DRAM bytes at equal 132-KiB peak. They do not
independently validate native lowering for every schedule in this family.

### Whole-Job applicability fails before implementation

The candidate's source predicate requires full GB copies at both ends. Reuse
the existing G2 raw templates and G1/counterfactual emitted Tile assignments;
do not run native generation again. There are **54 raw Jobs**, 18 per operator
across the three shapes, whose relevant intermediate backing is MainMemory.
For **each of the 54**, its first archived emitted Tile has at least one relevant
GB copy that is only a partial tensor region. Thus this raw Job is not wholly
inside the full-copy source predicate.

This check is deliberately restricted: direct dense 8-bit 256x256 projections,
perfect divisor Tiles, one GB copy of each relevant tensor, no spatial loop
preceding that GB copy, and the verified native loop/Symbol correspondence.
The region at GB storage is bounded by the two current rank Tiles. Later
reservation lowering cannot move its allocation before that storage or enlarge
its projected region; temporal repetition does not turn one tiled allocation
into a simultaneous full copy. The checker fails on unsupported patterns; it
does not treat compact strings as general equivalence keys.

For example, Matmul0 `task:49` has an emitted assignment beginning `stride0=1,
stride1=32`. Its T1 GB copy is bounded by a 1x32 region (32 bytes), not the full
65,536-byte tensor. A high total reservation from other tensors would not prove
that this particular T1 copy is full.

| Archived class among the 54 Jobs | Jobs with an outside-predicate Tile |
| --- | ---: |
| Has a returned frontier descendant | 32 |
| Local Join input, no final descendant | 7 |
| No local Join rows | 15 |

These are counterexamples to **whole-Job applicability of this rewrite**, not
proof that each outside Tile has a necessary Pareto completion. Combined rules
might eventually cover those remaining domains; this rule alone does not.
The [54 counterexamples](results/native_generation_entry/full_copy_scope.json)
retain raw templates, exact assignments, copy bounds and source hashes.

There is a second granularity obstacle. The rule covers complete producer/
consumer **pairs** with full copies. A local plan may also connect to a tiled
consumer, where retaining a full input could raise the consumer's peak. The
argument supplies no coverage for those other completions. Removing a covered
set of pairs does not remove a local generation task if it still has uncovered
contexts. A proof permitting local evaluation to disappear must cover all such
contexts or demonstrate a cheaper shared replacement. No such proof is provided
by this candidate. Its actual prefix/row savings have not been established.

**Decision: do not implement this as a Generation-saving filter.** It may be a
valid complete-plan rewrite within the conditional trace grammar, but it has
not passed the native family-coverage and computational-elimination gates.
There is no new model-call, enumeration or batch-time credit. Once this work
boundary failed, no forwarding engine or additional scalar-Oracle expansion was
built. The research question and strong baseline remain unchanged.

The reproduction checker performs archive arithmetic only:

```sh
python research/diagnostics/results/native_generation_entry/check_full_copy_scope.py --output research/diagnostics/results/native_generation_entry/full_copy_scope.json
```

No native search/model or test suite was rerun for this candidate. All earlier
benchmark/test receipts remain historical; frozen source/model/Oracle paths are
unchanged. This is a rejected concrete candidate, not another search mechanism.
