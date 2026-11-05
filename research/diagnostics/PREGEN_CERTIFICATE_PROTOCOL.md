# G2: pre-generation certificate feasibility, three ablations

This round uses the revised G2 definition: Local / Architecture / Graph
certificates. It does not implement the earlier proposed symbolic-preparation
reuse gate, a Conditional Frontier Engine, or an online FFM pruning path.

## Declared certificate class and proof obligations

Study a **necessary-condition relaxation**, not arbitrary conditional dominance.
The certified rejection rules are integer hard infeasibility only:

1. Local: inconsistent positive dense loop/Tile bounds, independently of capacity.
2. Architecture: Local plus minimum GB/Register bits or minimum spatial use above
   a real target's hard capacity. Minimum-utilization fallback is never a hard
   constraint. Unknown facts retain a Job.
3. Graph: Architecture plus lack of any relaxed support along a required tensor
   dependency, propagated to a fixed point after conditioning on the Job. Every
   unit-loop deletion is permitted, even unrealizable ones; alias/rank/order/Tile
   matching and joint consistency restrictions are relaxed, never invented.

The integer storage bound applies to linear, positive, direct-projection dense
MatMul stages with distinct operands and one instance. Before a storage node,
each unbound Tile variable has interval [1, previous upper extent]. Each tensor
copy covers at least the product of lower projection extents times precision.
Use the maximum bound across copies of the **same** tensor, not their sum. Native
per-stage reservation prefixes add distinct tensor occupancies, so their sum is
a lower bound. This is not a sum of peaks across stages. Other grammars are
unknown. Global resource bounds use max of stage lower bounds, **not** an alleged
exact Fusion peak or the unproved 100 -> 116 KiB transfer formula.

Any legal complete plan induces locally feasible templates and matching backing
interfaces on each required edge. Relaxed support contains all such edges;
arc-consistency deletion therefore cannot remove that plan. This proves hard
infeasibility of the **declared direct native template-completion space**, not
absence of a plan with a new Copy/Retile/recomputation operation. FFM fallback
and Pareto policy preservation is a separate obligation; no Job is skipped.

## Cost-bound diagnostic, separately labeled

Record optimistic real-arithmetic E/T lower bounds from mandatory MACs and
full-tensor DRAM backing transfers, using evaluated native action coefficients.
For perfect spatial factor loops, the usable count is bounded by the largest
divisor of the full rank extent that fits the fanout; unknown cases use the full
hardware fanout instead. Other nonnegative costs are dropped. Per-stage latency
uses max of compute/read/write service lower bounds. Graph bounds sum stage E/T
lower bounds over relaxed supported domains and use max for resources.

**These cost bounds do not issue rejection certificates.** In particular, no
roundoff theorem or equivalence to FFM's historical selection policy is claimed.
Only after all decisions are fixed, screen them against the already completed
reference fronts as a free post-hoc incumbent Oracle. This checks whether even
unrealistically good free reference incumbents would help the bounds. It is not
an online result, is not counted as certified coverage, and avoids pretending
that incumbent acquisition was free in a real algorithm.

## Blindness, timing, and evaluation

- Snapshot and analyze Jobs at `_allocate_jobs`, after resource-tracking setup but
  **before** `run_model` / Tile enumeration / physical row materialization.
- The analyzer API receives no G1 label, returned Tile, final frontier or saved
  timing. All original Jobs execute afterwards. G1 data enter only a separate
  retrospective appraisal, matched by exact pre-evaluation template identity.
- Main case: the same three 6,144-PE shapes and 128/132 KiB, Event+Cache/RU contract.
  Measure certificate computation three times in fresh processes, with a warm-up;
  publish all trials. Common template setup is still required and gets no saving.
- Report per-target exclusions separately from whole shared Job and whole-batch
  exclusions. Only all-target exclusions receive G1 whole-task cost credit. Never
  add a rejected-member count to a Job count or allocate time by rejected rows.
- Subtract certificate computation from post-hoc gross credit. This is a net
  **projection**, not measured search speedup, and omits any unimplemented engine
  overhead. Compare complete RU fronts exactly and check lower bounds on every
  generated model row. Track Local-waste 18 and Join-input-waste 54 separately.
- Holdout dense 2mm/3mm shapes check the generic rules independently of the 72
  post-hoc labels. Unit counterexamples cover loop degeneration, unknown support,
  fixed spatial infeasibility, non-additive resource peaks and shared copies.

Zero coverage would refute usefulness of this specific cheap relaxation on this
case, **not** all graph-conditioned dominance, correlated E/T/resource bounds,
or nonlocal resource-obligation certificates. G1's 52.9% is potential work, not a
guarantee that these inexpensive necessary conditions can recognize it.
