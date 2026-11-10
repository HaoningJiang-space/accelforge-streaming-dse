# Final-write ownership fix, all-plan audit, and the exact cut DP

Completed 2026-11-09 on the designated server; raw records in
`results/ownership/`. Frozen results and their records are unchanged; the old
pricing is reproducible with `legacy_nested_writes=True`.

## 1. The defect and the fix (`39ca741e`)

P21d found that two nested partitions both charged the final DRAM write of the
same intermediate. A partition that sends an intermediate through DRAM now owns
that one write and passes the tensor to its children as written; the owned set
is part of the projected cache key.

## 2. All-plan audit (`audit_all_plans.py`, first version `3bdb0b0f`)

Witness replay only checks frontier plans, so an overpriced plan the solver
discarded stays invisible. With Pareto pruning disabled and sibling curves
combined by full product, every plan of seven tiny graphs was executed:

| Graph | Plans | Checked | Fixed: wrong prices | Legacy: wrong prices |
| --- | ---: | ---: | ---: | ---: |
| coupling same (2,2,2,2) | 175,522 | all | 0 | 21,840 |
| coupling cross (2,2,2,2) | 175,522 | all | 0 | 21,840 |
| fork kk (2,2,2,2) | 175,522 | all | 0 | 21,840 |
| fork kki (2,2,2,2) | 11,164,470 | first 200,000 | 0 | 28,288 |
| residual (2,2,2) depth 2 | 70,880 | all | 0 | 0 |
| residual (2,2,2) depth 2, reads X | 58,356 | all | 0 | 10,303 |
| residual (2,2,2) depth 3, reads X | 417,814 | first 200,000 | 0 | 36,025 |

Every legacy error overcharges exactly 4 B, one duplicate final write of a
4-element intermediate; no other error kind appears. Two graphs are partial
coverage. (Codex later replaced the auditor with a streaming version in
`c38b2fa1`; these counts come from the first version.)

## 3. Regression of archived curves (`regress_ownership.py`)

| Archive | Tasks | Unchanged | Changed |
| --- | ---: | ---: | ---: |
| classify_v2 / p14 small graphs | 76 | 76 | 0 |
| coupling sweeps (P15/P16) | 287 | 287 | 0 |
| P18 | 84 | 84 | 0 |
| P19 (n=8 and n=16) | 32 | 32 | 0 |
| P21 unrestricted | 16 | 16 | 0 |
| P21d arms (completed) | 16 | 14 | 2 |

No curve rose and every changed curve's frontier witnesses replay exactly. The
two changes are the P21d structural arms the frozen scorer had already marked
invalid (cases 7 and 9: 488→456 and 552→520 at capacity 3). Repriced, both
equal their unrestricted curves. Many plans were overpriced, but none was on
an archived frontier, so **no archived frontier and no frozen verdict changes**.
P21d remains failed: 4 unequal (the K(L−I) counterexample persists under
correct pricing), now 4 equal, 4 depth-12 cases incomplete in the frozen run.

## 4. Exact cut DP (`c922be9e`, `partitions='dp'`)

`_solve` enumerated all 2^(n−1) contiguous partitions. A tensor crosses cut p
when ops on both sides use it; at a chosen cut that means two groups share it.
The DP builds partitions left to right; its state at p is the keep/DRAM choice
of each crossing tensor, on which every later cost depends, so each state's
prefix frontier can be Pareto-pruned. Child groups still search the original
loop/retention grammar. Costs, ownership, write-through and split_shared rules
mirror the enumeration.

Each benchmark ran both modes in separate processes (8 GiB, 1800 s each);
DP frontier witnesses were all executed (`bench_cut_dp.py`):

| Graph | Ops | Max crossing | DP seconds | Enumeration seconds | Equal | DP replays |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| residual (2,2,4) d4 | 6 | 2 | 0.1 | 0.2 | yes | 7/7 |
| residual (2,2,4) d6 | 8 | 2 | 0.2–0.3 | 1.8–2.3 | yes | 7/7 |
| residual (2,2,4) d8 | 10 | 2 | 0.4–0.5 | 24.7–27.2 | yes | 7/7 |
| residual (2,2,4) d10 | 12 | 2 | 0.9–1.2 | 254–288 | yes | 7/7 |
| residual (2,2,4) d12 | 14 | 2 | 1.4–1.7 | timeout | — | 7/7 |
| residual (8,2,4) d12 | 14 | 2 | 5.7–7.3 | timeout | — | 9/9 |
| residual (4,8,2) d12 | 14 | 2 | 6.8–7.8 | timeout | — | 10/10 |
| fork (8,4,8,2) kkkkkk | 7 | 1 | 725 | 1515 | yes | 16/16 |
| fork (8,4,8,2) kkkiii | 7 | 1 | 717 | 1527 | yes | 16/16 |
| fork (8,8,8,4) kkkiii | 7 | 1 | 890 | 1741 | yes | 14/14 |

Ranges cover the two read modes. Enumeration grows about tenfold per two
residual operators; the DP about twofold. The four depth-12 graphs that timed
out in frozen P21d now have exact, executed frontiers in seconds. Those are
supplementary computations; they do not rescore P21d.

The forks gain only twofold: at width 1 the partition layer is cheap, and the
cost is the loop/retention recursion inside the six-consumer group. Cut width
bounds the partition layer only; it is not a bound on total runtime.

## 5. What this does and does not establish

- The serial-grammar pricing is now consistent with independent execution on
  every plan checked, not only frontier witnesses.
- For contiguous partitions, the keep/DRAM choices of crossing tensors are a
  sufficient boundary state in this grammar (equality on every completed
  comparison, plus the argument above). Its size is set by cut width, which is
  2 or less on every graph here.
- Not established: a compact state for the loop/retention layer, which now
  dominates on forks; any statement about non-contiguous schedules, overlap,
  or hardware beyond this grammar.

Next: count states per cut and per recursion layer (P2), and target the
loop/retention layer, where the forks now spend their time.
