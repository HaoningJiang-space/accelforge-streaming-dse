# Global hardware/mapping EDP exploration

Status: experimental route under Chat GPT-6 Extra High supervision. No external
SOTA or algorithmic novelty claim. The initial geometry bound is a control for a
future buffer/fusion-sensitive bound, not a sufficient research contribution.

## Decision and declared problem

Coarse raw-template interface propagation deleted no templates. A separate attempt
to generalize shared native preparation failed pre-model Tile-catalog coverage;
the prototype and failing output are archived as text in `results/control_rejected*`
and `results/native_shared*`. Neither is enabled by the new solver.

The new solver minimizes global EDP across *physical* hardware and native mapping
choices under independent PE and SRAM ceilings. This is not calibrated chip area.
Each visited shape invokes the unmodified native FFM/Event mapping search. It
shares capacity cohorts and enumeration-cache entries exactly as the Event
control does. A feasible incumbent is independently reconstructed on its selected
physical shape and SRAM before it may justify a cut. Initialization, reconstruction,
bound construction, oracle work, queries and cache scope are all timed.

An EDP cut cannot establish global E/T Pareto preservation. The implementation
explicitly reports `full_global_pareto_preserved=false`. Completeness is relative
to the frozen native FFM policy, including its fallback and fusion filters; it is
not completeness over every legal physical mapping.

## Current bound and its restrictions

For NVDLA, 8-bit values and an n-operator M-by-K matrix chain:

```
operations = n M K²
compulsory external bits = 8 (2 M K + n K²)
E_lower = operations * MAC_energy + compulsory_bits * DRAM_energy
P_upper = floorpow2(min(Px,K)) * floorpow2(min(Py,K))
T_lower = n M K² * MAC_latency / P_upper
```

The compulsory transfers comprise the original input, all distinct weight
matrices, and final output. Intermediates can remain on chip; no spill penalty is
assumed. All GlobalBuffer energy is omitted. Action coefficients remain those of
the upstream NVDLA YAML. Both bounds are deliberately multiplied by 0.99.

The spatial bound requires perfect power-of-two ranks and the frozen spatial
grammar: input reuse can spatialize the output N rank, output reuse the reduction
K rank. Their products cannot exceed the largest power-of-two factors allowed by
the respective rank extents and fanouts. It is not valid for general imperfect
tiling, different spatial reuse policies, extra independent spatial dimensions,
or a model with overlapped operator execution. Native FFM sums operator costs.
Source fingerprints guard architecture/workload changes. The solver rejects
imperfect tiling, nonzero Pareto tolerance and unsupported workloads.

For nonnegative objectives, `E_lower*T_lower >= incumbent_EDP` rules out strict
improvement. Every affected budget must have a feasible incumbent before a region
is removed. The implementation rounds the cutoff upward using the larger of
reported and reconstructed costs, with an additional conservative allowance.

The 0.99 weakening is **not** a universal floating-point error theorem. Acceptance
requires an independent finite audit checking E and T against every complete
reference-frontier vector, replaying each cut and checking witness provenance,
budget membership and discovery time. This certifies the declared finite policy
experiment after validation; it is not a general numerical proof for new inputs.

## Pre-registered domains and controls

Keep the original 12-point 3mm domain as a negative control. Its shape-aware bounds
pass the full native-frontier check but the oracle-incumbent diagnostic can cut
zero points at every budget. That diagnostic is never read by the real search.

An independent arithmetic domain rule selects **all** ordered integer factor
pairs of 6,144 PEs and the same four original SRAM capacities: 24 shapes, 96
physical hardware points. No shapes are selected using benchmark measurements.
The original 12 points are included. This expansion deliberately tests the effect
of unfavorable array geometry; improvement here alone would not demonstrate a
buffer/fusion-sensitive contribution.

Controls use identical geometry ordering, Event+Bitset, cross-shape
EnumerationReuse, worker count and improving-witness validation:

* `events`: no cuts;
* `configured`: configured-PE compute bound, without rank/factor sensitivity;
* `shape`: rank/factor-aware geometry bound.

Initial diagnostics may overlap or use evolving code and must not be treated as
formal timing repetitions. Formal measurements must freeze code and run at least
five fresh processes **sequentially**, with complete raw outputs, medians and work
counts. Post-search reference reading and audit time is separate and explicit.

## Literature and next stronger mechanism

[Trummer and Koch, PVLDB 2014](https://www.vldb.org/pvldb/vol8/p221-trummer.pdf)
provides a DB precedent for vector-valued parametric optimization. Its query-plan
replacement rules do not automatically justify native FFM partial-state pruning.
[Sia, SOSP 2023](https://suhasjs.github.io/files/sia-sosp23.pdf) motivates matching
resource configurations to work, but its empirical throughput predictions are
not admissible deletion certificates here.
[Orojenesis, ISCA 2024](https://timeloop.csail.mit.edu/orojenesis) analyzes attainable
data movement as a function of buffer size, including fused operation sequences.
It motivates a capacity-sensitive lower envelope. Its documentation identifies
the reference implementation and supported workloads; we have not reproduced its
artifact or imported its bounds as proven facts about this native model.

The meaningful next test is whether a proved capacity/fusion-sensitive envelope
can eliminate hardware *beyond* the geometry bound on balanced arrays and on a
second workload. Do not sum independent intermediate communication bounds across
fused operators; that can double count transfers avoided by fusion. External
DOSA/DiGamma comparison still requires common evaluator, declared mapping-space
intersection, budgets, seeds and search-time accounting. Downloaded upstream
repositories alone are not reproduced baselines.

## Commands (native Windows environment)

First diagnostics: the original 12-point run preserves all native vectors and
cuts no shapes. On the 96-point domain, the full Event control executes 24 native
shape solves; shape-bound search executes 10 and cuts 14 regions (56 physical
points). All visited complete vectors, all skipped reference E/T bounds, all cut
arithmetic/provenance and all three global EDP values pass the independent audit.
Expanded rows decrease from 230,369 to 71,909; model rows from 85,914 to 30,450;
Join pair rows from 358,045 to 189,680. These are actual work counters.
The diagnostic Event run overlapped briefly with the 12-point correctness run
and preceded a witness-ledger extension; its 120.633 s versus 72.263 s must not be
treated as a frozen-code statistical speedup. Sequential repetitions remain due.

```
./research/runtime/run_windows.ps1 -PythonArguments @('-m','research.joint_budget.bound_gate','--reference','research/joint_budget/results/independent_1.json','--output','research/joint_budget/results/bound_gate_original12.json')
./research/runtime/run_windows.ps1 -PythonArguments @('-m','research.joint_budget.region_search','--method','events','--domain','factors96','--output','research/joint_budget/results/region_events96_1.json')
./research/runtime/run_windows.ps1 -PythonArguments @('-m','research.joint_budget.region_search','--method','shape','--domain','factors96','--reference','research/joint_budget/results/region_events96_1.json','--output','research/joint_budget/results/region_shape96_1.json')
```
