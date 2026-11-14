# Evaluation contract and PyTorchSim pilot

The contribution under study is graph-structured mapping search. Backend
simulation is evidence about the selected executions, not evidence of search
optimality. No sample plots or proposed metric values are experimental data.

## Three research questions

| Question | Primary quantities | Required controls |
| --- | --- | --- |
| RQ1: hardware quality | end-to-end latency; energy/EDP once calibrated | identical hardware, precision, workload and charged search/evaluation budget |
| RQ2: search efficiency | wall time and time-to-target quality | same grammar/objective; exact frontier or certified bound; timeout rate and peak RSS |
| RQ3: architecture sensitivity | latency/energy versus SRAM, PE and DRAM budgets | separate mapping choice from hardware-resource changes; calibrated resource models |

Search speedup is T_search,baseline / T_search,ours. Execution speedup uses
execution latency instead. DRAM reduction is 1-Q_ours/Q_baseline. Energy
reduction uses independently modelled energy. These ratios are never interchanged.
Energy and EDP remain **unmeasured** until compute, SRAM, DRAM and interconnect
action costs, idle/static costs, calibration and units are specified. Cycles
alone do not supply energy. Fixed hardware has fixed area; no area improvement
is inferred from a mapping change.

The hardware comparison includes native Heuristic, native Autotune, baseline
exact DP and the new exact reductions. Native and research grammars differ.
Only matched-grammar experiments claim frontier preservation; fixed-budget
hardware experiments report best observed executable candidates and include
native candidates in the pool. Report compilation, search and hardware
evaluation time separately and charge all of them in time-to-target curves.

The current Capacity-Traffic Pareto frontier does **not** guarantee latency/EDP
optimality after reranking. A capacity/traffic-dominated plan can have different
utilization or overlap; tied points currently retain only one witness. Thus
timing/energy evaluation must preserve additional candidates or establish an
objective-compatible dominance theorem. The first pilot reports only the best
of evaluated candidates, with no latency-optimality gap unless a valid bound
exists. Timeout-derived feasible plans and proved bounds are separate fields.

## Why PyTorchSim first

The upstream source was inspected at
[`509f42554202edb29cf8d31ddf619776f465e717`](https://github.com/PSAL-POSTECH/PyTorchSim/tree/509f42554202edb29cf8d31ddf619776f465e717).
Its PyTorch compiler, tile-operation graph and NPU compute/DMA/memory models
are closer to the single-accelerator question than ASTRA-Sim's usual aggregate
compute interface. ASTRA-Sim remains a later distributed-system/communication
backend; it is not the SRAM mapping oracle.

Source-level findings, not a completed integration:

- [GEMM template](https://github.com/PSAL-POSTECH/PyTorchSim/blob/509f42554202edb29cf8d31ddf619776f465e717/PyTorchSimFrontend/mlir/mlir_gemm_template.py)
  contains explicit nested loop templates and tile/subtile selection. The
  documented external JSON is keyed by M_N_K. This is not a general importer
  of cross-operator partitions, arbitrary loop nests or retention scopes.
- [Configuration code](https://github.com/PSAL-POSTECH/PyTorchSim/blob/509f42554202edb29cf8d31ddf619776f465e717/PyTorchSimFrontend/extension_config.py)
  admits `external-then-heuristic` and `external-then-autotune`, whereas an older
  README example says `external`. A pilot must inspect actual selected tiles
  and reject unexpected fallback. A shape-key hit alone is not proof that the
  compiler retained the complete requested execution.
- [TOG generator](https://github.com/PSAL-POSTECH/PyTorchSim/blob/509f42554202edb29cf8d31ddf619776f465e717/AsmParser/tog_generator.py)
  and [parser](https://github.com/PSAL-POSTECH/PyTorchSim/blob/509f42554202edb29cf8d31ddf619776f465e717/TOGSim/src/TileGraphParser.cc)
  carry compute, loop, DMA and wait structure, including address/loop strides.
  A witness-to-TOG exporter therefore needs real address, lifetime, dependency
  and partial-accumulation translation. One aggregate DMA per graph is inadequate.

The authors' published accuracy/simulation-speed results are not our measured
accuracy or speed. The backend source, binary, compiler, hardware configuration
and dependencies must all be pinned for our pilot.

## Pilot acceptance sequence

1. Start with a standalone GEMM whose dimensions/tiles are admitted by both
   grammars. Compare external tile settings with native Heuristic and Autotune.
   Preserve the selected tile, loop order, template and fusion decisions.
2. Verify numerical outputs and derive a tile-by-tile address/transfer ledger.
   Compare MAC count, operand/accumulator sizes, SRAM reservations, partial-sum
   reads/writes and total bytes with independently replayed witnesses.
   Reject same-shape operator conflicts and compiler fallback. Explicitly
   distinguish useful bytes, DMA bytes and DRAM transaction bytes.
3. Only then record cycles, compute utilization, DMA active/idle and stalls.
   Overlapping components need not sum to total time; define the counters.
4. Extend to a two-linear/activation island and a residual join with a real
   witness-to-TOG importer. Restore the original tensor identities, layouts,
   byte addresses, allocation lifetimes, dependencies and loop trip counts.
5. Whole-model latency requires full operator coverage or a declared opaque
   backend for each barrier. Partial-island results are labelled as such.
   Add MobileNet-v2 and BERT/Llama coverage after the first three-model audit.

The first eight PyTorchSim GEMM executions are archived in
[PYTORCHSIM_RESULTS.md](PYTORCHSIM_RESULTS.md): five numerical passes, three
failures, and a separate DMA byte-address mismatch that blocks timing acceptance.
Raw cycles are diagnostics, not accepted performance results. Energy, EDP and
area remain unmeasured.

The independent chain audit at `7e03ab3b` further separates grammar optimum
from dependency-legal scalar scheduling. Its 4/5 result applies to the declared
dense, single-row, binary-feature FFN chain with at least two layers and the
specified residency contract. A one-layer resident-weight copy has a 3-cell
scalar schedule versus a 4-cell v2 plateau. The dense-chain checker needs an
incidence guard before general pruning use; this benchmark installs no such
certificate and makes no physical-optimality claim from v2 alone.
