# Mainline and reference boundaries

Active development branch: **`research/joint-synthesis`**, isolated from the
`research/main` working tree. No historical research directory is deleted.
`research/main` contains the initial executable gate at `a986b381`; this branch
continues the independent synthesis work and keeps its reference assets intact.

## Ownership

| Location | Role and maintenance boundary |
| --- | --- |
| `research/joint_synthesis/` | Active independent plan/demand/composition/DP work |
| `accelforge/frontend/`, `accelforge/model/` | Reusable IR/model infrastructure via future explicit adapters; currently unchanged |
| `accelforge/mapper/FFM/` | Frozen reference search/backend; never a call-through implementation of the new search |
| `research/joint_search/` | Frozen six-point engineering baseline (results through `d40a664b`); external comparison/validation only |
| `research/graph_coopt/` | Historical diagnostics and verified experiments; no new Memo/Join-pruner mainline |
| `research/tracking_audit/` | Historical correctness, capacity, Reservation and parametric-search evidence |

Freezing means no feature expansion of the old research engines. It does not
erase history or forbid a separately justified correctness fix. A reference fix
must be separately versioned, with its effect on existing results reported.

## Allowed dependencies

The active core is:

`graph_ir → physical_plan → local resource_demand / composition → graph_dp`.

`exhaustive_oracle` imports only plan/model **data**, implements its own physical
storage, scalar execution and counters, and cannot import production demand,
composition, schedule generation or Pareto helpers. `validate` compares the two
after measurements exist. It cannot feed Oracle responses into DP decisions.

Future external adapters may reuse AccelForge's Workload/Tensor IR, calibrated
component models and reconstruction facilities. They must not call native FFM
Mapping generation, Join or Pareto decisions to perform the new main search.
The current closed proof core needs no adapter or third-party package and runs
under `python -S`. Adding model/IR adapters changes that boundary and requires
explicit model/grammar equivalence checks, not a blanket import exception.

FFM and `joint_search` benchmarks/validation remain outside the new solver.
Their model differs from the current normalized barrier grammar. Neither source
reuse nor a shared tensor name establishes a fair EDP/performance comparison.

## Gate order

1. Execute and inspect the independent exhaustive Oracle on the declared grammar.
2. Check local formulas, explicit converters and composition against its actions
   and simultaneous copy occupancy; keep unsupported semantics rejected.
3. Check conditional DP against the unpruned complete space and replay sources.
4. Only then propose a separately scoped global architecture-budget synthesis.
5. Streaming/fused interfaces, 3mm/GLU and strong same-model performance gates
   require new proofs/coverage and remain unimplemented.

The current barrier gate passes the first three in its restricted model. Its
initial results are archived at `a986b381`; the modular replay is in
`results/composition_gate_modular.json`. File separation is engineering, not an
additional algorithmic or performance result. No placeholder architecture solver
or generic graph framework is added to imply later gates are complete.
