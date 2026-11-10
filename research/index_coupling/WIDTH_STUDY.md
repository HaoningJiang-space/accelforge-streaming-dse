# Width hypothesis: definitions and a bounded test plan

The proposed product `n * 2^w_cut * 2^w_obl * tile_levels * frontier_size` is a
hypothesis, not a complexity theorem. This study keeps the exact serial grammar
and all cuts; it adds no cut heuristic or approximation. It does not change P21f.

## Distinct quantities

- **Cut width:** maximum number of tensors touched on both sides of a boundary.
  For fixed extents, external tensors and ownership, it bounds the keep/DRAM
  labels at that cut. It does not count all recursive invocation contexts.
- **Local obligation width:** number of nonexternal tensors lacking one legal
  loop rank, in one group invocation. This bounds that invocation's retention
  alternatives, not the accumulated external set across multiple ancestors.
- **Extent configurations:** tile choices for independent rank variables form
  a product of domains, not one global recursion-depth factor. Projection removes
  unused ranks locally but need not bound a growing span's number of ranks.
- **Frontier size and number of spans:** neither is automatically constant.

For one cut-DP invocation, states at p have at most `2^|B_p|` residency labels.
A transition p→q also chooses new labels in `B_q \ B_p`. Thus that pair can
attempt `2^|B_p union B_q|` combinations, at most `4^w_cut`. The implementation
considers up to n(n+1)/2 candidate intervals. Suppressing polynomial bookkeeping,
a conservative per-invocation bound is `O(n^2 * 4^w_cut * F log F)`, where F
bounds the frontiers being combined and pruned; recursive child search is not
included. Total work sums over reachable `(span, extents, external, owned, entry)`
contexts. A maximum branching width alone does not bound that context count.
This is an implementation bound, not a lower bound for every possible algorithm.

The positional-residency counterexample only refutes count-only merging. It
does not prove that all 2^w_obl subsets are semantically distinct or unavoidable.

## Stacks need global definitions

Equal numerical feature sizes do not identify distinct contraction ranks across
layers. `graph/stacks.py` uses boundary ranks D0...DL and private hidden ranks.

Forward FFN/attention-core chains have cut width one, but a legal M loop over
the entire stack lacks two weights or K/V inputs per layer. Thus their whole-
span obligation width is at least 2L. These are the existing graph abstractions;
attention uses supplied K/V and elementwise softmax, not a complete Transformer.

Training FFNs execute all forwards then reverse-layer backwards, preserving
gradient dependencies. At the forward/backward boundary, each layer has five
crossing tensors: its input activation, H, Z, W1 and W2. The cut width is 5L,
and the legal global M loop has 4L obligations, including weight gradients.
Concatenating complete single-layer forward/backward blocks would use gradients
before they are produced and is not an equivalent training graph.

## Measurements fixed before solver runs

All numerical extents are two. Cases: all-k and balanced-mixed forks with
2...6 consumers; residuals of depths 4,6,8,12,16,24 with/without X reads; and
forward FFN, training FFN and attention-core stacks of 1,2,4,8 layers. There are
34 jobs. Each uses a fresh Linux process, hash seed 0, exact DP, witnesses,
profiling, historical halving tiles, and no optional name reuse/independence
shortcuts. Limits: 60 seconds including replay, 6 GiB address space, at most
four jobs at once. Timings are instrumented; incomplete counts are lower bounds
on observed work, not completed scaling samples.

`graph/widths.py` reports root legal obligations, the maximum across spans with
no external tensors, and a conditional upper bound allowing all blocking internal
tensors to be external. The last is an upper bound over interfaces, not a claim
that every maximizing interface is reachable. It also reports all cut tensors
and the Cartesian upper bound on rank-extent configurations. These structural
calculations call no solver. Existing runtime stats supply cache counts, spans,
external-set cardinalities, DP transitions, loop choices and frontier maxima.

Questions: do residual state counts remain constant per operator with fixed
widths and rank domains? Do the actual stack definitions satisfy the assumed
constant widths? Which dimensions of context grow when counts do not follow
the proposed product? No fit or timeout will be promoted into a structural proof.
