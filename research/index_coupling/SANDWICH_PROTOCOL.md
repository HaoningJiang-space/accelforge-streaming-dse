# Sandwich certificate for chain states (frozen before measurement)

Scope: grammar v2, cut-DP partitions, halving tiles, spill cost 2, the
archived C2-audit call DAGs (`results/c2_bound/<case>/baseline.json.gz`).
This document is offline only: it adds no solver branch.

## Claim

For a solve state sigma of a chain span (contiguous ops, interior vectors
neither external nor owned; any M, any weight residency):

- **LB(C) = sum_j R_j(C).** This is the operator-projection bound,
  CONTRACTION_ORACLE.md §14. R_j is §12's keep-level optimum of contraction j
  alone, and elementwise operators contribute 0. It is proved.
- **UB(C)** is the singleton partition. Every op is its own group, and every
  interior vector is either kept or sent via DRAM:
  - kept: its size at the state's extents is charged as cells in both
    adjacent groups, and it is resident inside them;
  - via DRAM: 2 × its size is added as extra traffic, one write and one read.

  Each group's response is the single-op response with the given residency:
  §12's keep-level model for a contraction, and the number of live tensors
  (with zero traffic) for an elementwise op. UB is the minimum over keep and
  DRAM choices, computed by a boundary DP.
  - UB >= actual, because this is a plan the cut DP contains.
  - **This rests on one checked assumption:** the keep-level model equals
    the grammar's single-op response at the residencies used.
- **Certificate.** If UB(C) = LB(C) for every C, then actual = LB = UB. The
  state's response is then known without expanding any partition or loop.

## Measurements

For `ffn_forward_l1..l4`, `attention_forward_l2/l4`, `ffn_forward_l1_m8` and
`ffn_forward_l2_m8`:

1. **Validity (implementation check).** For every qualifying state, check
   LB <= actual <= UB at every capacity up to the last breakpoint + 2. Any
   violation is a bug or a refutation of the single-op assumption. It will be
   reported, not filtered.
2. **Coverage.** Report qualifying states, certified states, and certified
   states with M > 1, separately.
3. **Exactness.** Every certified state must equal its archived curve.
4. **Work.** Make certified states terminal in the call DAG, as in §15.
   Report the fraction of each exclusive counter in states no longer
   reachable from the root, for:
   - certified states only;
   - the union with unit-M closed-form states (§15).
5. **Failure attribution.** For qualifying but uncertified M > 1 states,
   report where the gap is: UB > actual (singletons are not optimal, so
   fusion is needed), or LB < actual (the bound is loose), or both.

## Decision rule

**Stop condition.** In the M8 cases, if the union in item 4 removes less than
20% of exclusive DP transitions beyond the unit-M closed forms alone, the
singleton upper bound is too weak. In that case, do not build an online
version. Report which gap dominates in item 5.

**Go condition.** If the threshold is met, a later online experiment must
time witness-bearing search and native witness reconstruction separately
from frontier-only search.
