# Widths bound local choices, not yet the total exact search

The 34-case study completed 29 curves with 146/146 exact frontier replays;
five searches reached the fixed 60-second limit. Constant cut/obligation widths
did not make residual-chain search linear. The proposed stacks do not have
constant global obligation width; correctly ordered training also has growing
cut width. A separate single-operator control isolates ancestor residency.

Definitions and limits were fixed in [WIDTH_STUDY.md](WIDTH_STUDY.md), source
`ef848f66`, before the 34 searches. All extents are two, exact cut DP is enabled,
historical halving tiles are used, and optional name canonicalization and
independent-operator splitting are disabled. Jobs run in fresh Linux processes,
Python 3.10.12, hash seed 0, with witnesses/profiling, 60 s including replay,
6 GiB address space and at most four workers. The table times are instrumented
single-run observations, not a production-speed claim or an asymptotic fit.

## Fixed widths: residual chains

Here n=depth+2. All cases have w_cut=2, maximum local obligation width 2,
eight possible global extent configurations and maximum observed frontier size
6. Nevertheless both the number of spans and the transitions within them grow.

| Depth, independent H input | Memo entries (solve + group) | DP transitions | Search seconds |
| --- | ---: | ---: | ---: |
| 4 | 776 | 3,405 | 0.0446 |
| 6 | 1,220 | 9,905 | 0.1081 |
| 8 | 1,776 | 22,837 | 0.2343 |
| 12 | 3,224 | 80,541 | 0.7695 |
| 16 | 5,120 | 206,725 | 1.9558 |
| 24 | 10,256 | 826,325 | 7.5803 |

The read-X controls behave similarly: depth 4 has 860 memo entries; depth 24
has 10,700 and takes 8.304 s including replay. These measurements refute the
proposed linear description of this implementation under fixed widths/rank
domains/frontier size. They do not prove a lower bound against a different
algorithm. A DP reduction can turn exponential partition enumeration into
polynomial work without making it linear.

## Growing obligation width: forks

Both all-k and balanced mixed-role forks have w_cut=1, extent-grid upper bound
16, and w_obl=m+1. They have exactly the same memo counts in this small corpus,
despite different curves/frontier sizes.

| Consumers m | w_obl | Memo entries, each role arm | Seconds including replay, all-k / mixed |
| --- | ---: | ---: | ---: |
| 2 | 3 | 626 | 0.0244 / 0.0253 |
| 3 | 4 | 2,147 | 0.1128 / 0.1135 |
| 4 | 5 | 7,585 | 0.5698 / 0.5707 |
| 5 | 6 | 27,956 | 2.9899 / 2.9857 |
| 6 | 7 | 106,604 | 15.2248 / 15.3181 |

This is compatible with severe retention-context growth but is not a fit proving
2^w_obl, nor does the positional-residency counterexample prove that every
subset is necessary. The small extents here differ from the earlier roughly
four-minute P19 shape; their timings should not be interchanged.

## The stacks' global widths grow

The graph builders give each layer boundary its own contraction rank. Equal
numerical dimensions do not make those index variables identical. A legal M
loop over a whole forward stack lacks every layer's two weights (or K/V inputs).
Training executes every forward layer first, then backward layers in reverse
order. Concatenated single-layer forward/backward blocks would violate the
gradient dependencies.

| Graph, L layers | Operators | w_cut | Maximum local w_obl | Extent-grid upper bound |
| --- | ---: | ---: | ---: | ---: |
| FFN forward | 3L | 1 | 2L | 2^(2L+2) |
| Attention core forward | 3L | 1 | 2L | 2^(2L+2) |
| FFN training | 8L | 5L | 4L | 2^(2L+2) |

These structural quantities come from incidence alone; they do not assume the
corresponding searches complete. The extent grid is an upper bound, not the
number of reachable configurations in every span. For these graphs the maximum
unconditioned and conditional-upper obligation widths coincide.

| Family | 1 layer | 2 layers | 4 layers | 8 layers |
| --- | ---: | ---: | ---: | ---: |
| FFN forward, elapsed seconds | 0.0107 | 0.0721 | 5.1158 | timeout, 60 s |
| FFN forward, complete memo entries | 271 | 1,052 | 10,834 | incomplete |
| Attention core, elapsed seconds | 0.0113 | 0.0774 | 5.4441 | timeout, 60 s |
| FFN training, elapsed seconds | 5.7349 | timeout, 60 s | timeout, 60 s | timeout, 60 s |

The two forward families are cost-isomorphic at these uniform sizes and have
identical memo counts. They are not two independent real-model confirmations.
These are serial einsum abstractions: attention has supplied K/V and elementwise
softmax, and FFN retains the existing activation abstraction. No complete
Transformer result or exact linear-scaling training optimizer is established.
Timeout records retain partial counters, which are not completed scaling samples.

## Accumulated obligations: a one-operator control

The separate source `58e0a26c` specifies the following family and exact key-count
prediction **before** its own searches, after examining the 34-case study.
One operator has k ranks v_i of extent two. Input T_i carries all ranks except
v_i; output Y carries every rank. Therefore n=1, w_cut=0, w_obl=1 for every
legal loop. Each rank can be unsliced, sliced with T_i dropped, or sliced with
T_i retained by an ancestor.

Every combination is reachable, so the current solver has exactly 3^k solve
keys. The 2^k fully sliced states stop at solve, leaving 3^k-2^k group keys.
Equivalently, summing over the subset S of sliced ranks gives
sum_S 2^|S| = 3^k. At fixed fully sliced extents alone, 2^k external sets exist.

| k | Predicted and observed solve keys | Predicted and observed group keys | Maximum external-set size |
| --- | ---: | ---: | ---: |
| 1 | 3 | 1 | 1 |
| 2 | 9 | 5 | 2 |
| 3 | 27 | 19 | 3 |
| 4 | 81 | 65 | 4 |
| 5 | 243 | 211 | 5 |
| 6 | 729 | 665 | 6 |
| 7 | 2,187 | 2,059 | 7 |
| 8 | 6,561 | 6,305 | 8 |

All eight predictions match, with 36/36 exact witness replays and maximum
observed frontier size k. Each run uses a fresh Linux process, 60 s and
1 GiB, witnesses and exact DP. The largest completes in 0.569 s. This isolates
why maximum local branching width cannot bound accumulated contexts; even a
2^k extent-grid factor alone omits them. Rank count and tensor volume grow in
this family. These are keys of this implementation, not a proof that all keys
are semantically distinct or that every exact algorithm needs exponential work.

## The justified complexity statement and next target

For **one fixed invocation context**, a cut has at most 2^w_cut residency
labels. A transition p to q chooses labels on B_p union B_q, at most 4^w_cut
combinations. There are up to n(n+1)/2 intervals. Ignoring polynomial incidence
bookkeeping, a conservative bound for the partition work in that invocation is
O(n^2 4^w_cut F log F), with F bounding combined/pruned frontier sizes.
Recursive loop work and child contexts are additional.

Total work must sum over reachable `(span, extents, external, owned, entry)`
contexts. Per-loop work has a local 2^w_obl choice factor, but this does not bound
the number of such contexts. A rank-domain product, ancestor-residency choices,
interval count and frontier size cannot be replaced by one tile-depth scalar.
Repeated output writers also trigger enumeration fallback; a DP-only bound must
state its single-writer assumption.

The useful structural question is now how many **distinct conditional responses**
those reachable contexts induce, and which identities/ordering/ownership facts
permit exact equivalence or dominance. A theorem needs a parameter controlling
the joint rank-and-residency interface, plus a proof of how that parameter
behaves under composition. Counting all existing keys is a diagnostic, not yet
such a theorem. Do not cap fusion spans or remove cuts to manufacture linearity.

## Records and checks

- [34-case records and original manifest](results/width_scaling/), including
  the pre-search structural-only report, five timeouts and source hash.
- [Ancestor control records](results/ancestor_width/), with predicted/observed
  counts, complete witnesses, execution ledgers and source hashes.
- `test_widths.py`: three tests pass, covering structural widths, single-layer
  equality to the existing graph builders and a valid two-layer training order.
- No frozen scientific score, solver default or search grammar changed.
  P21f is separately scored in [P21F_RESULTS.md](P21F_RESULTS.md).
