# Capacity-tracking audit

This is the current experiment entry point for fixed-bandwidth GlobalBuffer capacity
reuse on tag 1.0 (GLU, a matmul chain and MobileNet; tpu_v4i and nvdla). The three paths are `indep` (one search per capacity), `var`
(shared generation, selective resource tracking at Join), and `push` (also eliminate
provably unnecessary fixed resources during generation).

## Current status and limits

### Multi-workload validation, commit `3e6a8502`

Five cases, each with indep/var/push, three repeats in rotated order after an untimed
warmup, eight workers, no template-count limit, fixed bandwidth. Two cases ran at a
time under `run_capped.sh 24 7200`. Records: [results/multi_3e6a8502/](results/multi_3e6a8502/).

| Case | GlobalBuffer MiB | Median s indep / var / push | var | push | Peak RSS |
| --- | --- | --- | --- | --- | --- |
| glu 256,512,1024 @ tpu_v4i | 0.25, 0.375, 1, 4 | 124.3 / 33.9 / 32.9 | 3.66x | 3.78x | 3.8 GB |
| matmuls 3,256,256 @ tpu_v4i | 0.0625, 0.25, 1 | 60.4 / 25.4 / 21.2 | 2.38x | 2.85x | 3.5 GB |
| glu 64,128,256 @ nvdla | 0.03125, 0.0625, 0.25 | 23.6 / 8.0 / 7.4 | 2.97x | 3.20x | 3.1 GB |
| matmuls 3,256,256 @ nvdla | 0.03125, 0.0625, 0.25 | 10.9 / 4.4 / 5.4 | 2.46x | 2.01x | 3.0 GB |
| mobilenet 1 @ nvdla | 0.03125, 0.0625, 0.25 | 183.0 / 69.3 / 49.8 | 2.64x | 3.67x | 4.6 GB |

In every case indep, var and push pick mappings with the same re-evaluated EDP at every
capacity in every repeat; every pick re-evaluates exactly at its capacity, no variant
is below the best known EDP, and every usage check completed. The GLU@tpu_v4i EDPs equal
the `d422ce05` baseline below. The server load average was 150-220 on 256 cores, so
absolute times are noisy; each case's variants share its run's conditions.

- matmuls@tpu_v4i exited 3 under the then-current rule: at 0.0625 MiB, FFM's *reported*
  energy was 5.26846525e-5 in two repeats and 5.26846488e-5 in one (7e-8 relative),
  while every pick re-evaluates to E=5.2684652544e-5. Commit `371fb0e6` judges
  consistency and optimality on the re-evaluated EDP; re-judging all five logs with it
  finds every case consistent and best known.
- min_usage shortfalls are reported for GLU and MobileNet on both architectures and
  are all at the attainable maximum: a spatial dimension can only unroll ranks
  irrelevant to its tensor, so e.g. GLU FFG reuse_output on nvdla is 128/192, MobileNet
  pointwise 24/192 and 24/32, depthwise reuse_output 9/192, and FFH/depthwise
  reuse_input 1/128 or 1/32 (no irrelevant rank).
- MobileNet needed two fixes. The tag1 copy of the workload
  (`research/workloads/mobilenet_28_tag1.yaml`) renames `shape` and aligns Depthwise1's
  window. Its depthwise layers then failed in unmodified tag 1.0 with
  `KeyError: 'Depthwise0<SEP>n_iterations<SEP>2'`: a backing holder lowered through a
  sliding-window loop had its reservation below that loop (Compatibility counted it as
  fused) but `label_fused_loops` did not label the loop fused. `3e6a8502` labels fused
  loops from the actual reservation positions.
- Not covered: mobilenet@tpu_v4i (indep alone exceeded the 40-minute probe limit),
  eyeriss (energy plugin incompatible with tag1), bandwidth variation, larger shapes.

### GLU baseline, commit `d422ce05`

Current baseline, commit `d422ce05` (min-usage fallback fix, suboptimal picks fail the
audit). Half-scale GLU (256,512,1024), GlobalBuffer 0.25/0.375/1/4 MiB, fixed bandwidth,
no template-count limit, eight workers, three repeats in rotated order after an
untimed warmup. Run under `run_capped.sh 24 5400`; exit 0. Records:
[results/capacity_d422ce05_r3.txt](results/capacity_d422ce05_r3.txt).

| Capacity (MiB) | EDP, identical for indep/var/push in all repeats |
| --- | --- |
| 0.25 | 1.844437720269433e-08 |
| 0.375 | 1.841359736486614e-08 |
| 1, 4 | 1.5785650060107967e-08 |

| Variant | Search seconds per repeat | Median | Speedup vs indep |
| --- | --- | --- | --- |
| indep | 129.3 / 134.4 / 132.8 | 132.8 | 1.00x |
| var | 38.6 / 39.0 / 35.5 | 38.6 | 3.44x |
| push | 34.1 / 31.6 / 32.9 | 32.9 | 4.03x |

All flags are true except `all_min_usage_satisfied`: `all_picks_valid`,
`all_repeats_consistent`, `all_picks_best_known`, `all_min_usage_checks_completed`.
Process-group peak RSS was 3.8 GB. The server load average was about 216 on 256 cores,
so absolute times are noisy; the variants share each run's conditions.

Every pick has the same two shortfalls: Einsum FFH on ArrayFanout `reuse_input` and
`reuse_output`, usage 1/128 against min_usage 1. FFH is elementwise (b,m,c are relevant
to both its input and output), so neither reuse dimension has a rank to unroll and
1/128 is the highest attainable usage, which is FFM's documented fallback. Earlier
runs had the same mapping but reported no shortfall because the old checker skipped
dimensions without an explicit spatial loop. The min-usage fallback fix did not change
any pick in this experiment; the EDPs equal those recorded before it.

Earlier measurements and the investigation are in [HISTORY.md](HISTORY.md). The small
(4,8,16) smoke run used for the review is in
[results/review_smoke.json](results/review_smoke.json).

Remaining limits:

- The default `has_copy_above_fused_loops` filter excludes **all** templates with
  a non-backing shared-tensor copy above a fused loop. This is a conservative
  restriction, not a complete compatibility fix: agreeing copies on both sides
  may be representable too. Thus "unlimited templates" does not mean the original
  FFM Mapspace is preserved. Coverage and full-space optimality remain unproved.
- `min_usage` shortfalls and checker errors are different. FFM permits highest
  attainable usage when its minimum is unreachable. A shortfall is reported but
  is not by itself proof of a mapper bug; the audit does not prove that the fallback
  is globally best. A checker exception now invalidates the audit.
- Shared capacity filtering uses FFM's normalized floating-point Reservations.
  This does not certify byte-exact boundaries at every capacity scale.
- Streaming bounds temporary Pair blocks, not the live Frontier or total process
  memory. `run_capped.sh` samples RSS every two seconds; it is not a hard cgroup
  limit. The watchdog now cleans up its process group on SIGTERM/SIGINT/SIGHUP,
  timeout, RSS exhaustion and monitoring errors. SIGKILL cannot be handled, and
  descendants that explicitly leave the group are outside this guarantee.
- Capacity-only reuse is supported experimentally. Cross-bandwidth reuse, full
  candidate coverage, and a global memory budget are still separate tasks.

## Files and responsibilities

| File | Purpose |
| --- | --- |
| `summarize_audit.py` | One table per audit log: EDP per capacity and variant with invalid/suboptimal/shortfall flags, medians and speedups. |
| `capacity_audit.py` | Validated CLI, timed experiment loop, summary, worker cleanup in `finally`. Importing it does not start an experiment. |
| `common.py` | Spec/search setup, environment hygiene, float64 EDP selection, mapping re-evaluation, spatial-usage checks, quality accounting. |
| `test_audit_logic.py`, `test_capacity_audit.py` | Validation, failure propagation, numeric boundaries, CLI and cleanup regressions. |
| `test_min_usage.py` | Real tile-enumerator regression for unreachable min_usage and reachable/hard minima. |
| `trace_pick.py` | Investigate one row, per-Einsum reconstruction and final mapping; diagnostic output, not an acceptance gate. |
| `check_shared_resources.py` | Investigate reservation mismatches across joined groups. |
| `run_capped.sh`, `run_capped.py` | POSIX process-group watchdog; shell entry point delegates to a standard-library Python supervisor. |
| `legacy_p0/` | Older upstream GPU/profiling experiments; not the tag1 backend. |
| `HISTORY.md` | Chronological evidence and superseded hypotheses. |

The helpers clear inherited `AF_*` variables before each search. The configuration
record includes the revision and whether either library or research files are dirty.

## Running and interpreting an audit

From the repository root, in the existing tag1 environment:

```bash
export PYTHONPATH="$PWD"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
research/tracking_audit/run_capped.sh 16 3600 audit.log -- \
    ~/graph_dse/venv-tag1/bin/python research/tracking_audit/capacity_audit.py \
    256,512,1024 0.25,0.375,1,4 indep,var,push --jobs 8 --repeats 3
```

The positional list holds the workload's parameters. `--workload` and `--arch` select
another case from `common.WORKLOADS` and `common.ARCHES`:

| Workload | Parameters | Graph |
| --- | --- | --- |
| `glu` (default) | M,G,C | Z feeds FFG and FFU, which merge in elementwise FFH, then FFB |
| `matmuls` | N_EINSUMS,M,KN | chain of N matrix multiplications |
| `mobilenet` | BATCH_SIZE | MobileNet block: pointwise and 3x3 depthwise convolutions (`research/workloads/mobilenet_28_tag1.yaml`) |

Architectures: `tpu_v4i` (default) and `nvdla`. `eyeriss` is excluded because its
energy plugin is incompatible with the tag1 library. Summarize logs with
`python research/tracking_audit/summarize_audit.py audit.log ...`.

Compare only runs with identical jobs, case, constraints and cost models. Search time
excludes re-evaluation; total elapsed time includes validation. Each RUN is saved in
the log before the next variant. Archive the log and exact code revision together.

Every pick is reconstructed and re-evaluated at the target capacity. Energy and latency
must be finite, nonnegative and agree within relative 1e-6. Spatial checks cover every
dimension on the active compute path; an omitted spatial loop uses one instance.

The SUMMARY separates:

- `all_picks_valid`: all capacity/cost checks succeeded and the usage checker completed.
- `all_repeats_consistent`: each variant's EDP agrees across repeats (relative 1e-9).
- `all_min_usage_checks_completed` and `all_min_usage_satisfied`: successful checking
  versus actual attainment of the requested utilization.
- `quality.*.suboptimal` and `all_picks_best_known`: a valid pick has worse EDP than
  another known valid pick feasible at that capacity (relative 1e-6).

Exit codes, most severe first: 2 for invalid picks (including an incomplete usage check)
or arguments; 5 if any variant is suboptimal; 3 for inconsistent repeats; otherwise 0.
A min_usage shortfall alone is reported but does not fail the run. Unexpected search errors propagate as failures,
and the capacity-audit worker pool is cleaned up on both success and exceptions.

The watchdog preserves the child exit code. It returns 137 for an RSS/time limit,
4 for live group members left after the main command exits, 128+signal when the
supervisor is cancelled, and 125 on launch/monitoring failure. `NO_VLIMIT=1` disables
only the per-process virtual-address limit; sampled RSS and time limits still apply.

## Bug-fix review after a686597f

- After Reservation insertion, fused-loop labels now use the actual first/backing
  Reservation of every shared tensor, matching Compatibility. Inferring the boundary
  from a Storage's `_lower` flag mislabels both reservations stopped above a loop and
  reservations lowered through multiple relevant loops. Four of five focused cases
  failed before the fix; all pass afterwards. Template-stage labeling is unchanged.
- Utilization checking includes `usage_scale`, as the model does. CONFIG builds the
  selected Case rather than always inspecting the default GLU configuration.
- The watchdog eliminates the startup race between `setsid` and the first `ps`,
  selects PGID explicitly, cleans up on cancellation, and fails on monitoring errors.
  Real child/grandchild tests cover exit status, all three cancellation signals,
  timeout, orphan cleanup and RSS control with `NO_VLIMIT=1`.
- Log summarization tolerates truncated JSON and missing historical flags, showing
  them as incomplete/unknown. A new CONFIG resets state, so an appended failed run
  cannot inherit an earlier successful SUMMARY.

Validation: 101 focused audit/Streaming tests passed locally. The single-process
`matmuls(2,4,8)@nvdla` smoke test at 0.03125/0.125 MiB completed under the watchdog:
indep/push had identical EDP 9.449881321091679e-17, all four picks re-evaluated, and
all usage checks completed. Expected shortfalls on this small shape are reported.
This was one run without warmup, not a speedup benchmark. Structured log lines:
[results/bugfix_matmuls_smoke.txt](results/bugfix_matmuls_smoke.txt).

## Regression tests

```bash
PYTHONPATH="$PWD" OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    python -m pytest -q research/tracking_audit research/streaming_join
```

The captured-Join tests default to the trusted, checked-in
`streaming_join/fixtures/real_join_large_tag1.pkl`. `CAPTURE_FILE` may override it
with another trusted capture of the expected schema. The capture uses a Pandas
StringDtype pickle format that Pandas 2.2.3 cannot read; the review suite was run
with Python 3.12, Pandas 3.1.0, NumPy 2.3.5 and paretoset 1.2.5.
These tests are not a full DSE benchmark or an exhaustive search-space proof.

## Library switches

Memory lists are comma-separated and unknown memory names raise.

| Switch | Effect |
| --- | --- |
| `AF_VARIABLE_RESOURCES` | Join retains the listed resource tradeoffs; fixed resources are removed only after the sum-of-maxima capacity proof. |
| `AF_GENERATION_VARIABLE_RESOURCES` | With RESOURCE_USAGE, preserve listed variable memories during generation; fixed memories use the normal elimination rules. |
| `AF_ABL_SKIP_BIG_ENOUGH` | Exempt listed memories from the full-tensor-size upper-bound elimination. |
| `AF_ABL_SKIP_PMAPPING_ONLY` | Exempt listed memories from the below-all-backing-holders elimination. |
| `AF_ABL_BIG_ENOUGH_UNTRACK_ONLY` | Stop reservation tracking for listed "big enough" memories while retaining usage objectives. |
| `AF_ABL_ALLOW_UNREPRESENTABLE=1` | Diagnostic restoration of templates excluded by the conservative copy filter; may reproduce invalid reconstructions. |

The ablation switches are experiment controls, not validated production features.
