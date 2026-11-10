# One unresolved obligation: exact certificates, a normal form, and their limits

The scalar "free retention" condition proposed by the user is sufficient for
global conditional optimality in the declared grammar. Its incremental coverage
is nevertheless small. Each old six-consumer census has 150 certified states,
all already covered by Scalar-X Bridge. Ten small root cases have 276 incremental
hits, with 0–0.40% additional response-cache reduction over the existing bridges.

There is also an exact **multi-point** response when only vector X and one
private tensor t remain locally live. It requires three schedule families, not
just Keep/Spill endpoints. This restricted normal form matches 384 conditional
queries against both DP and enumeration, including final-write ownership and
both tile domains. A three-live-tensor counterexample shows why it cannot be
extended merely by counting obligations or operand slots.

These are exploratory derivations and implementation checks, not new frozen
predictions. The default solver, frozen sources and order domain are unchanged.
The audit ran from base `046c318c` with exact hashes of the new working sources.
Evidence: [results/one_obligation/](results/one_obligation/),
[free_retention.py](free_retention.py), [one_obligation.py](one_obligation.py),
[audit_one_obligation.py](audit_one_obligation.py).

## 1. The user's scalar-retention certificate

For fixed span S and caller-resident tensors R, let

    a_o = |access(o) minus R|,
    d(R) = max_o a_o,
    M = {o : a_o = d(R)}.

For a nonresident tensor t,

    d(R) - d(R union {t}) = 1
      iff every o in M accesses t.

Each operator's count either stays unchanged or decreases by one. A bottleneck
that does not access t keeps the maximum unchanged. If every bottleneck accesses
t, those counts become d-1 and all others were already at most d-1; at least one
old bottleneck attains d-1. This proves both directions.

Suppose an unrestricted solve has a legal common loop axis v, with unit tiles
available, and exactly one nonexternal tensor t lacks v. Require:

1. The current slice of t has size one.
2. Every current bottleneck operator accesses t.
3. After retaining t and reducing v to one, a legal child construction attains
   `(d(R union {t}), 0)` internally.

The one-group partition followed by that unit loop attains

    (1 + d(R union {t}), r * 0) = (d(R), 0).

No legal execution uses fewer than d(R) local operand/output cells or has
negative extra traffic. Therefore this is the **entire conditional frontier**,
not just the optimum inside the selected loop. The proof does not compare
the Spill branch: reaching both global lower bounds makes it unnecessary.

The implementation certifies the child with the original scalar leaf, Scalar-X
Bridge, or Streamed Bridge. It never assumes that the scalar leaf attains the
per-operator count; its actual capacity is the count of all live scalar tensors.
It also checks loop legality, including the internal-producer completion rule.

For the supplied `fork(1,2,2,1,'k')`, R={A}, the sole K obligation is U0.
The counts are d=3 and d_after_keep=2; B remains nonscalar in the reduced child,
so Scalar-X Bridge applies. The internal frontier is `(3,0)`. Public conditional
traffic is 7 after compulsory transfers; the complete retaining parent frame
executes at peak 5 and traffic 18. These quantities have different interfaces.

Two negative controls are retained:

- With the same graph and R={A,C0}, EX is also a bottleneck and does not access
  U0. The maximum does not fall, so the certificate is rejected.
- For `fork(1,1,2,1,'kk')`, R={A,U1}, retaining U0 does lower the operand bound,
  but the reduced child hits a larger mandatory scalar leaf. The certificate
  is rejected instead of silently changing the grammar.

## 2. Coverage, overlap, and actual work removed

The census considers unconstrained **multi-operator solve** entries and preserves
the original scalar leaf. It counts legal one-obligation axis candidates and
unique states separately; these counts need not agree. The whole saved censuses
still contain both solve and group entries, including excluded states.

For each old 106,604-entry six-consumer census (all-k and mixed):

| Filter | Count |
| --- | ---: |
| Legal one-obligation axis candidates | 7,689 |
| Scalar obligation, with a one-slot drop | 7,233 |
| Child attains the required bound | 150 |
| Exact match to the saved whole conditional frontier | 150 |
| Already covered by Scalar-X Bridge | 150 |
| Incremental coverage | **0** |

The other 7,083 scalar candidates encounter a scalar child whose total live
count exceeds its per-operator bound. This does not prove that all these parent
states are intrinsically hard: many are already solved by a different existing
certificate. It only rejects this particular construction.

Fresh runs are exploratory, selected to exercise the condition and its failure
boundaries: six added cases and four shapes already used in the Streamed Bridge
study. They are not held-out predictions. All three variants' complete root curves agree; all recorded
certificates match the baseline conditional curves.

| I,J,K,L; roles | Baseline entries | Free-retention states / incremental | Existing-bridge / new cache entries | Existing-bridge / new DP transitions |
| --- | ---: | ---: | ---: | ---: |
| 1,2,4,1; kkkkkk | 3,706 | 21 / 21 | 3,087 / 3,079 | 24,610 / 23,875 |
| 1,2,4,1; kkkiii | 3,706 | 21 / 21 | 3,087 / 3,079 | 24,610 / 23,875 |
| 4,2,1,1; iiiiii | 3,706 | 21 / 21 | 3,087 / 3,079 | 24,610 / 23,875 |
| 1,1,4,2; kkk | 546 | 3 / 3 | 499 / 497 | 1,058 / 1,023 |
| 4,1,1,2; kii | 546 | 3 / 3 | 499 / 497 | 1,058 / 1,023 |
| 1,1,4,1; kkk | 296 | 0 / 0 | 296 / 296 | 707 / 707 |
| 4,2,2,2; kkk | 4,199 | 42 / 21 | 3,741 / 3,730 | 11,885 / 11,749 |
| 4,2,4,2; kki | 8,024 | 63 / 42 | 7,544 / 7,522 | 29,733 / 29,461 |
| 4,2,2,2; kkkk | 15,389 | 96 / 48 | 13,553 / 13,539 | 73,130 / 72,692 |
| 4,2,4,2; kkii | 30,374 | 144 / 96 | 28,499 / 28,471 | 191,351 / 190,475 |

There are 414 certified states in these fresh baselines, 138 overlapping prior
bridges and **276 incremental**. Of the incremental states, 207 have local X
and 69 already have external X; only 20 are on the entire producer span. Child
proofs use Scalar-X Bridge for 69 and the original scalar leaf for 207. Counts
of new hits are not counts of cache entries eliminated: the hit itself remains
cached while some descendant work disappears.

Across the nine nonzero cases, incremental cache savings are 0.098–0.401% and
DP-transition savings 0.458–3.308%. No timing speedup is claimed. These profiled
runs share the machine with regression tests, and all cases are small. Each
census/validation batch has a 25-second cap and a 1-GiB memory cap (sampled peak
RSS, with RLIMIT_AS also on Linux); all completed. The whole audit took about
37 seconds. Old six-consumer root searches were not rerun for timing.

## 3. A complete nonzero-traffic normal form for two locally live tensors

For general size s, the user's fixed-loop recurrence is exact:

    Q_(v,b)(C) = min { r F_keep(C-s),
                       alpha_t*(r-1)*s + r F_spill(C) },    r=e_v/b.

Infeasible child capacities give infinity. This is the response of that
particular whole-span loop choice. The unrestricted response is at most this
value and can improve it through another axis or partition. An equality claim
therefore needs an additional completeness argument, supplied below only for
the stated restricted core.

Now allow t to have size s, but impose a stronger structural condition:

- S is an unrestricted contiguous multi-operator standard-Fork span, in the
  original order; all default exact cost and completion rules apply.
- X is not external and is a vector of length n>1: exactly one of I,K is active.
- The **only** nonexternal tensors are X and a private tensor t lacking that
  active axis v. All other operands/outputs are genuinely caller-resident.
- The other axis h of t is J when t belongs to EX, otherwise L; its extent is s.
- Write ownership W is contained in {X}. The historical halving or all-divisors
  domain is fixed; let B(n), B(s) contain reachable tile extents, including the
  full extent. Both domains are closed under their recursive tile choices.

Let alpha_t=1 for an input t and 2 for an accumulated output t. Let alpha_X=2
when t belongs to EX, and 1 otherwise. Define the boundary coefficient

    beta = 0                      if EX is absent from S;
           2 - 1[X in W]          if EX is present.

Then the exact internal frontier is the Pareto envelope of:

    T:      (s+1, 0),
    X_b:    (b+1, alpha_t * s * (n/b - 1)),              b in B(n),
    T_c:    (c+1, alpha_X * n * (s/c - 1) + beta*n),     c in B(s).

The three families respectively keep all of t; retain one X block and stream
t; or retain one t block and revisit X. If EX is present, the last family must
separate EX from the consumers and materialize X. Its boundary charge includes
one consumer-group read and the producer's final write unless the parent owns
that write. When t belongs to EX, repeated J tiles spill X partial sums, hence
alpha_X=2. Otherwise the consumer group refetches completed X with coefficient 1.

### Attainability

For T, retain t across unit v loops; the child has only scalar X locally live.
For X_b, use outer v tiles b while revisiting t, retain X across singleton
groups within each block, and stream t at unit h tiles in its one operator.
The local peak is b+1. Other operators need at most the already allocated X
plus no local private tensor.

For T_c without EX, use whole-span h tiles c with X refetched, then retain the
t tile across unit v loops. With EX present, cut after EX and send X through
DRAM. The active side uses the same h/v construction; the other side streams
X at unit v tiles and needs only one local cell. All consumer operations use
the same literal L axis, so this construction preserves their fixed order.
The saved witnesses implement these constructions explicitly.

### Why additional partitions and nested loop orders cannot improve them

Only X can cross a partition: t is private to one operator. A partition that
retains X needs at least n+1 local cells at the active operator, and is dominated
by X_n with zero extra traffic. Other groups access only X locally and cannot
reduce the active operator's demand by being split further. Any discarded-X
partition has nonnegative transfers; the cheapest useful separation for h
streaming is the single producer/consumer cut used above.

Follow the active operator through a remaining plan. Only v changes X's size
and only h changes t's size. Loops along other ranks leave both objects invariant;
retaining them cannot beat these zero-traffic constructions, and refetching them
adds nonnegative traffic without reducing local sizes.

If the plan ultimately retains an X tile b, earlier h loops are unnecessary:
after retaining X_b, t can be streamed at unit h tiles without changing capacity.
Removing those h loops removes their X revisit and materialization charges.
Successive v refetches telescope to alpha_t*s*(n/b-1), giving X_b.

If it ultimately retains a t tile c, earlier v refetches can similarly be
removed: X can stream at unit v tiles after t is retained. Successive h
revisits telescope to alpha_X*n*(s/c-1). At c=s the whole-span T construction
avoids any separation. At c<s, an EX-containing span cannot execute the needed
h loop jointly with its consumers: J is not common for a producer obligation,
and L is not common when t is a consumer obligation. Without retained X it must
materialize X, paying at least beta*n. This gives T_c. If v blocking preceded
that separation, its boundary charges sum over blocks to the same beta*n,
and removing the preceding t revisits only lowers traffic.

A path ending at the two-scalar leaf without an explicit retention can instead
retain the last unit tile at the same two-cell peak; the same elimination
applies. Thus every plan is weakly dominated by one of the three attainable
families. The argument uses the two-live condition throughout. It is not a
normal-form theorem for arbitrary one-obligation spans.

### Two explicit four-point curves

For `fork(8,8,1,8,'kk')` with only X,C0 locally live, the exact internal curve is

    ((2,56), (3,24), (5,8), (9,0)).

The intermediate X blocks b=2 and b=4 supply points missed by a unit-loop
Keep/Spill endpoint comparison.

For `fork(8,8,1,8,'ik')` with only X,V0 locally live, it is

    ((2,72), (3,40), (5,16), (9,0)).

At capacity two, revisiting V0 under unit I loops costs 112 extra transfers.
Instead, materializing X costs 16 and refetching it across eight unit L tiles
costs 56, totaling 72. The swapped-loop construction is globally optimal under
the restricted normal form. This is a positive-traffic result, not another
zero-traffic plateau certificate.

## 4. One obligation still does not summarize the general problem

Take `fork(4,4,1,4,'ii')`. In each query below, exactly one tensor lacks the
chosen I axis: output V0, size four, revisit coefficient two. Both have n=4,
s=4, d=2, the same count of local tensors, the same 40-cell external reservation,
and the same 20 compulsory transfers. The additional local tensor is an input
of size 16 in both cases.

| Locally live tensors | Exact internal frontier |
| --- | --- |
| X,V0,A | `((2,20),(3,8),(5,0))` |
| X,V0,D1 | `((2,24),(3,8),(5,0))` |

A carries I,J; D1 carries L,I. Both vary along I, so neither is an I obligation.
They interact differently with the alternative L schedule and the cut after
EX. Consequently the same single-axis obligation summary does not determine
the complete response. The full framed executions have the same peak 42 at
the first point but traffic 156 versus 164, exactly reproducing the difference.

This refutes a response depending only on n,s,alpha_t,d and external footprint.
It does not refute either sufficient theorem above. It shows why "one remaining
obligation" is relative to a selected axis and does not imply one remaining
resource conflict across all alternative mappings.

## 5. Validation scope and reproduction

- 714 free-retention census matches: 300 old plus 414 fresh; no mismatches.
- 83 conditional free-retention cases, each checked by both partition solvers
  and executed inside a real retaining parent frame.
- 207 two-live census matches in the four larger-X census roots; none in the
  two old tiny-six roots. This formula is not installed as a solver shortcut.
- 384 two-live conditional queries, each compared with DP and enumeration
  (768 oracle calls); 720 complete framed executions, including 272 with a
  caller that owns X's final write and later consumes it. Input/output roles,
  producer inclusion, non-power-of-two dimensions and both tile domains vary.
- Six exact negative-control executions and 141 exact fresh-root executions.
- All 25 combined regression tests pass. Repeated executions/oracle calls
  are counts of checks, not assertions of distinct physical schedules.

```sh
python -m unittest research.index_coupling.test_free_retention \
  research.index_coupling.test_one_obligation \
  research.index_coupling.test_streamed_bridge research.index_coupling.test_scalar_bridge \
  research.index_coupling.test_residency_states research.index_coupling.test_p21f
PYTHONHASHSEED=0 python -m research.index_coupling.audit_one_obligation \
  --out /tmp/one-obligation-audit --seconds 25
```

The optional wrapper checks the original scalar leaf and both existing bridges
before free retention. It never changes cache keys or production defaults.
The two-live module returns analytic candidates and reconstructs their witnesses;
it does not call a mapping solver to obtain the formula. Its validation does
use the unchanged solver as an independent recurrence reference.
