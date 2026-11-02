# Capacity-tracking audit

Can one RESOURCE_USAGE search replace one FFM search per GlobalBuffer capacity, and is the
FFM baseline itself optimal under capacity pressure? Workload: tag1 GLU (`glu_tag1.yaml`) on
`tpu_v4i`, fixed bandwidth, GlobalBuffer capacity swept.

## Library switches

All are environment variables. Memory lists are comma-separated; unknown memory names raise.

| switch | read in | effect |
|---|---|---|
| `AF_VARIABLE_RESOURCES` | `join_pmappings` | Join: keep the listed memories as objectives; drop other memories only when the sum of per-Einsum maxima proves they fit (tag1). |
| `AF_GENERATION_VARIABLE_RESOURCES` | `make_pmappings.get_memories_to_track` | With RESOURCE_USAGE: only the listed memories stay fully tracked; fixed memories are eliminated as in an ENERGY\|LATENCY search. |
| `AF_ABL_SKIP_BIG_ENOUGH` | same | Ablation: the listed memories skip the "big enough for every tensor" elimination. |
| `AF_ABL_SKIP_PMAPPING_ONLY` | same | Ablation: the listed memories skip the "never reserved across fused loops" elimination. |
| `AF_ABL_BIG_ENOUGH_UNTRACK_ONLY` | `make_pmappings.get_memories_to_track` | Ablation: for the listed memories, "big enough" only stops reservation tracking and keeps the usage objective. |
| `AF_ABL_ALLOW_UNREPRESENTABLE` | `make_pmappings` | Ablation (`1`): keep templates with a copy of a fusable tensor above a fused loop, which are skipped by default (see "Root cause" below). |

## Scripts

- `common.py`: spec construction, the three search variants (`indep`, `var`, `push`), switch
  hygiene (every switch is cleared before each search), and `check_pick`, which re-evaluates a
  picked mapping at its exact capacity and requires energy and latency to match within 1e-6.
- `capacity_audit.py M,G,C CAPS VARIANTS [--repeats N] [--jobs N] [ABLATION=MEMS ...]`: times the
  variants, strictly validates every pick, and prints a `SUMMARY` with speedups and per-capacity
  quality. Exits 2 if any pick is invalid. `--jobs` (at most 16) sets AccelForge worker processes;
  workers share the process group, so `run_capped.sh` counts and kills them with the main process.
  Compare times only between runs with the same `--jobs`.
- `run_capped.sh CAP_GB TIMEOUT_S LOG -- cmd`: runs a command in its own process group under an
  RSS and time cap, and exits with the command's status (137 if the watchdog killed it).
- `legacy_p0/`: earlier join profiling and GPU Pareto scripts (upstream `04cf894e`, reference only).

Run on the shared server from the repository root, with the tag1 venv and single-threaded math libraries:

    export PYTHONPATH=$PWD OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
    research/tracking_audit/run_capped.sh 16 3600 audit.log -- \
        ~/graph_dse/venv-tag1/bin/python research/tracking_audit/capacity_audit.py \
        256,512,1024 0.25,0.375,1,4 indep,var,push

## Findings so far

These came from the earlier per-question scripts (see commit `1dfa68c5`) and are to be
re-run with `capacity_audit.py`. Half scale (256,512,1024); "valid" means re-evaluation at the
exact capacity succeeded.

| GLB | indep | var | push |
|---|---|---|---|
| 0.25 MiB | 1.8361e-8 | 1.8202e-8, valid | 1.8361e-8, valid |
| 0.375 MiB | 1.8361e-8 | 1.8105e-8, **invalid** | 1.8260e-8, valid |
| 1, 4 MiB | 1.5488e-8 | same, valid | same, valid |

1. **var can pick an infeasible mapping.** At 0.375 MiB it reports 0.375 MiB of GlobalBuffer, but the
   reconstructed mapping needs 0.5 MiB and fails re-evaluation. Its reported energy (2.5087e-4)
   also differs from the re-evaluated energy (2.4992e-4). Searching directly at 0.375 MiB gives the
   same row, so filtering across capacities is not the cause. It is still open whether the
   reservation is under-counted or the row is reconstructed into a different mapping.
2. **Independent FFM misses valid mappings under capacity pressure.** 1.8202e-8 is valid at 0.25 MiB
   (hence also at 0.375 MiB), but indep returns 1.8361e-8 at both. With LocalBuffer exempt from
   both eliminations (former `AF_ABL_KEEP`), indep finds 1.8202e-8; exempting Register does not help.
   Which of the two eliminations is responsible, and why, is open.
3. The `jobs` leftover-variable fix (`54a7c6ff`) does not change indep at 0.375 MiB.
4. At small scale (64,128,256) all variants agree (within about 2e-8 relative) and every pick is
   valid; push took 173 s vs 214 s for var.
5. Full RESOURCE_USAGE without any elimination did not finish at half scale within 90 min / 24 GB.

## Re-run with capacity_audit.py (commit 30261d90, half scale, caps 0.25/0.375/1/4 MiB)

`--jobs 8` reproduces the serial EDPs and validity exactly (group peak 3.9 GB, no worker left
afterwards), so later runs use 8 workers. One repeat with 8 workers: indep 192 s, var 64 s (3.0x),
push 46 s (4.2x).

LocalBuffer ablations of indep (serial):

| indep with | 0.25 MiB | 0.375 MiB |
|---|---|---|
| default (LocalBuffer eliminated as big enough) | 1.8361e-8 valid | 1.8361e-8 valid |
| `AF_ABL_SKIP_BIG_ENOUGH=LocalBuffer` | **1.8202e-8 valid** | **1.8105e-8 invalid** |
| `AF_ABL_SKIP_PMAPPING_ONLY=LocalBuffer` | 1.8361e-8 valid | 1.8361e-8 valid |

So the invalid 0.375 MiB pick is not specific to the shared search: plain independent FFM produces
it as soon as LocalBuffer is tracked. var tracks every memory during generation and inherits it;
push and default indep eliminate LocalBuffer and avoid it, but also lose the valid 1.8202e-8.
Both effects involve LocalBuffer, the only memory with a spatial fanout (Z=4) and `min_usage: 1`.

Serial, 2 repeats (medians; group peak 0.65 GB): indep 533 s, var 193 s (2.77x), push 143 s (3.72x).
Quality is identical to the 8-worker run. Note that push is *not* equal to indep at 0.375 MiB:
push finds a valid 1.8260e-8 against 1.8361e-8. Neither reaches 1.8202e-8, which var found valid
at 0.25 MiB and which is therefore also valid at 0.375 MiB. `capacity_audit.py` now uses this
capacity monotonicity for the best known valid EDP.

## Tracing the invalid 0.375 MiB pick (indep, LocalBuffer tracked)

`trace_pick.py` (8 workers): the reconstructed mapping stores the shared input Z (256x512, 128 KiB)
in GlobalBuffer *above* the fused `c` loop. The valid 0.25 MiB pick never puts Z in GlobalBuffer.
Re-evaluated at 4 MiB, the bad mapping needs 0.5 MiB of GlobalBuffer (FFM: 0.375 MiB, short by one
Z) and 9.5e-7 J less energy than FFM scored. That is about one MainMemory read of Z (9.2e-7 J).

`check_shared_resources.py`: no shared tensor is freed with mismatched left/right memory or level, with
or without LocalBuffer tracked. Shared compatibility tensors are backing reservations (Z is backed in
MainMemory), so the GlobalBuffer copy of Z is not freed there. Shared-tensor freeing is ruled out.

Leading hypothesis (unverified): FFM scored a pmapping that keeps Z in GlobalBuffer *below* the fused
loop (freed before FFU, re-read from MainMemory each `c` iteration), but the mapping reconstructed from
the row places that Z storage above the fused loop. Next: rebuild the FFG pmapping of the bad row alone
and compare its scored and re-evaluated reservation and energy.

## Root cause of the invalid pick (verified with `trace_pick.py`, commit a2754ccb)

Per-Einsum pmappings rebuilt from the bad row (`row2pmappings`):

- FFG keeps Z only in MainMemory and, below the fused `c` loop, in LocalBuffer. It does not use GlobalBuffer.
- FFU additionally keeps Z in **GlobalBuffer above the fused `c` loop**.

`Mapping._from_pmappings` merges both into one tree. Nodes above the shared loop form the common prefix, so
the merged mapping holds Z in GlobalBuffer for FFG as well. FFG then reads Z from GlobalBuffer instead
of re-reading it from MainMemory: the energy is lower and the reservation spans FFG's execution, needing
0.5 MiB. FFM scored a different object: the combination where only FFU holds the GlobalBuffer copy
(0.375 MiB).

Why the join accepted it: `TensorReservation.get_backing_tensors` (compatibility.py; identical in
upstream main) keeps one reservation per tensor name, the backing one. FFU's extra GlobalBuffer copy of
Z above the shared loop is therefore not part of its compatibility, and FFG and FFU look compatible
although the tree language cannot express "only FFU holds this copy above the shared loop". Tracking
LocalBuffer only changes which candidates survive pruning, so this combination becomes the EDP winner.

Fix options:
1. Join side (conservative): treat non-backing holders of a shared tensor above the shared loop as part of
   compatibility, so the two sides must agree on them. Every accepted combination is then representable.
2. Reconstruction side: keep per-Einsum holders below a split instead of elevating them. This represents
   what FFM scored, but needs a check that the model evaluates such trees as intended.

## After the fix (commit 6dfce0ac, half scale, 8 workers, 1 repeat)

Skipped templates per search: FFG 8, FFU 8, FFH 12. `research/streaming_join` tests: 39 passed.

| GLB | indep (default) | var | push | indep, `AF_ABL_SKIP_BIG_ENOUGH=LocalBuffer` |
|---|---|---|---|---|
| 0.25 MiB | 1.8361e-8 | **1.8202e-8** | 1.8361e-8 | **1.8202e-8** |
| 0.375 MiB | 1.8361e-8 | **1.8202e-8** | 1.8260e-8 | **1.8202e-8** |
| 1, 4 MiB | 1.5488e-8 | 1.5488e-8 | 1.5488e-8 | not run |

Every pick of every variant is now valid under strict re-evaluation (exit 0). Times: indep 167 s,
var 51 s (3.2x), push 37 s (4.5x); group peak 3.7 GB.

Open: eliminating LocalBuffer as "big enough" (default indep, push) still loses the valid 1.8202e-8,
although a memory that never overflows should only add candidates when untracked.

## Root cause of the LocalBuffer loss: min-usage constraint used a leftover formula (fixed in 47f2a732)

`_make_tile_shapes` built the min-usage objectives with `formula=v`, where `v` was left over from the
preceding memory-usage loop, i.e. the usage of whichever memory came last. Which memory that was
depended on the tracked set, so eliminating LocalBuffer changed tile-shape pruning. Upstream main
already fixed this. The fix uses the run_model spatial usage column
`usage<SEP>spatial<SEP>{component}<SEP>{dimension}` and asserts it exists.

Confirmation before the fix: `AF_ABL_BIG_ENOUGH_UNTRACK_ONLY=LocalBuffer` (stop reservation tracking
but keep the usage objective) recovered 1.8202e-8, so the usage-objective set, not reservation
tracking, caused the difference.

After the fix (half scale, 8 workers, 1 repeat; 39 tests pass; group peak 3.5 GB):

| GLB | indep | var | push | indep, LocalBuffer tracked |
|---|---|---|---|---|
| 0.25 MiB | 1.8444e-8 | 1.8444e-8 | 1.8444e-8 | 1.8444e-8 |
| 0.375 MiB | 1.8414e-8 | 1.8414e-8 | 1.8414e-8 | 1.8414e-8 |
| 1, 4 MiB | 1.5786e-8 | 1.5786e-8 | 1.5786e-8 | not run |

All variants agree at every capacity and every pick re-evaluates. Times: indep 135 s, var 38 s (3.6x),
push 36 s (3.7x).

The earlier "best known" 1.8202e-8 and 1.5488e-8 were not legal: e.g. the 1.8202e-8 mapping splits g by
256 across LocalBuffer's spatial dimension Z (G = 512, fanout 4), using 2 of 4 instances, while
tpu_v4i requires `min_usage: 1`. `check_pick` missed this because `evaluate_mapping` checks capacity and
cost but not mapper constraints such as min_usage. That check is still to be added.
