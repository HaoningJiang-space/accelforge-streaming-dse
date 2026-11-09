# Scalar-retention proof and its empirical boundary

A restricted theorem is proved and implemented: two residence scopes can
replace an X strip by one X cell without changing any tensor's transfer count.
Inside three row and three column constructions, strip-width decisions can
then be eliminated analytically. This does not prove that those constructions
cover arbitrary fusion schedules or approximate the complete curve well.

[Proof](SCALAR_RETENTION_PROOF.md) · [Frozen protocol](SCALAR_RETENTION_PROTOCOL.md)

## Proven statements

With h=J+2L and row width r, the same per-tensor traffic can be realized with
one of three peaks:

    retain X:                     r(K+1)+1
    retain operand slices:        r(h+1)+1
    two scopes, scalar X:         (r+1)h+1

The better operand-residence choice is r*h+min(r,h)+1. Both constructions
perform each MAC once, complete the J reduction before consuming X, and never
spill X. The full proof supplies the allocation/lifetime trace and separate
same/cross read/write counts, including partial sums and ragged final strips.

Because every strip's traffic has the form alpha*ceil(I/r)+beta with alpha>0,
a capacity query selects the largest feasible width from three affine
inequalities, then its smallest equal-traffic representative. It requires
O(1) integer-arithmetic operations and at most two plan objects. The column
analogue follows identically. Compiling the full six-family frontier needs
only O(sqrt(I)+sqrt(K)) representatives for arbitrary integer widths, followed
by skyline sorting; the power-of-two grid already has logarithmically many.

These are exact claims inside this stated complete-fork grammar. The argument
is mathematical, not inferred from finite tests. It is not a general DAG
separator theorem or a novelty claim.

## Implementation verification

All compute ran on the designated experiment server with Python 3.12.16.
Proof, candidate code and protocol were frozen at `8be1e40e`; the aggregator
was added at `23868fd6`. Original constructors and the independent cell
simulator were unchanged. Inputs and revision are stored in every run file.

| Check | Result |
| --- | --- |
| Positive integer shape cases | 303 |
| Per-tensor traffic identities across all integer widths | 23960, all pass |
| Direct query / compressed frontier versus exhaustive six-family search | 569980 capacity queries, all pass |
| Additional non-power-of-two/endpoint checks | 5 shapes, 652 queries, all pass |
| Independent small executions, including ragged tails | 92, all pass |
| Invalid interface/width cases rejected | 5 |
| Execution with metrics() poisoned | passes |
| Fresh scalar-frontier executions | 16, all pass; 276480 operations |
| Independently executed calibration witnesses | both pass |

Integer-grid plan objects across the 303-shape check shrink from 71880 to
8904 (87.61% fewer), while the complete six-family numerical frontier is
unchanged. The count is candidate construction, not MAC execution or native
run_model calls. The power-of-two tests are separately recorded.

[Theorem checks](results/scalar_retention/validation.jsonl) ·
[Non-power checks](results/scalar_retention/nonpower_queries.jsonl) ·
[Independent fresh executions](results/scalar_retention/audit.jsonl)

## Matched-space timing

All three methods solve exactly the same six-family, all-integer-width
problem. Both compiler baselines may cache the whole frontier and use binary
search for all subsequent queries. Every row includes construction and query
time. Values are sums of within-case medians over four shapes, both patterns;
nine repeats rotate method order. Query counts are per instance.

| Queries | Exhaustive family + cached lookup | Quotient-compressed + cached lookup | Direct formula queries |
| ---: | ---: | ---: | ---: |
| 1 | 24.297 ms | 2.938 ms | 0.214 ms |
| 8 | 24.257 ms | 2.948 ms | 1.827 ms |
| 64 | 24.468 ms | 3.023 ms | 13.587 ms |
| 512 | 24.778 ms | 3.434 ms | 106.334 ms |

Compressed compilation is about 7.2–8.3x faster in these matched-family tests.
Direct queries win for very few queries, but lose to compiled/cached lookup
as the query count grows. Thus O(1) arithmetic does not imply a faster query
than a small cached frontier. No native FFM/Capacity Events speedup follows.

[All timing samples](results/scalar_retention/benchmark.jsonl)

## Wider-grammar quality: improvements and failure

Keep the old reduced/full constructors and add scalar schedules at the same
power-of-two widths. Compare with the unchanged recursive reference. The old
78 instances are now regression, not held out; eight NEW shapes/both patterns
supply 16 fresh instances. All 94 cases complete without errors.

| Set / full family | Integer budgets within 5% traffic | Worst traffic excess |
| --- | ---: | ---: |
| Old 78, before | 80.23% | 112.00% |
| Old 78, plus scalar | 80.34% | 46.07% |
| Fresh 16, before | 82.29% | 106.67% |
| Fresh 16, plus scalar | 84.96% | 42.64% |

All these full families have candidates at every reference-feasible budget.
Both the <=10% worst-loss gate and the >=90% within-5% gate STILL FAIL.
Across all 94, within-5% increases from 80.27% to 80.44%; it is a limited
full-curve improvement despite repairing the previous worst two points.

For the regression set, sums of median build times are 647.49 ms (full) and
666.29 ms (full+scalar). For the fresh set, 98.71 and 102.38 ms. These timings
include unchanged base-family construction plus scalar generation and a final
Pareto pass. They do not reuse a pre-built baseline for free.

The new worst full-family regression point is cross (64,4,64,64) at 3 B;
the fresh worst is same (64,1,64,4), also at 3 B. These points are outside the
new scalar construction's useful capacity range. They are not classified
by a new mechanism in this experiment.

[Case rows, frontiers and interval comparisons](results/scalar_retention/cases.jsonl) ·
[Aggregate scores](results/scalar_retention/summary.json)

## Two calibrated examples, now derived rather than looked up

- Cross (16,2,64,4), r=16, h=10: peak=(16+1)*10+1=171 B,
  traffic=800 B; every input/output transferred once. Old vector-X operand
  residence required 177 B. New independent execution matches exactly.
- Cross (64,4,64,8), column c=32, h=20: peak=(32+1)*20+1=661 B,
  traffic=4352 B. Old vector-X operand residence required 673 B.

These examples motivated the theorem; do not count them as held-out prediction
successes. The fresh instances test a rule that was frozen before evaluation.

## What the proof settles

There IS a cheap, semantics-preserving internal decision elimination for a
specified physical plan family: lifetime choice and strip width do not have
to be rediscovered by enumerating every member. The proof supplies both safe
coverage inside that family and fewer actual plan constructions.

There is NO proof that this family suffices for arbitrary nested residency,
that it meets the broader quality gate, or that it applies directly to FFN.
The fresh quality failures are evidence against that stronger claim. Keep the
identity and exact six-family solver as restricted results; do not relabel
them as a complete architecture–mapping synthesis algorithm.

## Reproduce

From a pinned checkout in the server environment:

```sh
python -B -m research.index_coupling.run_scalar_retention validate > validation.jsonl
python -B -m research.index_coupling.run_scalar_retention benchmark > benchmark.jsonl
python -B -m research.index_coupling.run_scalar_retention run > cases.jsonl
python -B -m research.index_coupling.run_scalar_retention audit --input cases.jsonl > audit.jsonl
python -B -m research.index_coupling.summarize_scalar_retention /path/to/result-directory
```
