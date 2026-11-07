# Chat-supervised native joint-budget experiment

**SOTA acceptance remains unmet.** The native reference is reproduced, but the
first graph-support abstraction certifies no useful nonlocal family elimination.
There is no new BCGE optimizer or new-method speedup claim in these results.

The final Chat review accepts the infrastructure evidence and marks the research
gate **FAIL**. Both user SOTA criteria remain unfulfilled. The unresolved proof
obligation is one sound, nontrivial pre-expansion predicate together with bucket
closedness: deleting it must preserve pooled Pareto, ordered fallback and native
Join processing. This coarse support mechanism is not enabled as an optimizer.

Chat supervised the DB/OS/HPC reading and the experiment through
[GPT-6 / Extra High](https://chatgpt.com/c/6aee2ce0-094c-83e8-bfdd-5132e0ab9d62).
Codex implemented and ran the local code. [CONTRACT.md](CONTRACT.md) states the
problem, relaxed support proof, native-policy limitations, paper links, strong
baselines, acceptance targets and remaining obligations.

## Native 3mm reference

The frozen workload is NVDLA `matmuls(3,256,256)` on twelve physical architectures:
16x384 / 32x192 / 64x96, each at 128 KiB / 132 KiB-1 byte / 132 KiB / 256 KiB.
Explicit global budgets cap PE count at 6144 and SRAM at 128 / 132 / 256 KiB.
This is resource-budget selection, not calibrated-area synthesis.

Every reported method completes all twelve points. Cached and Event results
match the independent full E/T/exact-resource vector sets exactly. All 36
selected result instances reconstruct and reproduce their physical cost/capacity
and per-dimension spatial fit. These are selected instances, not necessarily
distinct mappings or replay of all tied sources.

| Existing method | One fresh-process grid, s | Actual expanded rows | Model rows | Join pair rows | Peak process GiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Independent FFM | 79.269 | 179,431 | 35,882 | 220,744 | 0.322 |
| FFM + existing enumeration cache | 73.255 | 43,154 | 35,882 | 220,744 | 0.330 |
| Existing Event + Bitset + cache | 26.263 | 43,154 | 9,086 | 55,862 | 0.288 |

There is **one diagnostic trial per existing method**, not five-trial medians or
a novel algorithm benchmark. Imports are outside the timer; spec construction,
preparation, generation, native Join, queries and cache scope are inside it.
Frontier comparisons, serialization and selected-source validation are outside.
Peak working set is captured before validation and includes imports. Finished
child peaks are unavailable on Windows. No cross-host ratios are reported.

The same physical architecture supports the whole graph. The selected designs
under the three resource ceilings are:

| SRAM ceiling | Selected array / SRAM | Native EDP, J s |
| --- | --- | ---: |
| 128 KiB | 64x96 / 128 KiB | 4.288793280512e-10 |
| 132 KiB | 32x192 / 132 KiB | 3.47009735196672e-10 |
| 256 KiB | 32x192 / 132 KiB | 3.47009735196672e-10 |

Thus the previously archived architecture-ranking reversal is reproduced on
Windows. A larger capacity is not automatically the selected design. These are
FFM-policy results, not a proof over every physically possible fused mapping.

Raw data: [independent](results/independent_1.json), [cached](results/cached_1.json),
[Events](results/events_1.json), [summary](results/summary.json).

## First pre-enumeration graph-support gate: negative result

`support_audit.py` prepares complete native raw template catalogs, forbids numeric
Tile expansion and native Join during the audit, and runs two-way support
projection to a fixpoint on the **first native Join edge only**. Hardware IDs
must agree for all mandatory operators. Later raw-operator pairs are not assumed
to describe the actual composed native prefix. Unknown
interfaces are retained. This relaxation uses backing/persistence and loop-count
keys, with all possible unit-loop deletion patterns; it does not invent a
materialization-only Fusion resource law.

| Resource ceiling | Hardware points | Raw template instances | Deleted families | Deleted hardware |
| --- | ---: | ---: | ---: | ---: |
| 128 KiB | 3 | 126 | 0 | 0 |
| 132 KiB | 9 | 378 | 0 | 0 |
| 256 KiB | 12 | 504 | 0 | 0 |

All 360 directed family-interface descriptors are known under the relaxation;
zero deletions are not caused by unknown placeholders. Fixpoint is reached in
one round. This is evidence that adding global hardware identity and repeated
support propagation to **this particular coarse abstraction** does not provide
useful pruning on this case. It does not disprove every stronger BCGE predicate.
Actual skipped jobs, saved numeric expansions and saved native Join work are
all zero. No job-deletion optimization is enabled.

The raw catalogs contain 864 loop instances whose `calculated_n_iterations`
formula is not yet populated. The proposed stronger `MayRealize` test therefore
cannot be inferred from these raw keys: it would require symbolic formula and
hard-constraint preparation, with its cost included. Native successful-match
coverage and bucket closedness remain explicitly uncertified in the JSON.

Native local Pareto pools jobs within Compatibility buckets. Deleting individual
jobs based on continuation support could change the surviving local candidates;
even necessary physical support does not by itself prove reference-policy
equivalence. A stronger resource/consumer predicate needs a separate proof before
it can skip real work. The current experiment deliberately stops at certificates.

[Raw support data](results/raw_support.json) includes raw family fingerprints,
budget domains, propagation results, explicit scope flags and source hashes.
[Seven tests](results/tests.txt) include same-hardware consistency, propagation
through a chain, isolated mandatory operators, unknown descriptors and exhaustive
witness preservation over forty randomized cyclic factor instances.

## Reproduce on this Windows host

Use [the isolated native runtime](../runtime/README.md), which explicitly records
its older Conda ISL and unavailable estimator exceptions. Native NVDLA action
costs were not changed. The broader five-directory regression passed
**661 tests, with one POSIX-only module skipped**, in 425.09 s:
[log](../joint_synthesis/results/windows_baseline/regression.txt).

```powershell
./research/runtime/run_windows.ps1 -PythonArguments @('-m', 'research.joint_budget.baseline', '--method', 'independent', '--output', 'research/joint_budget/results/independent_1.json')
./research/runtime/run_windows.ps1 -PythonArguments @('-m', 'research.joint_budget.baseline', '--method', 'events', '--reference', 'research/joint_budget/results/independent_1.json', '--output', 'research/joint_budget/results/events_1.json')
./research/runtime/run_windows.ps1 -PythonArguments @('-m', 'research.joint_budget.support_audit', '--output', 'research/joint_budget/results/raw_support.json')
./research/runtime/run_windows.ps1 -PythonArguments @('-m', 'pytest', '-q', 'research/joint_budget')
```

[Downloaded-source revisions](results/sources.json) identify the installed
ChatGPT skill and DOSA / DiGamma / GAMMA checkouts. External systems have **not**
been reproduced or compared under a common evaluator. DOSA's official setup
requires a Gurobi license and native Timeloop/Accelergy. Strong SOTA acceptance,
an independent complete joint optimizer, calibrated area, Attention validation,
five-trial comparisons and the propagation ablation remain uncompleted.
