# Two contractions: close the conditional interfaces before composing

The root normal form in CONTRACTION_ORACLE.md §8 is already derived and tested.
During this independent derivation, the main branch also added conditional
segments and chain-DP predictions. The present task is direct verification of
the full conditional response and the difference between solve/group entries,
not a claim to have independently discovered a new root formula.

## 1. Contract

    h[j] = sum_i x[i] W0[i,j],  z[k] = sum_j h[j] W1[j,k].

The three distinct ranks have positive extents a,b,c. Both weights are
caller-resident. Flags p,q declare whether the whole input x and whole output
z are also caller-resident. Their reservation and compulsory transfers are
excluded from the response. h is not external; it has one producer and one
consumer. No caller owns a write of h. Extra traffic is above the compulsory
reads of nonexternal x and writes of nonexternal z.

Use v2, serial execution, no recomputation, fixed operator order, whole-tensor
keep/refetch at each loop, pinned caller reservations, default read cost 1 and
partial-sum spill cost 2. Halving and all-divisors domains retain their exact
recursive reachable sets R(n). There are no pointwise operators, aliases,
root-cut constraints, approximation grid, capacity truncation or DMA overlap.
This is a grammar response, not the optimum over arbitrary physical schedules.

## 2. Single-contraction conditional response

Write F_pq(a,b;C) for the single-contraction extra traffic with the same endpoint
flags. With neither endpoint resident it is the previously proved f(a,b;C).
With one endpoint resident it is zero for C>=1 and infeasible below 1. With
both resident it is zero for C>=0. The single remaining live vector can be
streamed one element at a time; all reduction obligations are caller-resident
or occupy that one scalar slot.

## 3. Solve-entry formula

Let G_pq(a,b,c;C) be the two-contraction solve response. One candidate
materializes h:

    D_pq(C) = 2b + F_p0(a,b;C) + F_0q(b,c;C).

For u in R(b), choose kx>=p and kz>=q, each Boolean. These flags say which
endpoints are resident inside the common-j loop. Define

    A = (kx-p)a + (kz-q)c,
    P = A + u + max(1-kx,1-kz),
    Q = [(1-kx)a + 2(1-kz)c] (b/u-1).

Then

    G_pq(C) = min( D_pq(C), min_{u,kx,kz : P<=C} Q ).

Each family keeps the h tile across the operator split. Each singleton needs
one additional free endpoint cell unless both endpoints are resident. The
max of the two singleton needs gives max(1-kx,1-kz), not their sum. u=b
includes the root partition holding all h; extra endpoint reservations at
u=b are dominated by that simpler partition. A proper recursively reachable
u may require several j loops to realize, with the same aggregate cost.

For p=q=0 the formula is the five familiar choices: materialize h, keep only
the h tile, additionally keep x, additionally keep z, or keep both endpoints.
For p=1,q=0 it reduces to

    min(2b+f(b,c;C),
        min_{u in R(b),u+1<=C} 2c(b/u-1),
        0 if C>=c+1).

The p=0,q=1 expression replaces the first f with f(a,b), the loop coefficient
with a, and the last threshold with a+1. G_11 is zero for C>=1.

## 4. Why nested loops do not add another family

Induct simultaneously over b and endpoint flags, using the already-established
single-contraction normal form. A root partition either keeps h, with peak
b+max(1-p,1-q) and zero extra traffic, or materializes h at D_pq. The only
common active rank of a nonscalar two-op group is j.

Consider an outer j loop with tile u, r=b/u, and additional endpoint retention.
There are two cases for the inner normal form.

**It keeps an h tile v.** An endpoint retained only at an inner j level can be
retained at the outer j level without increasing its size: x and z carry no j.
Within this normal form they have no earlier-release materialization phase.
Their reservation at the peak is unchanged, and the outer repeated-read/spill
charges only disappear. For an endpoint never retained, charges telescope:

    w(r-1) + r w(u/v-1) = w(b/v-1),   w=a or 2c.

Since v is recursively reachable from b, this is one of the stated families.
Different retention levels therefore do not improve it.

**It materializes h.** Project the resulting plan onto each contraction,
including its inherited endpoint reservations and j loops. Each projection
is a legal single-contraction plan using no more than C free cells. Their
repeat charges partition into the x-read and z-partial-sum terms. The total
h traffic is r(2u)=2b. Executing the two projected plans sequentially, with h
in DRAM, cannot increase peak storage. Minimizing each projection gives D_pq,
which is no worse. This case must be handled separately: hoisting endpoint
reservations across a materialization phase is not generally capacity-free.

The scalar base is v2's partitionable leaf. In particular, a=b=c=1 with no
endpoint resident has zero extra traffic at C=2, not v1's mandatory whole-leaf
capacity 3. With both endpoints resident, only h needs one cell. The families
above give exactly these base cases. All candidates are attainable or dominated
by an attainable candidate, completing the normal-form argument.

## 5. Group entry is a different response

A reusable group response cannot take a root operator partition. Let H_pq be
that response. If b=1 and every nonresident endpoint is scalar, v2 redirects
the all-scalar group to solve, so H_pq=G_pq. Otherwise,

    H_pq(C) = min over proper FIRST tiles u admitted at b, kx>=p,kz>=q of
      [(1-kx)a+2(1-kz)c](b/u-1)
        + (b/u) G_kx,kz(a,u,c; C-(kx-p)a-(kz-q)c).

An empty minimum is infeasible. This is a finite formula using G, with no
recursive search. It uses directly admitted proper first tiles, not u=b or
all recursively reachable tiles indiscriminately.

Two paper controls make the distinction concrete:

- a=8,b=2,c=8, p=q=0: at C=3, G=0 (keep h whole), but H=24.
- b=1 with a nonscalar nonresident endpoint: H is infeasible at every C,
  although G is feasible by splitting the operators. There is no common
  active loop rank. The all-scalar v2 exception must not be missed.

The existing `chain2_closed_form.pair` families include u=b and omit the
materialize-h alternative. They are a set of attainable solve-side candidates
whose missing alternative can be represented by the outer chain DP. They are
not a complete group response and must not replace the group cache directly.

## 6. Frozen direct-interface check

Before computing any new reference curve for these cases, commit this file,
the pure predictor, freeze script and generated predictions. Existing root
and long-chain studies, the single-contraction formula, and the two paper
controls above are disclosed prior knowledge. This is a prospective direct
interface check, not a new novelty claim or re-scoring of those studies.

- Shapes: (1,1,1), (1,6,4), (6,1,5), (4,6,1), (3,6,5), (4,9,2),
  (6,10,3), (5,12,4), (8,6,9), (2,15,7), (7,8,3), (12,15,8), (8,2,8).
- All four endpoint-residency contexts, both tile domains and both entries:
  208 full response cases. Every integer C from 0 through max(4,a+b+c+1).
- Infeasibility is JSON null, never zero. Count finite positive traffic,
  zero-traffic and infeasible cases separately; report context/entry strata.
- Prediction: every point and every full frontier equals unmodified v2
  `curve`. Compare literal partition enumeration and cut DP as an additional
  implementation control. Preserve all failures; do not refit this prediction.
- Replay every finite frontier witness inside an explicit caller frame,
  including external inputs/outputs and their weight reservations. For a
  nonscalar group witness, add the legal singleton-group solve wrapper in the
  parent frame; scalar redirected groups already have solve-form witnesses.
- Local standard-library runs, 30 seconds per response case including checks
  and replay. Save source/protocol/prediction hashes, raw curves, witnesses,
  measured counters and failures. No speedup or hardware-quality claim.

All finite cases reach their zero-extra plateau within the stated capacity
range; a nonscalar group with b=1 stays infeasible forever. Thus comparing
the breakpoint lists also checks the entire integer-capacity domain.
