# One conditional resource contract, three composable exact reductions

The first joint experiment passes within its declared serial grammar. On a
six-operator family with a distinguished downstream branch and a reconvergent
product join, cut DP, a certified symmetry quotient and a local lower-bound
certificate preserve every root frontier and every compared internal response.
The certificate handles a subgraph containing both F and Join and appears inside
executed optimal whole-graph witnesses. This is more than three switches on
unrelated test graphs. It remains a restricted reference architecture: global
order representatives are enumerated, not dynamically quotiented at every state.

## Contract and local theorem

The fixed [protocol](UNIFIED_SEARCH_PROTOCOL.md) specifies

    X=AB; U_i=X C_i (i=0,1,2); V0=U0*D0; Y=V0*U1*U2.

The last two ops are elementwise products, not shared multi-writer reductions.
E1/E2 are interchangeable with their private tensors; F distinguishes E0.
Typed-incidence checking tests 36 maps and certifies a two-element group.
There are 12 global topological orders and six undecorated order orbits.

Every arm searches the SAME union of fixed-order grammars: one global order per
plan, serial execution, no recomputation, halving tiles, ordinary read/write
charges, exact Pareto pruning and the original mandatory scalar leaf. Keys
include solve/group entry, extents, residency and write ownership. Internal
responses exclude caller reservations and compulsory transfers; the root adds
its compulsory traffic once. Production `curve.py` and the executor are unchanged.

The old Scalar Bridge required the whole graph to be a standard Fork. The new
graph-local sufficient condition is:

- H consists of the nonexternal tensors used by multiple operators of the span;
  every member of H is scalar at the current extents.
- For each singleton op, all remaining private tensors carry every active rank
  used by any of them. Unit streams introduce no private refetch or spill.
- Retain H over first-to-last-use intervals. If the resulting maximum singleton
  peak equals the operand-slot lower bound d, this realizes both C=d and extra Q=0.

The complete internal response is then {(d,0)}. A larger constructed peak,
nonscalar shared object or unsupported private stream is rejected and ordinary
search continues. The mandatory scalar leaf retains precedence. Local outputs
need not be terminal in the original graph: their caller-owned boundary writes
are preserved. The predicate is sufficient, not a complete recognizer.

Joint correctness is conditional substitution. Max of adjusted peaks, sums of
traffic and positive trip multiplication preserve dominance. Thus exact child
responses can replace searches under the same boundary. The quotient maps legal
decisions and costs under certified renamings. Cut DP retains a Pareto set of
PREFIX costs at each boundary; equal continuation keys do not erase prefix cost.

## Complete census and coverage

Source `b6e2ddbc` was committed before remote measurement. Three shapes and all
eight D/Q/C configurations ran in fresh Linux/Python 3.10.12 processes, seed
zero, 180 seconds and 6 GiB per arm, with at most four workers. D enables cut DP,
Q the query/order quotient, and C the local certificate.

All **24/24 arms complete**. Every root frontier matches 000, and **1,018,272
optimized internal response records match** their literal-order baseline
records, with zero missing contexts or mismatches. This includes repeated states
across arms, not a million unique physical states. All **144 census frontier
replays** are exact. Reference 000 uses all orders and partition masks with no
reductions; it shares the accounting recurrence. Executor replay is the separate
physical check, not a second name for numerical equality.

| Shape I,J,K,L | Baseline response entries | All-on entries | Baseline certificate-eligible states | All-on certificate hits |
| --- | ---: | ---: | ---: | ---: |
| skinny 1,2,1,2 | 3,372 | 1,686 | 0 | 0 |
| core 2,2,2,2 | 90,496 | 40,472 | 10,078 | 5,039 |
| rectangle 2,3,2,4 | 122,408 | 55,462 | 11,902 | 5,951 |

Entry counts sum solve/group caches across order-specific kernel instances.
Equal numerical responses and additional equivalent keys can remain; these
counts are neither a minimal-state measure nor a general quotient-size bound.

Independently applying the certificate predicate to baseline states gives
**21,980/21,980 equal responses**. Each nondegenerate shape includes 548 eligible
order-specific states containing Join and 1,370 containing F (overlapping
categories). H ranges from one to four scalars, so coverage is not restricted
to an embedded terminal Fork.

The skinny case is a negative result. A Fork-shaped local solve can be certified
in isolation, but the root never reaches such a nonscalar solve: group-entry
restrictions and the mandatory scalar leaf matter. C has zero hits there.

## What each rule eliminates

Full core ablation, in D/Q/C bit order:

| DQC | Response entries | Partition choices | Cut-DP transitions | Loop choices | Certificate hits |
| --- | ---: | ---: | ---: | ---: | ---: |
| 000 | 90,496 | 900,988 | 0 | 85,198 | 0 |
| 001 | 80,944 | 767,562 | 0 | 81,550 | 10,078 |
| 010 | 45,248 | 450,494 | 0 | 42,599 | 0 |
| 011 | 40,472 | 383,781 | 0 | 40,775 | 5,039 |
| 100 | 90,496 | 0 | 776,110 | 85,198 | 0 |
| 101 | 80,944 | 0 | 611,668 | 81,550 | 10,078 |
| 110 | 45,248 | 0 | 388,055 | 42,599 | 0 |
| 111 | 40,472 | 0 | 305,834 | 40,775 | 5,039 |

Partition choices and DP transitions are different units, not interchangeable
counts of physical schedules. D preserves the response keys here while sharing
prefix combination work: at Q=C=0, Pareto candidates fall from 4,782,398 to
2,920,612. Q halves the order family and response entries. C reduces response
entries another 10.56% on core and 9.38% on rectangle, at either Q setting.
At D=1,Q=0 it reduces DP transitions by 21.19%/18.07%. These effects come from
the factorial comparison; their speedups are not added.

In all-on censuses, certificate predicates cost 0.218/0.302 seconds, while
symmetry detection plus order canonicalization costs below 0.001 s per shape.
These tiny-group measurements are not general complexity bounds.

## An executed joint witness containing F and Join

A reached core state has order E0,E1,F,E2,Join, extents I=1,J=1,K=2,L=1,
caller-resident X, and empty W. The certificate keeps H={U0,U1,U2,V0}.
Its operand-slot counts are [2,2,3,2,4], so d=4. Charging H over its actual
intervals gives singleton peaks [2,3,4,4,4], whose maximum is also four.
Consumers stream K with their scalar outputs retained; F and Join use scalar
singleton leaves. Extra traffic is zero, attaining both lower bounds.

The saved ancestry contains cut-DP calls inside a symmetry order representative.
This certificate is selected in root points **(6,44)** and **(8,40)**, both
executed exactly. Two other selected certificates cover E1,E2,Join and E2,Join.
Rectangle selects all three kinds too. Provenance tags are stripped before
execution: the executor receives ordinary group/loop notes. This is the requested
quotient → decomposition → certificate → executable whole-plan chain.

## Sequential controls and limits

After the censuses finished, 12 fresh-process controls ran sequentially without
census writing or profiling. Three repetitions per 000/111 and shape alternate
arm order. Every curve matches, with **84 more exact replays**. The interval
includes validation, symmetry detection, kernel construction and search, but
excludes Python imports and final replay.

| Shape | Baseline median seconds | All-on median seconds | Ratio of medians |
| --- | ---: | ---: | ---: |
| core | 15.598 | 3.293 | 4.74x |
| rectangle | 19.656 | 4.533 | 4.34x |

Total: **228 exact server replays**; seven local contract tests pass. No formal
arm is incomplete. The protocol discloses the prior combined local smoke-test
alarm, which is not a per-arm timing measurement.

Memory does not improve: profiled baseline/all-on RSS is 35.9/45.8 MiB on core
and 44.2/53.9 MiB on rectangle. This implementation stores certificate ancestry
and witness provenance, but no ablation isolates their causal share of memory.
Fewer response entries do not imply a smaller process peak.

The structural result is the **local scalar shared set plus interval-peak
certificate**, including a reconvergent subgraph. The recursive equation is a
correctness organization, not itself a novelty claim. Q currently quotients
whole-query states/orders only. Dynamic state transitions, automatic separators
and parameterized bounds for arbitrary graphs remain unproved.

## Artifacts and next proof obligation

Code: `unified_search.py`, `run_unified_search.py`, `score_unified_search.py`,
`test_unified_search.py`. [results/unified_search/](results/unified_search/) holds
every arm, compressed state census, source hashes, timing and validation. The
analyzer was added after the frozen run; its hash is recorded separately.

```sh
python3 -m unittest research.index_coupling.test_unified_search -q
python3 -m research.index_coupling.score_unified_search research/index_coupling/results/unified_search/census --timing research/index_coupling/results/unified_search/timing --out /tmp/unified-score.json
```

Next prove transition closure for a dynamic remaining-state quotient while
preserving the same grammar and one consistent global order. Bound joint
membership, extent, residency and ownership contexts, and use these complete
censuses as regression oracles. This study introduces no separate overlap,
heuristic-cut or additional optimization branch.
