# Architecture-family certificates and a real final-Join sanity check

This directory separates two experiments with different assumptions. Neither is
an end-to-end cross-architecture FFM speedup or a new graph-bound theorem.

## Actual FFM: experimental final-Join pruning with an oracle incumbent

[audit_real_join_bound.py](../../audit_real_join_bound.py) first runs normal FFM
for `matmuls(2,4,8)`, NVDLA `4x8`, 96 B GlobalBuffer. It chooses its best EDP
row as an incumbent, reconstructs it, and re-evaluates it on that target. This
incumbent comes from a **previous full search of the same architecture**. Its
acquisition cost is not included in any performance claim; it is a correctness
probe, not a usable search-speed comparison.

A second full run observes the four actual final Join groups. FFM's final Join
adds nonnegative left/right energy and latency fields. For each group the audit
uses conservative downward-rounded sums of the two input minima for each field,
then compares their exact-rational product with the incumbent's reported EDP.
It fails closed for missing, unsupported, nonfinite or negative objectives. This
is a basic **existing FFM partial-cost** bound, not a new dataflow/lifetime bound.
It applies only to the final Join of the two-Einsum workload and best EDP; it
does not preserve the complete Energy–Latency–resource frontier.

A third run experimentally applies the same test: when the lower bound is
*strictly* above the incumbent, it passes an empty left input to the existing
Join pipeline. Thus those original group pairs are not materialized; remaining
groups run normally. The selected final EDP is exactly the same in the reported
floating-point representation and its Mapping re-evaluates successfully.

| Observation | Result |
|---|---:|
| Final Join groups encountered | 4 |
| Groups skipped by the experimental run | 3 |
| Skipped matched pairs with known matching plans | 14 |
| Skipped groups with an unknown matched-pair count | 1 |
| Best EDP | `1.91037424e-16 J s`, unchanged |

One skipped group ultimately had no feasible output in the original run. The
unknown count means 14 is **not** the total number of matched pairs skipped.
The observation path still executes the entire Join and checks retained output
rows against each lower bound; the experimental path is separately run through
FFM. Source [result](real_join_audit.json) includes all four groups and both
validations. We do not claim independent physical verification or full-pair
exhaustion from retained rows alone: safety relies on the documented additive
final-Join semantics and nonnegative inputs. This is a one-architecture probe,
not an architecture-family certificate.

## Synthetic model: one proof for an integer architecture box

[architecture_family_certificate.py](../../architecture_family_certificate.py)
implements a sufficient **two-corner** proof for the restricted synthetic
[graph-cut model](../graph_cut_bound/README.md). In this model a fixed seed's
cost cannot worsen when PE dimensions, capacity or bandwidth increase, and the
branch lower bound cannot increase. Therefore:

```
U_max = cost(feasible seed, box lower corner)
L_min = branch_bound(box upper corner)
U_max <= (1 + epsilon) L_min  =>  prune the branch throughout the box
```

Seed feasibility is checked at the lowest capacity. An infeasible seed returns
`unproven`; an infeasible branch at maximal capacity is reported separately.
All calculations use exact integers and fractions. On the illustrative box
`Px=2..3, Py=4..6, C=32..36, B=2..3`, a single proof makes two corner calls
and covers **60** integer architectures. A separate post-audit enumerates all
60 and every one of four branch completions; all respect the proof. The [raw
result](synthetic_box.json) distinguishes proof work from post-audit work.

The cost model, fixed seed, spill assumptions and monotonicity are synthetic.
The proof does not automatically transfer to FFM, where policy membership,
physical feasibility, copies, sharing, bandwidth costs and Fusion composition
need separate evidence. A box that fails this sufficient condition is simply
unproven, not necessarily unsafe. No FFM architecture region has been certified.

## Regression and reproduction

[regression.txt](regression.txt) records targeted tests including exhaustive
small boxes, randomized monotonicity checks, exact FFM-like float32/float64
addition bounds, invalid and unknown cases, the conditional Copy Witness and
historic Fusion regressions. This is not a full repository test run.

```sh
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
python -m research.tracking_audit.audit_real_join_bound --output /tmp/real-join.json
python -m research.tracking_audit.audit_architecture_family --output /tmp/architecture-box.json
python -m pytest -q --disable-warnings research/tracking_audit/test_real_join_bound.py research/tracking_audit/test_architecture_family_certificate.py research/tracking_audit/test_cross_phase_copy_oracle.py research/tracking_audit/test_fusion_lifetime_ledger.py research/tracking_audit/test_fusion_cut_inspect.py research/tracking_audit/test_graph_cut_bound.py research/tracking_audit/test_permuted_join.py research/tracking_audit/test_fused_reservations.py
```

The open step is to derive an admissible graph-dependent branch bound and a
feasible, policy-appropriate seed over an actual FFM architecture family, and
then evaluate full preprocessing plus end-to-end search against the existing
cache. Neither experiment here establishes that result.
