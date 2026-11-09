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
