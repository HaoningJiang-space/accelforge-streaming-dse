# Native Windows research runtime

This checkout was exercised on Windows x86-64 with Python 3.12.16. The runtime
is isolated at `%USERPROFILE%/.codex/envs/accelforge`, managed by micromamba.
The separate repository `.venv` uses Python 3.12.12 and runs the standard-library
`joint_synthesis` gate; it is not the FFM environment.

From the repository root, in PowerShell:

```powershell
./research/runtime/run_windows.ps1 -PythonArguments @('-m', 'pytest', '-q', 'research/joint_search/tests', 'research/joint_synthesis/tests', 'research/tracking_audit/test_platform_runtime.py', '--disable-warnings')
./research/runtime/run_windows.ps1 -PythonArguments @('-m', 'research.joint_search.validation', '--output', 'native_audit.json')
./research/runtime/run_windows.ps1 -PythonArguments @('-S', '-m', 'research.joint_synthesis.validate', '--output', 'composition_gate.json')
```

The wrapper selects the environment, sets UTF-8 output and a checkout-local
configuration, and preserves Python's exit status. It restores the caller's
environment and working directory. It does not change the user's default config.

## Compatibility boundary

PyPI currently supplies no Windows wheel for `islpy>=2025`; the native environment
uses conda-forge `islpy=2024.2`, built against ISL 0.27. This is an explicit
exception to the package metadata, not a successful unmodified `pip install -e .`.
The exact tested dependency inventory and test outputs are stored with the
[original Windows baseline](https://github.com/HaoningJiang-space/accelforge-streaming-dse/tree/bcbf818d/research/joint_synthesis/results/windows_baseline).
Do not compare these timings to archived macOS measurements.

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

## Executable DAG weight prefetch

The next-wave policy can put part or all of a following streamed weight tile
into otherwise idle SRAM-write intervals of the current GEMM wave. It reserves
the whole next tile alongside the current tile, all live activations and the
current wave's staging. Each prefetched word books both the DRAM and SRAM-write
ports. The following wave fetches any remainder before its register fill.
The policy looks ahead only to the next wave of the same operator.

The [fixed-pool replay](../joint_budget/results/dag_prefetch_decision.json)
uses the distinct choices made by the preceding pricing models. It checks
identical action counts and energy and accounts for all removed synchronous
DMA ticks. EDP decreases on nine of ten workload-budget pairs, with a maximum
decrease of 27.23% for 3mm at 128 KiB. GLU and asymmetric select different
members of this fixed pool with prefetch. The test covers feasibility and
reranking in this pool. It does not search every prefetch-enabled mapping.

The next experiment chooses the cheaper of overlapping rows and running
them serially in each wave, after accounting for how much DMA each mode can
hide. Prefetch uses only complete words that fit in the write-port gaps.
The replay constructs the two legal timelines and checks the selected
timeline. The analytical search prices their row, reduction and output-tail
classes separately. Each wave decision changes only the synchronous remainder
of its immediate successor, so this policy composes additively across waves.
The optimizer enumerates every row band and integer spatial tile within the
same DAG grammar, with a lower bound allowing weight DMA to overlap MAC service
but never the register fill. Exactness applies to this one-wave lookahead
policy. The test does not explore DMA across operator or group boundaries.

```powershell
./research/runtime/run_windows.ps1 -PythonArguments @('-m','research.runtime.dag_prefetch_search','--projection','--cases','3mm','glu','diamond','--budgets','135168','--output','research/local_prefetch_opt.json')
```

At [132 KiB over the three common array shapes](../joint_budget/results/dag_prefetch_optimized_132k.json),
reoptimizing GLU and diamond lowers EDP by 14.32% and 14.51% relative to
the previous mappings replayed with the same prefetch policy. GLU changes
from 48×128 to 32×192 and drops two pinned weights. Its DRAM traffic stays at
106,496 words and its prefetched weight words rise from 9,288 to 46,864.
Diamond also unpins a weight and preserves its DRAM volume. The strong
architecture-first control and the joint optimum agree on all three graphs.

The [ten-pair extension](../joint_budget/results/dag_prefetch_optimized_projection.json)
uses the same three array shapes at both SRAM budgets. Eight pairs improve
over the previous mappings when both sides use the executable prefetch
evaluator. GLU and asymmetric select a different shape at both budgets.
The chosen fusion partitions agree, and the fusion-enabled architecture-first
control ties joint search in all ten pairs.

Residual at 128 KiB gives a traffic reversal. Its previous mapping moves
409,904 DRAM words and takes 26,376,128 ticks. The reoptimized mapping moves
412,976 words and takes 24,048,720 ticks, lowering EDP by 8.32%. Both use the
same array and fusion partition. On GLU, repricing the best new mapping on the
old 48×128 shape gives EDP 1.22461e16 in the experiment's integer units.
Switching to 32×192 gives 1.22340e16, an extra 0.10% improvement. Most of the
14.32% reduction comes from changing the mapping on the old shape.
