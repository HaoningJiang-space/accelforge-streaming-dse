# G1 counterfactuals and a minimal closed-scope resource effect

**Result:** we now have real, bounded examples of continuation-dependent resource
ranking, and an exact resource-arithmetic summary for a restricted prepared
program. We still do **not** have a universally sufficient physical interface or
a way to construct it before expensive generation. This does not justify a new
Graph optimizer or expanding the synthesis engine.

The study is diagnostic only. Native FFM, G1/G2 baselines and `joint_synthesis`
are unchanged. Trace/effect code was frozen at `381b002c`; subsequent offline
analysis adds a floating-cost margin filter. Full source fingerprints are in
the manifest. One untimed Event+Cache/RU six-target grid was observed; six
additional **fixed-mapping** evaluations verify effect-contract flags. There is
no new search algorithm or performance benchmark.

## 1. The 54 Jobs are evidence classes, not 54 proven graph-specific eliminations

We match the exact pre-evaluation template identities of G1's 54 Jobs that had
local Join inputs but no returned frontier descendants. The new trace preserves
all six complete numerical RU frontiers and the useful/unused status of every
G1 Job. It records local inputs, matched pairs and capacity-feasible terminal
rows **before** group Pareto.

| Evidence over those 54 Jobs | Jobs | Interpretation |
| --- | ---: | --- |
| At least one visited feasible complete plan | **39** | Whole-Job infeasibility cannot explain these Jobs |
| Only strictly dominated visited terminal completions | **33** | Strict dominance in the recorded pool, not all legal completions |
| Some completion equals a returned full RU point | **6** | Value-equivalent alternate-source evidence; these Jobs also have strictly dominated completions |
| No capacity-feasible terminal witness in this trace | **15** | Cause remains unresolved |

The last two middle rows partition the 39 witnessed Jobs. The unresolved 15
comprise four with no observed numeric matching pair and eleven with retained
prefix rows but no observed feasible terminal completion. Compatibility,
lookahead, prefix consolidation, target policy and earlier Pareto can all affect
this observation. We do not infer physical impossibility from missing traces.

A conservative local replacement check finds **0 fully covered Jobs**. It requires
the same concrete local group, equality of every non-cost/non-source transition
column, and no-worse E/T from another Job. This is a sufficient *numerical*
replacement test; zero witnesses does **not** establish the absence of another
universal local dominance rule. Existing local Pareto already removes many such
obvious alternatives.

The completed 39-Job evidence is limited by earlier pruning: terminal rows are
only those the reference actually visits. We have not rerun all legal completions
with prefix pruning disabled, changed fallback cohorts, or searched every
continuation. Therefore **Graph-Specific Waste in seconds remains unproved**;
the output records it as unknown, not as the time of all 54 Jobs.

## 2. A nontrivial continuation counterfactual

For each target, we hold a prepared Join bucket **and** a final consumer source
fixed, then compute the Pareto set of its recorded feasible complete rows. This
does not assume that a source ID alone fixes its LoopTree alignment. Thirty-three
Jobs have a completion that is efficient in such a nonsingleton restricted pool
but strictly dominated globally. Restricting a pool can itself create winners,
so this alone is not strong graph-specific evidence.

We then apply a stronger test: keep the **same producer competition set and
prepared program**, vary the consumer row, and look for a producer that changes
efficiency status because the **resource ordering** changes while its competitor
has no-worse E/T in both contexts.

- **11 Jobs** have this finite resource-order reversal evidence.
- **10 Jobs** have a witness with a cost gap above an `8*eps32*max_cost` diagnostic
  margin in both contexts. One remaining Job is near a floating cost tie and is
  kept separate from this stronger group.
- Every first per-Job resource witness is independently checked against the raw
  rows using scalar dominance comparisons, without the classifier's skyline mask.

Example: 32×192, 128 KiB, bucket 68, with the **same 32 producer candidates**.
Prefix sources Q=(53,78), P=(57,78); only the consumer source changes:

| Fixed consumer | Plan | Energy µJ | Latency µs | Final GB KiB |
| --- | --- | ---: | ---: | ---: |
| 217 | Q | 233.120 | 74.923 | **64.25** |
| 217 | P | **232.990** | 74.923 | 68.00 |
| 209 | Q | 233.120 | 74.923 | 68.25 |
| 209 | P | **232.990** | 74.923 | **68.25** |

With consumer 217, Q trades energy for storage and is on the restricted frontier.
With 209, the storage distinction disappears and P dominates Q. These are native
completed-row values, not artificial layout penalties or hypothetical resources.
They are not the globally best plans. Both consumers and the entire competition
set are retained in the raw trace.

This is a concrete reason that an internal scalar peak can be insufficient for
ranking plans in a continuation. It does **not** prove that every completion of
any of the eleven Jobs is useless, nor that no different local implementation
could universally replace it. The result is a row-level finite counterexample,
not a safe generation-pruning certificate or a Job-level attribution theorem.

## 3. Minimal resource-effect semantics

The independent `scoped_resource_effect.py` imports no native Join, resource,
Pareto or mapping-generator implementation. It interprets an explicit prepared
program containing nonnegative integer resource addition and scope closure.
Its domain is deliberately narrow:

- exact finite GB/Register coordinates and nested consumer reservation prefixes;
- a closed output scope (`next_shared_loop_index == -1`);
- no Allocation, Free or Alias adjustments;
- all matching and non-resource input requirements remain fixed.

Max-affine expressions are closed under addition and max. A structural induction
on those operations proves the expression equals the declared integer program
for every admitted coordinate vector within the exact range. A separate scalar
integer interpreter and native recorded outputs check the implementation.

Within **this fixed numeric program**, equal full non-resource requirements,
equal resource functions and no-worse correlated E/T imply numerically
interchangeable outputs for every admitted consumer input. This is the limited
sufficiency statement. It is **not** arbitrary-continuation equivalence,
ownership/copy correctness, preservation of FFM's search history after deletion,
or a universal physical-plan replacement theorem. Algebraically admitted
coordinates also need not correspond to realizable Tensor/Tile choices.
Changing a Tile can eliminate a loop or change the prepared instruction program.
Such changes are different contexts, not substitutions into one fixed effect.

### The real 116 KiB mechanism

For the archived 64×96 / 128 KiB witness, prepared producer demand is 52 KiB;
the consumer contributes outer obligation x=64 KiB and phase peak y=100 KiB.
The first resource instruction is `left_scope += consumer_outer`; closing gives
`max(52 KiB + x, y)`. A following root barrier with peak z gives:

\[
\Phi(x,y,z)=\max(52\ \mathrm{KiB}+x,\ y,\ z).
\]

At the recorded x=64, y=100, z=84 KiB, the result is **116 KiB**, not 100 KiB.
The composed evaluator passes the first result into the next root-scope rename
and closure; it does not substitute the archived final peak as a new constant.

All twelve archived transfers from six fixed mappings match the effect and the
independent scalar interpreter. Six new fixed-mapping probes additionally
confirm that the required no-allocation/free/alias contract actually holds; the
old archive did not expose the alias flags. No mapping search is invoked by
these probes.

The three 132 KiB source plans fail the 128 KiB query and fit 132 KiB. All three
128 KiB source plans fit both. Costs stay attached to their individual grounded
plans. The full four-dimensional numerical frontier of this **six-plan library**
has one point per shape at 128 KiB and two per shape at 132 KiB; resource tradeoffs
prevent collapsing each pair to its EDP winner.

The source mappings were EL-selected in the earlier causal study and then
re-evaluated with resources/actions. This library check is separate from the
current RU search trace. It is **not** exhaustive enumeration of a physical
schedule grammar, the entire FFM mapspace, or a new independent fusion Oracle.
The scalar interpreter verifies resource instructions, not physical allocation,
Tensor data copies or numerical MatMul execution.

## 4. What compresses, and what does not

The native trace contains 126 Jobs, 8,994 local model rows and 162 numeric group
Joins. Of the Join programs, 103 satisfy the closed-scope contract; **59 retain
open scopes** and are reported unsupported. No program is silently approximated.
The supported subset validates **39,579 matched row occurrences** against both
native values and the scalar interpreter.

| Representation in that supported subset | Count |
| --- | ---: |
| Prepared producer-row occurrences across fixed programs | 33,098 |
| Distinct canonical resource-expression keys | **5,332** |
| States retaining fixed context, remaining fields and correlated E/T | **33,079** |
| Conditional Pareto states within equal requirements and equal effects | **17,986** |

The resource-only reduction is substantial, but it discards information needed
by the surrounding decision process. Complete fixed-context equality removes
only 19 state occurrences. Conditional E/T Pareto removes more alternatives,
but these are **already-generated prepared states**, not Jobs avoided before
evaluation. No independent minima of E, T and resource are combined into a
fictional point.

These counts are not distinct complete physical Mapping identities. Repeated
producer states occur in multiple Join contexts, and the key deliberately keeps
those contexts distinct. Canonicalization only eliminates componentwise-covered
terms; different keys may represent the same function on a constrained domain.
Thus these are conservative representation counts, not a lower bound on the
best possible separator size or a proof that compact summaries cannot exist.

There are 402 canonical resource keys observed at multiple PE-shape targets.
That establishes equality of arithmetic functions with already grounded inputs,
not transferable Mapping legality, target fallback, cost functions or shared
generation. Capacity queries can reuse a fixed plan's effect; the existing Event
baseline already exploits capacity sharing. No new cross-architecture search
work is avoided here.

### Construction cost

| Diagnostic work in this run | Seconds |
| --- | ---: |
| Summary/key/evidence construction | 5.386 |
| Native/scalar row validation | 3.359 |
| Conditional equal-effect frontier | 0.016 |
| Total effect analysis including overhead | 8.772 |

The total includes those components; they must not be added again. Construction
includes conservative full-state keying and verbose evidence materialization,
not an optimized algebra kernel. The separate counterfactual classification is
5.098 s. These are one-run diagnostic costs, not timing medians or inherent
algorithmic lower bounds. More decisively, **all generation has already been
paid before either analysis starts**. Avoided generation is exactly zero.

## 5. Research decision

The positive evidence is now specific: continuation resources can change the
ordering of the same candidate set, and a small exact numeric resource effect
can reproduce a real cross-phase obligation. The negative evidence is equally
specific: this representation still starts from evaluated states, most complete
fixed-context states remain distinct, and a substantial set of open-scope joins
is not covered.

We cannot yet classify G1's 54 Jobs into universal local dominance versus
universal context-dependent dominance. Ten well-separated finite witnesses do
not authorize deleting ten Jobs. Nor does a compressed resource-only expression
establish a sufficient physical boundary for arbitrary continuations.

Therefore this round stops at diagnosis. No new searcher, Enforcer, open-scope
reservation engine or Graph DP extension was added. Before further expansion,
the missing claim remains: derive a compact **correlated physical subfamily
summary before expensive evaluation**, with a declared continuation grammar and
a proven coverage/replacement rule. This study does not establish that claim.

## Receipts and reproduction

- [Protocol](COUNTERFACTUAL_EFFECT_PROTOCOL.md),
  [trace](counterfactual_trace.py), [classification](classify_counterfactuals.py),
  [independent effect algebra](scoped_resource_effect.py),
  [fixed-source contract probes](verify_fixed_scope_flags.py).
- [Classification and per-Job witnesses](results/counterfactual_effects/classification.json).
- [Readable effect summary and composed six-plan library](results/counterfactual_effects/effects_summary.json),
  [all effect records, losslessly compressed](results/counterfactual_effects/effects.json.gz).
- [Raw numeric trace and provenance](results/counterfactual_effects/trace.json.gz),
  [scope probes](results/counterfactual_effects/fixed_scope_flags.json),
  [independent witness checks](results/counterfactual_effects/witness_checks.json).
- [Manifest](results/counterfactual_effects/manifest.json),
  [logs](results/counterfactual_effects/raw_logs.zip),
  [35 passing diagnostic tests](results/counterfactual_effects/tests.txt): 12 new
  tests plus 23 previous tests, not a production regression-suite claim.

```sh
PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMBA_NUM_THREADS=1 python -m research.diagnostics.counterfactual_trace --output research/diagnostics/results/counterfactual_effects
python -m research.diagnostics.classify_counterfactuals --trace research/diagnostics/results/counterfactual_effects/trace.json.gz --output research/diagnostics/results/counterfactual_effects/classification.json
python -m research.diagnostics.verify_fixed_scope_flags --output research/diagnostics/results/counterfactual_effects/fixed_scope_flags.json
```

The driver emits verbose `effects.json`; the published `.gz` is a lossless archive
of exactly those bytes. Its uncompressed hash is recorded in the witness receipt.
The readable summary removes only the per-producer record list. JSON byte size
reflects evidence serialization, not a search-memory benchmark.
