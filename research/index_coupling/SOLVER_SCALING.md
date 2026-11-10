# Exact solver scaling: implementation and bounded comparisons

This work changes search representation and accounting of search work. It does
not change the frozen P21d candidate cuts or turn a failed prediction into a pass.
`partitions='enumerate'` remains the default. The DP added in c922be9e remains
opt-in pending wider validation.

Measurements are now complete; see [SOLVER_SCALING_RESULTS.md](SOLVER_SCALING_RESULTS.md).
The initial comparison used c38b2fa1. Revision 347f0029 subsequently added the
medium residual control and `--no-profile` for repeated uninstrumented timings.
The solver itself is unchanged between those revisions.

## Implemented reductions

1. **Project write ownership to local producers.** For a span S, retain only
   `owned ∩ outputs(S)` in both recursive cache keys. `external` still projects
   to all tensors accessed by S. `ownership_projection=False` preserves the
   previous owned-key rule for comparisons.
2. **Merge exact frontiers by a linear sweep.** The older merger already avoided
   a Cartesian product; this removes its temporary capacity sets and sort.
   Static tensor axes and loop legality metadata are reused across extents.
3. **Measure work.** `curve(..., stats={})` records cache hits/misses/sizes,
   partition choices, loop choices, DP states/transitions, frontier candidates,
   merges and witness rope nodes. Pareto and merge timers exclude child search;
   total time includes everything. These are instrumented times, with profiling
   overhead, not timings of an uninstrumented production build. A state is counted
   when visited at a nonterminal DP boundary; a transition/choice when attempted.
4. **Stream the all-plan audit.** `graph/plan_stream.py` lazily walks the unpruned
   enumeration grammar. It stores active recursion and witnesses, not every
   subplan or a full Cartesian product. It deliberately does not cache subplans:
   reduced memory can cost repeated work. Counts now mean derivations, including
   duplicate witnesses; they cannot be compared to the old distinct-witness count.

The audit checks generation nodes and elapsed time during expansion, and its CLI
also uses a wall-time alarm and address-space cap (Linux experiment environment).
`--limit` applies before generating the next complete plan. Examples of failures
are bounded to three. Only generator exhaustion is `complete`; a plan/node/time/
memory limit is partial coverage and exits 2, or 1 if a checked plan failed.
Hitting exactly the plan limit is conservatively partial without looking ahead.

## Why the ownership projection is exact

In `_solve(S)`, `owned` is read only in the price of a dropped tensor with a
writer in S. `_group_curve(S)` passes ownership to descendants and never reads
it in its loop-spill price. Every descendant writer is also a writer in S.
Thus removing an ownership bit for a tensor with no writer in S cannot affect
any local charge, legal choice, or descendant charge. Induction over smaller
spans and decreasing loop extents proves equality of the generated costed
derivations, hence of their Pareto frontiers. This is a property of the current
grammar, not a general lifecycle-state sufficiency theorem.

## Cut DP scope and repairs

For fixed extents, external reservations and write ownership, prefix DP keeps
the keep/DRAM decisions of tensors crossing the current chosen cut. A decision
persists through the tensor's last use. Child group optimization still explores
the original loop/retention grammar. With a single writer per tensor, per-group
charges add to enumeration's partition charge; sibling capacity combines by max.
Within an identical boundary state, a dominated prefix cannot improve any suffix.

This argues equivalence to the existing partition recurrence, **not** that these
bits describe every physically legal schedule. Outer-loop retained partial sums
remain in the recursive interface, so ordinary whole-graph cut width alone is
not a bound on total runtime. The number of frontier points and recursive extent
and reservation states can still grow exponentially.

The new checks repair negative shifts at boundary zero with restricted cuts.
Spans with repeated output writers fall back to enumeration: the current DP's
single-writer transition does not implement their accumulation price. DP rejects
`grid != None`; approximate bucket pruning is order dependent and is not covered
by the exact-equivalence argument. Fixed root partitions continue to enumerate.

## Validation and comparison plan (fixed before server measurements)

`python -m unittest research.index_coupling.test_solver_scaling
research.index_coupling.test_p21d` checks:

- Numeric DP/enumeration and old/new projection equality, with independent
  simulation of every returned frontier witness on nine small graphs.
- Conditional external/written states, restricted cuts, fixed root groups,
  write-through/shared constraints, partial-sum pricing and multiwriter fallback.
- Linear merger versus a Cartesian-product reference, including capacity limits
  and the enumeration mode's approximate grid.
- Entire unpruned derivation multisets versus the former eager method on four
  tiny graphs, including legacy pricing, plus execution of corrected plans.
- Plan/node/time budget behavior without materializing the unpruned space.

`bench_solver_scaling.py` compares enumerate/DP × old/projected ownership keys.
All arms enable witnesses and profiling, use fresh processes, and independently
simulate every returned frontier point. The fixed cases are fork(2,2,2,2,kki),
residual(2,2,2,depth3,readX), P19 fork(8,4,8,2,kkkkkk/kkkiii), and
residual(8,2,4,depth12,readX). Each job gets 180 seconds including replay and 6 GiB
address space, with at most four jobs concurrently. These cases are a performance
sample, not new held-out scientific predictions. A completed pair can establish
equality on that graph; a timeout cannot establish it. Each result records source
hash, revision, Python version, resource use and its own checkpoint. Resumption
requires matching source and configuration. Existing experiment jobs are untouched.

## Literature connection

The conditional DP follows the lesson of [PLDI 2002 space-time optimization](https://www.csc.lsu.edu/~gb/TCE/Publications/SpaceTime-PLDI02.pdf):
Pareto comparison must preserve the constraints affecting future composition.
The lazy audit follows the generator/budget separation discussed in
[PPoPP 2020 YewPar](https://www.dcs.gla.ac.uk/~trinder/papers/ArchibaldMST_PPoPP20.pdf).
Neither source proves this solver's boundary state sufficient. Safe lower-bound
pruning and parallel work stealing are subsequent extensions; no heuristic
candidate filtering is being substituted for an exact oracle here.
