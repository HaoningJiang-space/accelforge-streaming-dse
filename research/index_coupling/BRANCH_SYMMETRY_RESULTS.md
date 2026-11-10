# Exact branch symmetry depends on the remaining problem and its boundary

Whole-branch permutations remain valid after dependent tails and a symmetric
join are attached. The sufficient quotient must preserve the **joint** branch
state: remaining operators, tensor roles/projections, residency, final-write
ownership and entry contract. Separate counts of those attributes are not
enough. Conversely, asymmetry in an already completed prefix need not prevent
symmetry of the conditional remaining problem.

The argument and bounded study plan are in [BRANCH_SYMMETRY.md](BRANCH_SYMMETRY.md).
This is a small exhaustive reference extending the order-complete Fork work,
not a general-DAG optimizer or a change to any frozen P verdict.

## Family, interface and proof

The family is `X=AB; U_i=X C_i; V_i=U_i D_i`. All numerical extents are two in
the main study. A branch swap must rename E/H and C/U/D/V together. Swapping
only the first consumer fails the full-incidence check. An optional final
elementwise product of all V_i preserves the symmetry under the model's
commutative einsum semantics. It is not a shared multi-writer accumulator.

Relabeling a legal plan under a certified automorphism preserves dependencies,
rank legality, tile choices, sizes, retention capacity, read/write charges and
ownership. The inverse gives equality of attainable cost sets. For one fixed
decorated state, redundant orders are removed by its **stabilizer**; responses
to different states can be reused across the whole state orbit. The oracle
restores both the chosen order and tensor identities in each witness.

Continuation experiments assume EX has finished. A branch has completed zero,
one or two operators. Residency is chosen only among ready private inputs of
the induced remaining graph; X is DRAM-backed if still used. Resident inputs
are pinned throughout this query. Reported C is free capacity after the caller's
reservation, and Q excludes resident-input compulsory loads and prefix costs.
Replay restores a physical retaining frame: `(c,q)` becomes `(A+c,A+2q)`.
This does not establish arbitrary last-use release or optimal prefix/suffix
composition. Progress is encoded by the remaining operator set and tensor
roles; it is not an additional history or time variable.

## Completed census

Seven jobs used source `dea01a89`, Python 3.10.12 on Linux, hash seed zero,
60 seconds including replay, 6 GiB address space and at most four workers.
The literal reference disables both state canonicalization and order-orbit
elimination, using the same unchanged fixed-order solver internally.

| Case | Completed queries → response orbits | Quotient / literal order calls | Exact replays | Wall seconds |
| --- | ---: | ---: | ---: | ---: |
| Two branches, all continuation states | 81 → 45 | 121 / 241 | 241 | 11.04 |
| Two branches + join, all continuation states | 100 → 55 | 131 / 260 | 377 | 26.66 |
| Two branches, root C/D assignments | 16 → 10 | 48 / 96 | 84 | 12.98 |
| Two branches + join, root C/D assignments | 16 → 10 | 48 / 96 | 102 | 32.08 |
| One branch has a tail, asymmetric control | 8 → 8 | 24 / 24 | 33 | 1.45 |
| Three branches, undecorated root | 1 → 1 | 15 / not run | 7 | 50.37 |
| Three branches + join, undecorated root | **incomplete** | 3 completed / not run | 0 | **60.00 timeout** |

All **221 completed literal-reference queries** have exactly equal full
frontiers. Their fixed-order solver calls fall from 717 to 372. The first five
rows include both algorithms and replay, so their times are not speedup ratios.
All **844 saved main-study frontier witnesses** execute exactly.

The three-branch open case exhausts 15 certified representatives of 90 orders;
there is no independent numerical enumeration of all 90 in this budget. The
join case completes no query. Its partial order envelope is not saved as an
optimum and supplies no equality evidence. The scorer retains this timeout
and exits nonzero; six completed jobs are not a seven-job pass.

At a continuation boundary, an unfinished two-op branch has four residency
patterns for C,D; a branch with only H remaining has four for U,D; a completed
branch has one without the join and two for V with the join. Thus there are
nine or ten joint types. The proved orbit counts are

    9^m  → binomial(m+8,8)
    10^m → binomial(m+9,9).

The m=2 counts above match. Unit tests also check the structural m=3 counts
729→165 and 1000→220; those larger continuation curves were not searched.
These are sufficient boundary keys, not all recursive states, minimal physical
states, or runtime bounds. For example, the open two-branch continuation has
45 orbit keys but only 30 distinct numerical frontiers in this sample.

## What separate counts lose

The following negative controls were found in preliminary local diagnostics
and then reproduced by the server census. They are not held-out predictions.

At the full open two-branch root, two private inputs occupy the same 8 B in both
states, and every legal order is allowed:

| Resident inputs | Q at free C=3 | Q at free C=8 |
| --- | ---: | ---: |
| C0,D0: same branch | 64 | 32 |
| C0,D1: different branches | 76 | 28 |

One C and one D is insufficient information. Their association with a branch
matters, and these two curves cross: neither dominates at every capacity.
This does not refute the original theorem for one binary attribute on fully
interchangeable single-op consumers; it identifies the joint type needed when
each branch has more than one private input and dependent computation.

After EX and E0 have completed, the remaining operators are H0,E1,H1. Keeping
D0 gives Q(3)=44, while keeping D1 gives Q(3)=48. Both have one resident D
(4 B) and the same multiset of branch progress. Separate progress/residency
histograms again lose the correlation. Saved component witnesses explain the
difference constructively:

| Component at C=3 | No pinned D | Its D pinned | Traffic saved |
| --- | ---: | ---: | ---: |
| Ready H0 | 20 | 8 | 12 |
| Unstarted E1,H1 | 36 | 28 | 8 |

Two legal group compositions attain 8+36=44 and 20+28=48, matching the complete
suffix oracle. Each component's saved root has a single group, so removing
that annotation preserves the required group entry; arbitrary solve responses
were not substituted. Two additional physical replays attain `(7,92)` and
`(7,100)` exactly. This is post-hoc attribution at C=3, not a general theorem
that independent component frontiers can always be summed under any interface.

## Symmetry can recover after an asymmetric prefix

A separately specified follow-up inserts `Prepare0: Z0=copy(X)` before E0 and
makes E0 read Z0. The original graph then has only the identity in the tested
branch-permutation group. After EX,Prepare0,E0,E1 finish, the remaining H0,H1
graph has a two-element branch group again. Both `{D0}` and `{D1}` suffix
queries return

    [(3,28), (4,24), (7,20)].

Using the original graph's conservative group takes two cache misses and four
order calls; certifying symmetry on the remaining typed graph takes one miss,
one hit and two order calls. Solve entries fall from 460 to 230. All six restored
frontier witnesses replay exactly. This control used source `046c318c`, a fresh
Linux process, seed zero, a 60-second/1-GiB budget, and finished in 0.031 seconds.
Different prefix costs remain charged outside the query. The result does not
equate the two full-graph execution histories.

The appropriate object is therefore the **remaining typed problem with its
boundary contracts**. An automorphism of the original graph is a sufficient
way to establish equivalence, but is unnecessarily restrictive in this example.
Any local equivalence must still preserve extents, residency/ownership, entry,
lifetime and outside order/identity constraints that remain relevant.

## Remaining algorithmic boundary and artifacts

Global branch renaming alone leaves `(2m-1)!!` order orbits for m two-op chains:
3,15,105 at m=2,3,4. These are syntactic classes under that particular action,
not distinct responses or a lower bound on all exact algorithms. The observed
three-branch cost and timeout make exhaustive topological-order enumeration an
unsuitable scaling path. A next exact algorithm should compose remaining-state
orbits during search, proving transition closure and witness reconstruction;
it cannot simply merge progress counts or pick one interleaving per branch
histogram. Shared multi-writer reduction state remains outside this experiment.

Code: `graph/branch_symmetry.py`, `run_branch_symmetry.py`,
`probe_recovered_symmetry.py`, `score_branch_symmetry.py`.
Records: [results/branch_symmetry/](results/branch_symmetry/), including the
manifest, every attempted arm, `score.json`, two component certificates,
recovery control and `validation.json`. Main-study source hashes refer to
`dea01a89`; the follow-up/certificate hashes refer to `046c318c`. The latter
adds rejection of inconsistent tensor declarations; the main graphs already
have consistent declarations. No main-study record was regenerated with it.

Seven unit tests pass. Total exact executions in these records are
**844 main + 2 component constructions + 6 recovery = 852**. Finite replay
checks are distinct from the renaming proof and from general execution
correctness. The ordinary solver, executor, frozen protocol and P21f manifest
are unchanged. No novelty or general polynomial-complexity claim is made.

Recheck with:

```sh
python3 -m unittest research.index_coupling.test_branch_symmetry -q
python3 -m research.index_coupling.score_branch_symmetry research/index_coupling/results/branch_symmetry
python3 -m research.index_coupling.score_branch_symmetry --certificate research/index_coupling/results/branch_symmetry
```

The middle command intentionally returns 1 for the archived incomplete arm.
