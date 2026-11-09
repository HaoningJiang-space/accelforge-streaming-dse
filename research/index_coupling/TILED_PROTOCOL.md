# Scoped two-axis construction: protocol before execution

Starting point: 52aee77d, 256 archived shapes already observed. This is an
exploratory extension and ablation, not a held-out prediction. All experiments
run on eex005 in the existing isolated worktree; ongoing FFN runs are untouched.

The two known nested-retention witnesses for (32,8,32,4) motivate the extension:
same retains A/U/V across K; cross retains B/V across I. Do not encode the
shape, traffic target, reference peak or witness in candidate generation.

Construct two-axis rectangular tiles of X. Pick I-outer or K-outer. Retain
any subset of tensors invariant across the inner tile axis at the outer scope.
EX finishes each X tile, then EU and EV consume it. Partial outputs are either
resident across their reduction tiles or explicitly spilled. The three small
matmul kernels can pick row-vector/scalar or column-vector/scalar scratch
orders, with identical per-tile traffic. Independent cell execution determines
their scratch choice from actual reservation sets, not the analytic formulas.

For each tile grid, compare:

1. Existing strips/whole-X family unchanged.
2. Existing family plus 2D tiles, **no** outer-scope retention.
3. Existing family plus 2D tiles with all legal outer-scope retention subsets.

Use both powers-of-two and all integer tile widths (ragged final tiles).
Hold the grid fixed within each ablation; distinguish wider-grammar improvements
from improvements over a baseline supporting the same tiles.

Measurements:

- Validate every new plan on (1,1,1,1), (2,3,4,5), (5,3,3,2), (4,4,4,4),
  both patterns and all integer tiles. Compare exact peak and all tensor reads/
  writes, numerical outputs and MAC completion. Also reject invalid interfaces.
- Preserve the original midpoint targets and all 6471 archived capacity knots;
  report improvements, matches, regressions, uncovered points, candidate counts
  and construction-plus-frontier times for all 512 shape/pattern instances.
- Additionally score the union of the new and archived breakpoints, rather than
  treating agreement at saved capacities as full-curve equality.
- Report the same/cross reverse exception at target 3840 separately. Success
  there does not validate the remaining 255 shapes by itself.
- Replay every newly retained 2D frontier plan in the power-of-two experiment.
  For the wider grid replay every 2D plan responsible for an improved union
  breakpoint relative to the archived grammar or existing strip family.
  Parallel replay may use at most four CPU workers.

The family still excludes DRAM-backed X, write-through, scope-dependent
partitioning and deeper nests. It is not assumed complete. No change to FFM,
curve_model, the old constructor or the independent simulator is required.
Any timing advantage over the broader recursive-nest search is a time/quality
result, not an exact-search speedup claim.

## Follow-up after observing the three-way sweep

The original ablation has run: the power-of-two scoped family matches 121/128
midpoint targets, versus 116/128 for both other modes. The reverse exception
is recovered at 137/133 bytes. No result is retroactively called a prediction.

The same-pattern witness suggests a cheaper subset. A nonretaining row strip
of width r keeps rK cells of X. An alternative instead retains A/U/V (same)
or A/U/D (cross), tiles K by one, and keeps only r cells of X. Both read/write
counts are identical: inputs have the same number of passes and outputs the
same number of partial-sum writebacks. The capacities are respectively
`r(K+1)+1` and `r(J+2L+1)+1`. The column analogue substitutes I for K and
retains B/C/D (same) or B/C/V (cross). These are two constructive alternatives,
not a lower bound or a proof that other retention masks are redundant.

Test one additional, separately labeled mode: old strips + no-retention 2D
tiles + only these two sets of residence alternatives. Check the traffic
identity for every integer strip on all archived shapes. Measure whether it
preserves the midpoint gains, how much full-curve quality it loses relative
to all masks, and how much construction work it avoids. Do not replace or
rewrite the original three-way sweep. This adds I/K strip choices, not their
Cartesian product, beyond the no-retention 2D baseline.
