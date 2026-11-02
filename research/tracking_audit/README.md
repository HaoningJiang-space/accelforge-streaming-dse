# Capacity-tracking audit

This is the current experiment entry point for fixed-bandwidth GlobalBuffer capacity
reuse on tag 1.0 GLU. The three paths are `indep` (one search per capacity), `var`
(shared generation, selective resource tracking at Join), and `push` (also eliminate
provably unnecessary fixed resources during generation).

## Current status and limits

The recorded half-scale experiment uses shape (256,512,1024), capacities
0.25/0.375/1/4 MiB, eight workers, and no template-count limit. At `9a4af4fc`,
the recorded three-repeat medians were 136.7 s / 39.8 s / 33.6 s for indep/var/push.
However, its min-usage checker raised a KeyError. A separate one-repeat run at
`64fd1fb0` reported agreeing EDPs and completed checks. That does not retroactively
validate all three repeats. These figures are historical measurements, not new
measurements of the current revision; the raw server logs are not included here.
The investigation and obsolete results are preserved in [HISTORY.md](HISTORY.md).

The current review fixes another tile-enumeration bug: when no candidate reached
`min_usage`, FFM selected the **lowest** usage instead of the highest attainable
usage. A small test using the real enumerator reproduced usage 0.125 instead of 0.5.
The fix preserves 0.5. The historical benchmark needs a new run after this change.

Local review validation: 32 audit/enumerator/CLI tests and 39 Streaming/Pareto
tests passed. A one-process GLU smoke run at shape (4,8,16), capacities
0.03125/0.125 MiB, found identical indep/push EDP 1.1906192914835282e-15.
All four picks re-evaluated and all usage checks completed; the small workload
has spatial utilization shortfalls, which are explicitly reported. The run had
one repeat and no warmup, so its timing is not a speedup result. Structured
records are saved in [results/review_smoke.json](results/review_smoke.json).

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
  limit. It also has no signal-forwarding trap: terminating only the wrapper can
  leave its detached command alive. Use its timeout for unattended experiments.
- Capacity-only reuse is supported experimentally. Cross-bandwidth reuse, full
  candidate coverage, and a global memory budget are still separate tasks.

## Files and responsibilities

| File | Purpose |
| --- | --- |
| `capacity_audit.py` | Validated CLI, timed experiment loop, summary, worker cleanup in `finally`. Importing it does not start an experiment. |
| `common.py` | Spec/search setup, environment hygiene, float64 EDP selection, mapping re-evaluation, spatial-usage checks, quality accounting. |
| `test_audit_logic.py`, `test_capacity_audit.py` | Validation, failure propagation, numeric boundaries, CLI and cleanup regressions. |
| `test_min_usage.py` | Real tile-enumerator regression for unreachable min_usage and reachable/hard minima. |
| `trace_pick.py` | Investigate one row, per-Einsum reconstruction and final mapping; diagnostic output, not an acceptance gate. |
| `check_shared_resources.py` | Investigate reservation mismatches across joined groups. |
| `run_capped.sh` | Linux process-group RSS/time watchdog. |
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

Compare only runs with identical jobs, shape, constraints and cost models. Search time
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
