# D1: computation-DAG boundary diagnostic

This protocol is fixed before the six-case server run. M8 remains a conditional
solver microbenchmark. The new research target is shared-data DAG mapping:
fan-out, reconvergence, lifetime and common-loop coordination. The recursive
solver call DAG is not the computation DAG studied here.

## Scope and questions

Start with the supported access semantics, not a new general hypergraph solver.
Use exact grammar v2, one global topological order per plan, halving divisible
tiles, serial execution, single writers, no recomputation, unit-byte elements,
and unlimited frontier capacity. No layout conversion or physical timing model
is introduced. The complete reference is the Pareto union of unchanged native
Cut DP over every legal global order, including all legal common loops.

The frozen six cases in `study.py` are: a four-op chain control; its residual
counterpart; a rectangular residual; two four-op fork/joins; and a five-op
asymmetric fork/join with one elementwise product on a branch. The latter is a
GLU-like supported core, **not** SiLU/sigmoid or a complete real-model benchmark.
The residual join uses the grammar's product arithmetic with addition-equivalent
access costs; it is not a numerical ResNet implementation. The chain control
drops the skip input, so its operation/traffic totals are not normalized
performance comparisons with the residual.

The declared three regions are producer, branch body, and join. Their boundaries
come from producer/consumer roles; the middle region can contain incomparable
operators. All of these particular graphs admit region-block orders. This is
not a proof that arbitrary DAG regions can be made contiguous without loss.

Compare four arms, keeping exact native group search inside each region:

1. `native_all_orders`: complete reference in the declared grammar.
2. `closed_materialized`: fixed region partition, every shared boundary tensor
   through DRAM; no loop spans the regions.
3. `closed_retained`: same partition, exhaustive keep/DRAM boundary decisions
   with first-to-last-use reservations; no loop spans the regions.
4. `shared_row_loop`: arm 3 plus every legal whole-graph I-loop halving tile and
   retention mask, containing the same region composition within the loop.
   Regions exchange tiles inside a common loop, not necessarily whole tensors.

No prediction is made that arm 4 equals the complete reference. If it fails,
record every differing frontier breakpoint and an executable reference witness.
Do not expand loop families or shapes after seeing a failure in this run.

## Exactness claim for the building block

Fix ordered sibling regions, extents, caller residency R, and paid final-write
ownership W. Let K be the kept shared tensors; other shared tensors use DRAM.
For region i, charge rho_i = sum of sizes of K whose first-to-last region-use
interval covers i. Query its **group-entry** extra response under R union K
and W union the dropped intermediates' final-write ownership. Then compose

    P = max_i (rho_i + P_i)
    Q_extra = Q_boundary + sum_i Q_i.

For a dropped intermediate, charge one final store unless already owned, plus
one read per later region using it. A shared graph input pays one additional
read per region after the first. Child compulsory read/final-output charges
are removed before composition; the root adds its actual compulsory traffic
once. These rules include a branch that uses a tensor locally and exports it
to another branch/join. Caller reservations never become free child capacity.

For a fixed legal surrounding rank v, tile b and r trips, charge its retained
tensors once to capacity and its dropped obligations once as
alpha_t (r-1)|t|, with alpha=1 for inputs and 2 for accumulated outputs. Scale
the child EXTRA traffic by r, then add root compulsory traffic. The legality
check retains full operator iteration domains and forbids an unfinished
nonresident intermediate from crossing to a consumer.

Proof scope: for each fixed boundary decision, native child frontiers are exact;
every combination is executable and every plan in that fixed region/loop grammar
has such a combination. Max, sum and positive loop scaling preserve dominance.
Taking the union is therefore exact for **that restricted grammar**, without
proving that these boundaries summarize every plan in complete native search.

## Checks, accounting and stopping rule

- Independently compare every enumerated boundary mask against native
  `root_groups`/`root_kept` on the full graph, including inner loop contexts.
  This checks induced-child normalization and final-write ownership. The
  reference shares the cost recurrence, so equality alone is not a physical
  proof; independently execute every saved root frontier witness as well.
- Check that every restricted point is dominated by or equal to the complete
  reference, and compare whole staircases at the union of their breakpoints.
- Save topology, boundaries, remaining consumer identities, full witnesses,
  cross-region loop frames, SRAM/traffic, child generation, boundary-mask and
  join counts, native DP transitions, total wall time, replay time and peak RSS.
- Use fresh sequential Linux processes on the experiment server, hash seed 0,
  180 seconds and 6 GiB per case. Record exceptions/timeouts as incomplete,
  preserve outputs and source hashes. No imputed frontier or speedup.
- Restricted arms search smaller spaces, so their time/candidate reductions
  are **not same-quality search speedups**, even if a case happens to match.
  This correctness run also includes extra reference checks and is not a
  timing benchmark. No native FFM Event/cache comparison is performed in D1.

Stop after these six cases. Use the result to specify the next sufficient
boundary contract: common loop frame, tile projection, remaining consumers,
ownership and entry mode. General order elimination, dynamic DAG separators,
native FFM candidate coverage and actual scaling remain subsequent proof and
measurement obligations, not deliverables claimed by this diagnostic.
