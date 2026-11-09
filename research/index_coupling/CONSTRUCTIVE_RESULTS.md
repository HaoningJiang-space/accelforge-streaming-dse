# Constructive fork schedules: eex005 results

Direct construction recovers most of the preselected middle-of-curve capacity
targets without recursive nest enumeration. It does **not** recover the full
frontier. Allowing nondivisor strips yields independently executable traffic
improvements and slightly reduces one previously reported capacity separation.

All runs below executed as `wangziheng@eex005`, Python 3.12.16, in
`/home/wangziheng/graph_dse/accelforge-index-bounds`. Original FFN runs continued
in their original checkout. Neither FFM nor the existing curve model/simulator
was modified. The only existing documentation correction is the README's
half-strip scratch formula (`n/2+1`, not `n+1`).

## Scope and provenance

The input is the same/cross fork and its dimensions. The constructor creates
row strips, column strips, and whole-X schedules with tiled scratch. It may
retain a subset of tensors across the strip loop. It uses tensor dimensions
and contraction axes, no stored reference answers and no `curve()`/FFM call.

This is a constructive upper-bound family. It neither proves a global I/O
lower bound nor searches all legal physical schedules. Unit-byte cells, exact
integer arithmetic, two-level memory and no recomputation are inherited from
the existing experiment. These are modeled byte counts, not measured device
latency, calibrated chip area, or hardware accumulator precision.

Protocol was committed in **34e273d6** before these runs. All 256 shapes had
already been observed in previous experiments: this is not a held-out study.
Reference input is the sweep archived by **c82f2ee8**. Validation, sweep and
focus runs used 34e273d6; improvement replay used **f4a91e6a**; union-breakpoint
replay used **d82b4663**. Metadata in each raw file records clean tracked code.

## Main controlled effect

Absolute traffic targets, not excess traffic:

| Shape (I,J,K,L) | Target traffic | Same minimum capacity in archived grammar | Cross minimum capacity in archived grammar | Constructive power-of-two family |
| --- | ---: | ---: | ---: | --- |
| 8,8,8,8 | 576 | 37 | 69 | both exact |
| 16,16,16,16 | 2304 | 137 | 265 | both exact |
| 32,4,32,16 | 3456 | 529 | 1041 | both exact |

The full recursive-nest curves were regenerated for these six cases. Both the
selected constructive schedules and the selected exact-nest witnesses were
independently executed. The cross plan in the last row actually transfers
2944 bytes; the target is an upper bound, not a required exact traffic value.

For a nonretaining row strip of width b and p=ceil(I/b), the executable costs
are S=bK+b+1 and:

```
same:  Q = IJ + pJK + 2pKL + 2IL
cross: Q = IJ + pJK + (3p-1)KL + 2IL
```

The cross schedule spills V partial sums between row strips. Its extra cost
over the same schedule is `(p-1)KL`. This describes those schedules, not every
possible implementation. For square n, b=n/2 gives S=n²/2+n/2+1, with traffic
9n² (same) and 10n² (cross). The constructor also supplies a whole-X schedule
at n²+n/2+1 with traffic 9n². No write-through or shared DRAM reload is needed
for these constructions, separating this effect from the P11/P14 mechanisms.

Across all **64 I=K shapes**, at the preselected target achieved by the same
graph's nonretaining half-row strip, the power-of-two constructor matches
**116/128** archived minimum capacities (58/64 shapes match for both patterns).
The other 12 are worse, with worst capacity ratio **2.034**. The target was
defined in the protocol, not selected independently to favor each result.

## Wider tile grammar changes an important number

Allowing every integer strip width, including a shorter final strip, gives this
new cross schedule for `(32,4,32,16)`:

| Item | Value |
| --- | ---: |
| Row strip sizes | 11, 11, 10 |
| Persistent B | 128 bytes |
| Persistent V | 512 bytes |
| Largest X strip | 352 bytes |
| Scratch at the observed peak | U: 11, C: 1 |
| Peak | **1004 bytes** |
| Reads A / B / C / D | 128 / 128 / 1536 / 512 |
| Writes U / V | 512 / 512 |
| Total traffic | **3328 bytes** |

Independent execution confirms every count, all 36,864 MACs, and all 1024
output cells. It satisfies the 3456-byte target at 1004 rather than 1041 bytes.
The wider constructor's same plan still needs 529 bytes. The ratio within this
constructive family is therefore **1.898**, not 1.968. Neither number is a
lower bound across all tilings and schedules. In particular the larger
power-of-two grammar's 1041-byte minimum cannot be generalized to arbitrary
tile sizes.

At the 6471 archived capacity knots across 256 shapes and two patterns:

| Constructor | Equal traffic | Worse | Better | Capacity not covered |
| --- | ---: | ---: | ---: | ---: |
| Power-of-two strips | 1633 | 3046 | 0 | 1792 |
| All integer strips | 1600 | 2828 | 251 | 1792 |

“Not covered” means this small family has no plan fitting that capacity; it is
not a statement of physical infeasibility. Among the **251 improved knots**,
traffic savings have median **9.64%** and maximum **23.40%**. These are statistics
conditioned on improvements, not average savings over the entire sweep.

Example: same `(32,32,8,16)` at capacity 69 has archived traffic 6016. A width-7
row strip (last strip width 4) uses 64 bytes and transfers 4608, a 23.40%
reduction. This is a tile-grammar effect; it is not isolated evidence of a new
Graph algorithm outperforming a baseline with the same tile choices.

The subsequent, explicitly post-observation audit also checks the union of
reference and constructive breakpoints. **1030 distinct improving plans**
cover **1281 improved union knots**, and every plan passes independent numeric,
capacity and per-tensor traffic replay (10,810,880 MACs total). This includes
the 1004-byte point, which comparing only archived knots would miss. No new
native FFM search was run, so these improvements are against the archived
restricted curve-model grammar, not a demonstrated FFM representation limit.

## The reverse exception survives and the constructor misses it

For `(32,8,32,4)` and traffic target 3840, regenerated exact-nest witnesses give:

| Pattern | Capacity | Traffic | Allocation breakdown at peak |
| --- | ---: | ---: | --- |
| Same | 137 | 2560 | A64 + B1 + U32 + V32 + X8 |
| Cross | 133 | 3840 | B64 + C1 + U4 + V32 + X32 |

The cross schedule tiles both axes: a K block of 8 retains B and V while
I blocks of 4 are processed. It writes/reads U partial sums (384 bytes each)
instead of retaining the same-pattern combination of A, U and V. All results
replay correctly; the four-byte reversal is real in the declared grammar.

The small constructor returns 261 bytes for both patterns at this target and
does not encode these nested retention scopes. This is a concrete coverage
failure, not hidden by the successful midpoint examples. It prevents claiming
that cross coupling always requires more buffer, or that one-dimensional strip
formulas characterize the entire frontier.

## Construction cost and validation

Across the 512 shape/pattern instances, construction plus Pareto selection:

| Family | Candidate count | Median time per instance | Total time |
| --- | ---: | ---: | ---: |
| Power-of-two strips | 54–108 | 0.779 ms | 0.396 s |
| All integer strips | 72–576 | 2.310 ms | 1.285 s |

Selected exact-nest curve runs took 1.59–7.36 seconds; these runs included
witness construction. The small constructor solves a narrower problem and
misses many points. **No exact-search speedup factor is claimed.** Times above
exclude validation/replay and JSON serialization, which are experiment costs,
not online construction work. Reference curves were already available for the
sweep, and their stored answers are used only for scoring.

Independent checks:

- 440 complete schedules on four small shapes, both patterns, all integer tile
  choices and retention masks: all per-tensor counts, peaks and outputs match.
- Eight focused constructive schedules plus eight exact-nest witnesses replay.
- All 246 plans improving the 251 archived knots replay.
- All 1030 plans improving the union knots replay. These overlap the preceding
  set and must not be summed as unique plans.

The positive result is a cheap route from contraction structure to useful
executable choices at many middle-range targets. The limitations are equally
material: a narrow family, low-capacity gaps, missing nested retention and
dependence of exact threshold values on tile grammar. This supports further
experimentation with explicit quality/coverage measurements; it does not yet
establish a complete non-incremental optimizer or a universal separation theorem.

## Reproduce and inspect

From the independent eex005 checkout, with `PYTHONHASHSEED=0`:

```sh
/home/wangziheng/graph_dse/venv-main/bin/python -B -m research.index_coupling.run_constructive_fork validate
/home/wangziheng/graph_dse/venv-main/bin/python -B -m research.index_coupling.run_constructive_fork sweep
/home/wangziheng/graph_dse/venv-main/bin/python -B -m research.index_coupling.run_constructive_fork focus
/home/wangziheng/graph_dse/venv-main/bin/python -B -m research.index_coupling.run_constructive_fork audit_union
```

Replay uses at most four workers; the rest is serial. Raw records are in
[results/constructive_fork](results/constructive_fork/), including complete
curves, all scored points, source commits, execution counters and reconstructible
plan parameters. Remote originals are under
`/home/wangziheng/graph_dse/runs/constructive-fork-34e273d6/`.
