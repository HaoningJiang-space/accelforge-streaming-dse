# Frozen validation of the existing constructive families

Base: ef165c9e. Freeze this file and runner before new constructor evaluation.
No candidate, metric, frontier, simulator or native FFM implementation changes.
This is validation, not tuning the family in response to test failures.

## Scope and test sets

1. All 31 shapes in coupling_sweep_heldout.jsonl, both patterns. These reference
   curves and their gap statistics have already been examined; they are held
   out from constructor design, NOT unseen mathematical observations.
2. Fresh shapes (I,J,K,L), both patterns: (2,2,8,4), (8,2,2,16),
   (16,2,16,8), (32,2,32,4), (64,2,64,8), (8,2,32,16),
   (32,2,8,16), (16,2,64,4). J=2 excludes the 256-shape development grid.
   Recompute the recursive reference from scratch for these cases.
3. FFN: check whether the actual producer/consumer index contracts in ffn()
   match the existing complete-three-MatMul fork grammar. A rejected contract
   is a transfer failure, not a license to replace the producer or drop live
   tensors. Do not report fork timings as full FFN timings.

## Fixed comparisons and metrics

Compare strips, reduced retention and full scoped retention, powers-of-two
only. The reference is curve_model's wider recursive-nest grammar, not a
physical global optimum or a native FFM runtime baseline. All methods compile
once for all capacities; none gets a per-query recomputation disadvantage.

Score the union of breakpoints, clipped from reference minimum capacity
through its plateau capacity. Also weight intervals by their count of integer
byte budgets; constant tails above the plateau cannot inflate success.
Report uncovered budgets, exact/within-5% fractions, maximum traffic excess,
and equal-traffic capacity ratios. Report per-instance and pooled results.
Fresh cases: three reference builds and seven rotated constructor repeats,
including construction and Pareto, excluding independent replay. Store samples.
Do not describe a quality-losing method as an exact-search speedup.

Screening gates (not claimed predictions): no uncovered reference budgets;
traffic excess <=10% at EVERY budget; >=90% of integer budgets within 5%;
constructor median cost <=half the fresh recursive reference. All must pass
before calling a family a broadly accurate cheap substitute. Report failures.

Execute the reduced and full plans witnessing each fresh case's maximum
traffic excess, plus their minimum-capacity and plateau plans, using the
unchanged independent cell simulator. Numerical outputs, complete operation
coverage, peak and per-tensor reads/writes must match. These selected replays
are not an exhaustive proof over the wider grammar.

## Existing FFN runs

Before this freeze, inspected the completed graph/nowt files: 1365/926 seconds.
Other nine part files are empty and logs end in MemoryError. Preserve source
hashes and label their source checkout b733c03e, with unrelated _version.py
modification. Do not attribute their runtime to this new benchmark. Score P12
against the best archived FFM row at each distinct capacity; P14-FFN remains
incomplete. No large rerun is authorized by this protocol's resource budget.

Run on the designated experiment server, four workers maximum, each with a
12-GiB address-space and 600-second CPU limit. Errors/timeouts are results,
never silently omitted. Record commit and tracked-dirty status, no login data.
