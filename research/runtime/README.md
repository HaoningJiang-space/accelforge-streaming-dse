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

The audit covers the action counts of the serialized dense GEMM mappings. The phase timing and SRAM lifetime checks are separate.
