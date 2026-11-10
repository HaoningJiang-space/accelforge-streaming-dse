# Where the exact solver's work goes, by graph family

State counts (REDUNDANCY_RESULTS.md) do not show where the time goes. This
study attributes each cache miss's **exclusive** work (its own DP transitions,
loop choices, Pareto candidates and time, minus those of child misses) to its
response stratum. It also counts every group query, hit or miss, that returns
an empty frontier.

Source `attribute_work.py` (`6700107a`) and `live_profile.py` (`72f83342`).
Records are in [results/work_attribution/](results/work_attribution/). All 49
cases are complete: the 47 census cases plus re-runs of same6/mixed6. Fresh
Linux processes, hash seed 0, exact cut DP, halving tiles, and no optional
reductions. Each case had at most 600 s, 6 GiB (RLIMIT_AS) and four workers.
Instrumentation slows the runs, so the times are relative only.

Strata, exactly one per miss:

- `empty`: no frontier point.
- `zero_at_d`: the single point (d, 0), with d the per-operator operand bound.
- `zero_above_d`: a single point (c, 0) with c > d. Extra traffic is zero, but
  the capacity is not at the operand bound.
- `rest`: everything else.

`repeat` additionally flags misses whose remainder-graph label
(`sufficient_stat`, residual_domain) was already seen. It approximates what an
isomorphism-keyed cache would reuse. A WL label is a proxy here, not a key.

## 1. Results

Share of exclusive DP transitions plus loop choices:

| Case | total | empty | zero_at_d | zero_above_d | rest | repeat | empty group calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fork 6, same role | 1,800,817 | 0 | 0.2% | **93.0%** | 6.8% | 6.5% | 15% |
| fork 6, kkkiii | 1,800,817 | 0 | 0.2% | **93.0%** | 6.8% | 2.4% | 15% |
| fork kkk, extents 4 | 74,023 | 0 | 0.7% | 30.3% | 69.1% | 10.3% | 4% |
| FFN forward 4 layers | 598,854 | 0 | 0 | 0.5% | **99.5%** | 4.3% | **53%** |
| attention forward 4 layers | 598,854 | 0 | 0 | 0.5% | **99.5%** | 4.3% | **53%** |
| FFN training 1 layer | 593,181 | 0 | 4.2% | 11.6% | **84.3%** | 2.4% | 35% |
| residual depth 24 | 832,369 | 0 | 4.4% | 4.8% | **90.8%** | **42.1%** | 3% |
| residual (4,4,8) depth 8 | 66,590 | 0 | 0 | 10.9% | 89.1% | 18.6% | 4% |
| ancestor k=8 | 41,297 | 0 | 0 | 7.4% | 92.6% | **99.3%** | 0 |

Two more observations:

- **What the work is.** In FFN-4, the 5,158 `rest` misses carry 590,626 DP
  transitions but only 5,531 loop choices. The cost there is cut-DP work over
  long spans, repeated across many (extents, residency) contexts.
- **How many tensors are live.** Among `rest` states, the share with at least
  three locally live nonscalar tensors is 93% (fork6), 97% (FFN-4), 91%
  (training), 99.5% (residual depth 24) and 100% (ancestor). The two-live
  normal form (ONE_OBLIGATION_RESULTS.md §3) covers k ≤ 2 only.

## 2. Reading

1. **Empty and lower-bound states cost almost nothing themselves.** They stop
   at a leaf or have no loop candidates. What they cost is the callers'
   transitions into empty groups: 53% of all DP transitions in the 4-layer
   stacks, 35% in training, 15% in the forks. Lemma 2 can skip these before
   the call. Each such transition is cheap (a cached lookup), so the time
   saved must be measured, not inferred from counts.
2. **The dominant mechanism depends on the graph family.**
   - *Forks*: 93% of the work is in zero-traffic states above the operand
     bound. These are the scalar-X zone, where the original scalar leaf counts
     every live scalar. A zero-traffic certificate (Scalar-X Bridge, which
     already removes 81% of transitions there) is the right tool.
   - *Repeated rank variables* (the residual chain, the ancestor control):
     isomorphism reuse covers 42% to 99%.
   - *Layered stacks with distinct rank variables* (FFN, attention, training):
     neither applies. Over 99% of the work is in nontrivial states, mostly
     with three or more live nonscalar tensors, and only 2-4% repeats a
     remainder.
3. **Analytic responses for the stacks need multi-tensor theory.** No
   certificate proved so far reaches the states that dominate the stacks'
   work. Two-live covers k ≤ 2, and the three-tensor counterexample already
   shows that single-axis obligation counts are insufficient.

## 3. Limits

- Exclusive counters attribute a transition to the state performing it, not
  to the child it queries.
- A WL `repeat` can over-merge non-isomorphic remainders. It is used here only
  as an estimate.
- Instrumented timings are relative only.
- Same grammar scope as REMAINDER_LEMMAS.md.
