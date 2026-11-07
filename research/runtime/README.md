# Native Windows research runtime

This checkout was exercised on Windows x86-64 with Python 3.12.16. The runtime
is isolated at `%USERPROFILE%/.codex/envs/accelforge`, managed by micromamba.
The separate repository `.venv` uses Python 3.12.12 and runs the standard-library
`joint_synthesis` gate; it is not the FFM environment.

From the repository root, in PowerShell:

```powershell
./research/runtime/run_windows.ps1 -PythonArguments @('-m', 'pytest', '-q', 'research/joint_search/tests', 'research/joint_synthesis/tests', 'research/tracking_audit/test_platform_runtime.py', '--disable-warnings')
./research/runtime/run_windows.ps1 -PythonArguments @('-m', 'research.joint_search.validation', '--output', 'research/joint_synthesis/results/windows_baseline/native_audit.json')
./research/runtime/run_windows.ps1 -PythonArguments @('-S', '-m', 'research.joint_synthesis.validate', '--output', 'research/joint_synthesis/results/windows_baseline/composition_gate.json')
```

The wrapper selects the environment, sets UTF-8 output and a checkout-local
configuration, and preserves Python's exit status. It restores the caller's
environment and working directory. It does not change the user's default config.

## Compatibility boundary

PyPI currently supplies no Windows wheel for `islpy>=2025`; the native environment
uses conda-forge `islpy=2024.2`, built against ISL 0.27. This is an explicit
exception to the package metadata, not a successful unmodified `pip install -e .`.
The exact tested dependency inventory and test outputs are stored with the
Windows baseline. Do not compare these timings to archived macOS measurements.

The NVDLA/TPU research architectures specify their action energy/latency directly.
`windows_config.yaml` disables installed estimator autodiscovery: CACTI imports
POSIX `fcntl`, and NeuroSim requires a native build. CACTI/NeuroSim are absent
from this environment. Their physical energy/area estimation has **not** been
validated. Models requiring those estimators still need a supported POSIX setup.

The Python `resource` module is absent on Windows. FFM reports a warning when
finite worker limits cannot be OS-enforced. Peak process working set is measured
with `GetProcessMemoryInfo`; historical finished-child peaks are unavailable
(`null`), not assumed zero. The POSIX process-group watchdog tests are skipped
on Windows; their safety properties have not been tested here.

## Recreate the isolated native environment

Obtain micromamba from its [official distribution](https://micro.mamba.pm/), then:

```powershell
$mm = "$env:USERPROFILE/.codex/tools/micromamba/Library/bin/micromamba.exe"
$prefix = "$env:USERPROFILE/.codex/envs/accelforge"
& $mm create -y -p $prefix -c conda-forge python=3.12.16 islpy=2024.2 pytest pip
& $mm run -p $prefix python -m pip install -r research/runtime/windows-requirements.txt
& $mm run -p $prefix python -m pip install --no-deps -e .
```

The requirements intentionally omit the unsupported estimators and leave ISL
to conda. `pip check` will report the known metadata exceptions above. This is
a research configuration with explicit action costs, not general Windows support
for every AccelForge hardware estimator.
# Independent 3mm memory counts

```powershell
./research/runtime/run_windows.ps1 -PythonArguments @('-m','pytest','-q','research/runtime/test_memory_trace.py')
./research/runtime/run_windows.ps1 -PythonArguments @('-m','research.runtime.audit_memory_trace','research/joint_budget/results/fusion_3mm96/independent.json','research/joint_budget/results/matched_tail_3mm96/events_tail.json','--output','research/local_memory_trace.json')
```

The [memory trace](../joint_budget/results/memory_trace_3mm96.json) reconstructs bit actions from the dense 8-bit GEMM projections and serialized loop and storage nodes. It counts a transfer per tile epoch, shares matching addresses along supported fanout axes, keeps register instances private, and initializes an output once per address. A hand-counted fused example checks the projection cardinalities against explicit address and epoch sets. The comparison reads native actions after reconstruction.

All 96 perfect mappings match. Of the 348 accepted Event tail mappings, 170 match and 178 have a GlobalBuffer output read discrepancy. Every discrepancy adds 524,288 bits for one operator and tensor. A full tile and a nondivisible remainder in a reduction can update the same 65,536 addresses. The native path elides a first read in both groups. The independent trace elides it once. The selected 128 KiB phase winner matches, while the 132 KiB and 256 KiB phase winners have one and two affected output tensors respectively. Their archived energy and EDP values need rescoring.

The [phase rescore](../joint_budget/results/memory_trace_phase_rescore.json) adds the missing reads to the remainder phases and checks that the corrected ledgers sum to the independent whole-mapping counts. The three archived winners score 3.76319e-10, 3.30835e-10, and 2.99011e-10 J·s at 128, 132, and 256 KiB. The missing reads increase energy at the latter two budgets. Phase delay is unchanged under the archived throughput model. This rescoring retains the original winners and does not establish a new ranking of the complete native candidate space.

## Joint row-strip synthesis

```powershell
./research/runtime/run_windows.ps1 -PythonArguments @('-m','pytest','-q','research/runtime/test_strip_codesign.py')
python -m pip install ortools==9.15.6755
python -m research.runtime.benchmark_strip_codesign --output research/local_strip_codesign.json --repeats 7
```

The [benchmark](../joint_budget/results/strip_codesign_cpsat.json) uses all 24 ordered geometries of 6,144 PEs and the four registered SRAM capacities. Both solvers can choose any contiguous fusion partition of the chain. Each fused segment chooses an integer row-strip height. Every stage can pin its weight matrix in SRAM for that segment or stream individual weight tiles. It independently chooses any integer spatial reduction and output width within the array and tensor extents. Equal block counts permit retaining the smallest tile, since larger tiles only increase the capacity requirement under this contract. This grammar is generated from the workload dimensions without a seed mapping menu.

Each segment materializes its input and output at the DRAM interface. Within the segment, each row strip stays on chip across producer and consumer stages. Pinned weights stay live for the segment. Each stage reserves both its input and output strip, plus one streamed weight tile if needed. The wave trace walks the rectangular MAC domains, counts the two permitted broadcast/reduction directions and private register traffic, checks coverage and first writes, and tests the live bytes. It agrees with the common analytic evaluator for every timed winner and control. The tests also compare the search against an exhaustive tiny-space coordinate trace. The arithmetic contract uses 8-bit tensor and partial-sum storage. Time is a deterministic serialized service schedule for DRAM, the SRAM ports and MAC. The resulting EDP belongs to this service model.

The connected-segment dynamic program retains an energy/time frontier at each materialized interface. A fully fused, minimum-transfer schedule with SRAM relaxed gives an architecture lower bound. Inside each segment, the same relaxation for fixed pin choices and strip height bounds all narrower strips. Both energy and time are nondecreasing as the number of strips increases with these choices fixed. Only componentwise dominated partial results are removed. The independent CP-SAT model chooses cuts, integer tiles, and SRAM allocations and minimizes the exact scaled integer product. It receives a feasible all-streamed hint generated from the dimensions and hardware constraints.

Seven single-worker trials alternate method order. Timings include model construction, search, common evaluation and the independent winner trace. Across 18 workload and budget pairs, including square 3mm512 and four rectangular chains, both searches produced the same exact optimal EDP in every trial. The specialized search had a 2.16× to 24.22× speedup across case medians, with a median of 17.97×. On 3mm256, the range was 12.21× to 21.94×. At 132 KiB on rectangular 6mm, selecting the architecture jointly reduced EDP by 2.16% relative to choosing the architecture on the best unfused chain and then reoptimizing fusion. This two-stage control tied in the other 17 cases. For 3mm256, the fixed NVDLA geometry control had 12.14%, 0%, and 15.26% higher reductions available under joint search, measured as a fraction of the fixed-geometry EDP.

The connected-interval search, planned residency, and affine loop construction draw respectively on [Cascades](https://15799.courses.cs.cmu.edu/spring2025/papers/05-cascades/graefe-ieee1995.pdf), [MAGE](https://www.usenix.org/conference/osdi21/presentation/kumar), and [Pluto](https://www.csa.iisc.ac.in/~udayb/publications/uday-pldi08.pdf). The external baseline is [Google OR-Tools CP-SAT](https://developers.google.com/optimization/cp/cp_solver). The evidence covers this row-strip grammar and evaluator. STREAM and SET use different timing and mapping semantics, and there is no same-contract cross-accelerator SOTA result in this experiment.

```powershell
./research/runtime/run_windows.ps1 -PythonArguments @('-m','research.runtime.replay_strip_native','--reference','research/joint_budget/results/strip_codesign_cpsat.json','--output','research/local_strip_native.json')
```

All six selected 3mm256 and 3mm512 plans also pass AccelForge's native Fusion Join, array unfolding, integer MAC work, and exact SRAM capacity checks. The peak bytes and all per-tensor action counts agree between the wave trace, the independent projection of the serialized native mapping, and native evaluation. The [native replay](../joint_budget/results/strip_codesign_native_replay.json) checks the winning plans and does not transfer the strip evaluator's optimality proof to native timing.

### Equal wall-clock quality

```powershell
python -m research.runtime.benchmark_strip_deadlines --output research/local_strip_deadlines.json
```

The [deadline comparison](../joint_budget/results/strip_codesign_deadlines.json) uses the same six workloads and three budgets. Both methods pay for generating and validating the same starting design. A new incumbent is available once its common score and wave trace pass. The 5, 20, and 100 ms snapshots are read from complete solution trajectories collected in nine alternating single-worker trials. The time thresholds were chosen after the exact-search comparison to measure the millisecond search regime. Each method still reaches the same certified endpoint.

At 20 ms the specialized search found a lower EDP in 79 of 162 paired trials and tied in 83. Its median EDP was lower in nine of the 18 workload and budget pairs. The largest reduction was 25.05% on the rectangular 6mm at 132 KiB. The 132 KiB cases of 3mm256 and 3mm512 had median reductions of 7.32% and 8.66%. At 5 ms there were 26 wins, 135 ties, and one trial in which the specialized search had no validated result by the deadline. At 100 ms there were 51 wins and 111 ties. These are search-budget effects under the shared evaluator.

### Crossed hardware and fusion controls

```powershell
python -m research.runtime.strip_cross_ablation --reference research/joint_budget/results/strip_codesign_cpsat.json --output research/local_strip_ablation.json
```

The [crossed controls](../joint_budget/results/strip_codesign_cross_ablation.json) fix the 48×128 geometry selected on 3mm256 at 256 KiB and test it on every budget and holdout. The fixed and free geometry settings each run with singleton or adaptive fusion, and a fifth control forces the full chain to fuse while keeping geometry free. All control plans pass the independent wave trace. Free geometry reduces EDP by 1.93–3.40% on the four holdout budget pairs where it changes the optimum under adaptive fusion. It ties the fixed geometry on the remaining 14 pairs. Adaptive partitioning improves over full-chain fusion by 9.68% and 8.62% on rectangular 5mm at 128 and 132 KiB, and by 3.65% on rectangular 6mm at 256 KiB. The largest gains against singleton execution are primarily due to avoiding intermediate DRAM traffic.

## Native timing and port overlap audit

```powershell
./research/runtime/run_windows.ps1 -PythonArguments @('-m','research.runtime.audit_strip_overlap','--reference','research/joint_budget/results/strip_codesign_cpsat.json','--output','research/local_strip_overlap.json')
```

The [audit](../joint_budget/results/strip_overlap_audit.json) separately reconstructs native latency from tile shape classes and schedules address-derived traffic on one shared DRAM port, separate SRAM read and write ports, and the MAC array. It reproduces every native per-component latency and summed per-stage maximum on six square winners and five microbenchmarks. All six winner action ledgers agree. The reduction-tail microbenchmarks reproduce the native first-read omission.

Native time is below the conserved work of a single port for three of the six winners. For 3mm512 at 128 KiB, native time is 90.35 μs and the compulsory DRAM service time is 116.05 μs. The 1×64×64 microbenchmark isolates this behavior. A 32×32 tile gives a native time of 110 ns, equal to the DRAM work bound. A 48×48 tile performs the same DRAM traffic, but the native fold charges 63.33 ns. It keeps the largest shape class and loses service from the remainder.

The port calendar allows DMA service at both ends of a transfer and stages row reads, MAC work, and output writes on separate ports when there is enough SRAM for a row of ingress and egress staging. It walks exact tail extents and verifies transfer conservation, per-port exclusion, ordering and capacity. It is an explicit feasible schedule under the declared analytical architecture. The native timing formula remains a diagnostic for these tail cases.

The two 4×7×7 microbenchmarks have the same exact traffic and MAC cycles. The native model gives 24,576 ticks for both. Under an 84-byte SRAM ceiling, the 4×4 and 5×5 waves have different staging constraints and complete in 29,154 and 29,379 ticks respectively.

## Accelerator-specific overlap benchmark

```powershell
git clone https://github.com/maestro-project/gamma.git libraries/gamma
git -C libraries/gamma checkout 3d6caf8448b269fa25c2f224db97fcc470d0370f
./research/runtime/run_windows.ps1 -PythonArguments @('-m','research.runtime.benchmark_strip_overlap','--gamma','libraries/gamma','--output','research/local_strip_specialized.json')
```

The [benchmark](../joint_budget/results/strip_overlap_specialized.json) extends the generated strip grammar to the explicit port calendar. It considers every feasible integer strip, reduction tile and output tile. The energy/time frontier with unbounded staging is a lower bound for all strips with the same number of bands. If that frontier can be realized, further strip widths in the class are dominated. Otherwise the search prices the whole class with the actual full and tail capacities. An exhaustive tiny-space test checks the result against the event calendar. Smaller registered SRAM capacities are dominated within each budget because capacity only expands the feasible staging options and has the same per-action costs.

The FFM control calls the native `PmappingDataframe.merge_next` compatibility join and Pareto pruning at materialized boundaries. It receives the same connected-segment frontiers, hardware bound, and starting plans as the specialized search. This isolates the cost of the composition kernel in the common grammar. The external GAMMA control imports the pinned published implementation's parent selection, dimension crossover and tile mutation directly. The adapter maps those operations onto integer fanout, cuts, pin/stream and tiling genes and supplies the common evaluator. Geometry is represented by a legal fixed-PE factor-pair gene. The original MAESTRO costs and variable PE-count mutations are outside the shared contract.

Five rotating single-worker trials cover eight chains and three budgets, including 3mm512, four rectangular chains and a pair of asymmetric chains in forward and reverse width order. Every recorded incumbent was checked by the independent port calendar after the timed search. The timing includes construction of the common starting plans and the search, and excludes Python imports and the independent replay of archived incumbents.

On the Intel Core i7-12700 host, the two exact searches agree in all 24 cases. The specialized search proves the optimum 1.75–8.25× faster than the FFM join control, with a median of 3.29×. At 150 ms it beats the GAMMA adaptation in 71 of 120 trials and ties in 49. The largest per-case median EDP reduction at that deadline is 24.14% at 132 KiB on 3mm256. At 50 ms GAMMA is ahead in 14 trials, the specialized search in 44, and 62 tie. At 500 ms the specialized search leads in 70 trials and 50 tie.

The [native replay](../joint_budget/results/strip_overlap_winner_replay.json) reconstructs all 24 new winners in AccelForge and matches their modeled per-component times with the independent formula. Six native totals fall below the independently conserved single-port work bound. Nine action ledgers agree. The other 15 differ in partial-sum SRAM reads, which the shared calendar reconstructs from the tensor events.

The [control results](../joint_budget/results/strip_overlap_controls.json) freeze the 24×256 geometry selected on 3mm256 at 256 KiB. Joint search improves 22 of 24 results against this fixed geometry, up to 36.30% on the wide-output holdout. Against selecting the best geometry for singleton execution and then reoptimizing fusion and mapping, it improves 3mm256 at 132 KiB by 13.61% and ties the other 23 cases. Reranking under the overlap calendar improves seven of 18 archived serial winners on that same calendar, with a maximum reduction of 17.69%.

The original research systems and comparison scope are documented in [Fast and Fusiest](https://arxiv.org/abs/2602.15166), [DiGamma](https://arxiv.org/abs/2201.11220), and the [official GAMMA code](https://github.com/maestro-project/gamma/tree/3d6caf8448b269fa25c2f224db97fcc470d0370f). The proof and quality comparison cover this dense GEMM chain grammar and explicit NVDLA port contract.

### Architecture-first controls at SRAM transitions

```powershell
./research/runtime/run_windows.ps1 -PythonArguments @('-m','research.runtime.strip_architecture_stress','--reference','research/joint_budget/results/strip_overlap_specialized.json','--output','research/local_strip_architecture_stress.json')
```

The [stress study](../joint_budget/results/strip_architecture_stress.json) retains every geometry tied at the exact singleton optimum and reoptimizes fusion on all of them. It also trains a single fixed geometry on the product of 3mm256 EDPs across all three budgets, which selects 48×128. For the original 24 cases, the tie-aware architecture-first control preserves the 13.61% advantage at 132 KiB on 3mm256 and ties in 23 cases. The stronger fixed-geometry control is beaten in 11 of 24 cases, by up to 7.46%.

The additional sweep brackets a 3,072-byte staging target with two row extents for each of five matrix widths and three budgets. The search improves on tie-aware architecture-first in six of these 30 cases, by 0.40–7.99%. The other 24 tie. All joint and restricted designs are replayed through the independent port calendar. This locates the architecture-first failure near specific staging thresholds and preserves the cases where the simpler policy suffices.

## Branched DAG port calendar

```powershell
./research/runtime/run_windows.ps1 -PythonArguments @('-m','pytest','-q','research/runtime/test_dag_calendar.py','research/runtime/test_strip_overlap.py')
./research/runtime/run_windows.ps1 -PythonArguments @('-m','research.runtime.benchmark_dag_calendar','--output','research/local_dag_calendar.json')
```

The DAG grammar covers row-local dense GEMMs and elementwise binary joins. A mapping selects any topological order and partition into fusion groups, integer row bands and spatial waves, and weight residency per GEMM. An input into a group enters SRAM at first use. Produced rows remain live through the last local consumer. A cut value is written to DRAM once and a later group can fetch it with a different row-band partition. The same SRAM ceiling includes live activation rows, pinned weights, the streamed weight tile and capacity-gated row staging. The array issues one operator at a time. DMA can use both ends of its transfer simultaneously, and independent SRAM/MAC ports overlap within eligible row waves.

The compiler computes static intervals. The event replayer independently maintains live allocations, DRAM row coverage and per-column reduction progress. It checks that each read has a complete producer, every output is written once, and SRAM and port intervals stay within their bounds. Tiny replay also checks actual modulo-256 tensor values against a scalar implementation. Tests deliberately corrupt a release, remove a reduction remainder, and lower capacity. A separate exhaustive tiny DAG checks the exact result.

The search composes Pareto frontiers at topological ideals. A group order dominates another order of the same operators if it never increases per-operator live bytes. Both orders have the same cut transfers. With this dominance rule, the [DAG experiment](../joint_budget/results/dag_calendar_joint.json) verifies 12 joint designs and their controls on GLU, diamond, residual and asymmetric forks. Free ordering lowers EDP by 38.31% relative to the declared fixed order on the asymmetric fork at 128 and 132 KiB. Architecture-first ties in the 12 initial cases. This result isolates an ordering and SRAM-lifetime effect under the common calendar.
