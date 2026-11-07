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
