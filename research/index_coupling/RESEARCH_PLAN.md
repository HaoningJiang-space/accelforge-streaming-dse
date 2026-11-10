# Research plan: a memory-demand invariant of computation graphs

Status: plan, agreed 2026-11-09. Predictions named here are drafts until written into
PROTOCOL.md before their runs. See STATUS.md for the ledger and FIRST_PRINCIPLES.md for
the derivations.

## Question

What is the least information about a computation graph that determines its
capacity-traffic curve S_G(q)? A secondary question is how compact that
information is at a cut, so that summaries of subgraphs compose.

Operationally, seek a computable sufficient invariant within a declared class
of representations and execution grammar Gamma:

    S_(G,Gamma)(q) = min { P(m) : m in Gamma(G), Q(m) <= q }.

Here q is total traffic. The existing inverse-curve helpers instead use excess
traffic over each curve's plateau; retain that baseline explicitly when
comparing physical traffic budgets. Gamma includes legal orders, tile domains,
precision, retention and recomputation rules. No globally minimal description
or unrestricted-mapping optimum has been established.

For fixed grammar and options, the curve is, by construction, a function of three
things: tensor sizes, the incidence between einsums and ranks, and the role of
each tensor (input, intermediate, accumulated output). Saying "the graph
determines the curve" is therefore empty. The content lies in which parts of
that description can be dropped without changing the curve:

- P17. With spill cost 1, swapping private terminal inputs and accumulated
  outputs in the studied fork preserves the curve. This does not remove
  producer/consumer roles or reduction-completion constraints in general DAGs.
- P18e. Exchanging I and K together with flipping every role preserves the curve.
- For homogeneous forks with all legal consumer orders, equal (#k,#i) is a
  renaming symmetry. At I=K and fixed m, role classes reduce to b=min(#k,#i).
  P18/P19 test additional quantitative claims about the maximum gap; symmetry
  alone neither computes the curve nor predicts that gap.

Direct related work includes red-blue pebbling (Hong-Kung), IOLB/IOOpt, SOAP
and HBL. Do not presume these ignore read/write accounting or memory-size
parameters: the [IOOpt interface](https://iocomplexity.corse.inria.fr/ioub)
records read/write occurrences, and [SOAP](https://htor.spcl.ethz.ch/publications/index.php?pub=418)
handles multiple statements and input/output reuse. The literature check in
FIRST_PRINCIPLES.md §5 must establish a specific distinction for the present
comparative role/retention results before any novelty claim.

## Why this is the composable summary

For a fixed serial interface, sibling groups compose after the caller charges
cross-group residency: P=max_g(A_g+p_g), Q=Q_boundary+sum_g(q_g).
`combine_max_sum` receives these adjusted peaks, not raw local capacities.
The interface fixes which tensors stay live, their roles, slice extents and
execution entry/partition. The projected cache key (`7b891c7c`) is sufficient
for the inspected recurrence with callers charging ancestor reservations.
It reduced one four-consumer control from 568,721 to 37,710 total memo entries;
the default solver also preserves all 475 archived comparisons. This is not
a count of boundary states at one cut or a proof of a minimal quotient.

So "how compact can a demand summary be" becomes a measurable question: how many
distinct interface states are there, and how coarse can they be while staying
exact? Count signatures per fixed cut and context domain, frontier size per
signature, and total memo/construction work separately. P17 shows that a graph
signature forgetting the terminal-role distinction without otherwise encoding
its effects is insufficient at spill cost 2 (95/95 differing curves).

## Why it is architecture-mapping co-optimization

S_(G,Gamma)(q) describes memory demand under its fixed hardware/execution
assumptions. Bandwidth gives an affordable traffic budget only together with a
time objective and compute/overlap model. If actual curve breakpoints or useful
bounds follow cheaply from graph structure, architecture queries can reuse
them without repeating mapping search. P19's n·min(ceil(b/2)·L,n/2) is a
maximum capacity-gap conjecture, not a breakpoint-location formula. PE shape,
banking or precision changes may require a different Gamma and cost model.

## Steps

1. **Close the open tests.** These decide whether the next steps build on the
   first-split account or on multi-level retention scopes.
   - P19 (done): the first-split knapsack predicts the maximum gap exactly
     (P19a, b pass) but not the width of the positive range (P19c fails, 0/8).
     All eight b=2/b=3 curve pairs cross. Peak, positive-range width and
     interval-weighted averages must remain separate (FIRST_PRINCIPLES.md §9);
     none is a replacement success criterion for P19c.
   - P14-FFN′ equality failed (26 lower points, plus the known 1 B offset).
     Classify remaining differences using executed witnesses and native source
     reconstruction; do not infer a unique mechanism from numerical agreement.
     Two source rows now reconstruct under legal independent-copy reordering
     and reproduce native costs. The 80 B comparison isolates 128 B less input
     refetch with equal aggregate partial-sum overhead. Both outer-axis
     obligation tables tie; the additional cost is in the child execution.
     This does not yet distinguish mapspace exclusion from pruning.
   - An integer-tile retest of dS, since the power-of-two grid is a known
     artifact source.
2. **P20, the minimal invariant (to be frozen after P19).** Use graph pairs with
   equal sizes, operator count and MAC count. State in advance which pairs have
   identical curves and which differ. Candidates:
   - *Order.* After order completion (Pareto union over legal orders, with
     tensor identities preserved), a fork's curve depends on roles only through
     (#k, #i). This is already proved by renaming for homogeneous independent
     consumers (P18_STRUCTURAL_INTERPRETATION.md §3); test it as a regression.
   - *Role count.* Test quantitative differences between different b classes.
     Equal-b placement is covered by symmetry only at fixed m, I=K and the
     stated homogeneous, order-completed grammar.
   - *A non-fork family.* Diamonds or GLU, where a join meets the shared tensor,
     to see whether the fork invariant survives a reconvergent path.
   **Selection discipline after P19:** compare complete conditional curves,
   not only maxima. Fix the cut, tile extents and legal order domain before
   testing an interface reduction; then separately measure the envelope over
   cut alternatives. Preserve physical-copy residency episodes or show why
   their effects can be discarded. Equal first-layer obligation costs do not
   establish equal child costs. This is a requirement for a future frozen
   test, not a new P20 prediction or an implemented search algorithm.
3. **P21: retain/spill and interface-state measurement.** Start with the frozen
   residual-block tests in PROTOCOL.md, independently of P19: P21a excludes X
   from H and tests the capacity-shift identity; P21b lets H read X and tests
   whether a conditional residency/granularity interface repairs the coarse
   curve. Distinguish the fixed partition from unrestricted fusion, include
   producer/join feasibility, and report ties in the 2s inequality. Then, on
   workload cuts (the modeled FFN forward/backward
   boundary, the attention score/value boundary), count projected interface
   states against complete mappings. The current FFN alias/lifetime and
   attention elementwise-softmax abstractions must be explicit. Then test coarser interfaces: role-blind,
   slice-blind, lifetime-blind. Each must reproduce the same final Pareto
   frontier, or the failure is reported. This reuses graph/curve.py. No new
   oracle is needed for the current grammar. A streaming oracle outside the
   grammar is a later extension.
   **P21 outcome:** all 56 feasible interface queries compose exactly; all
   eight read-X full cases refute the capacity-only interface. These include
   repeated tile queries (40 distinct feasible interfaces). Unrestricted
   curves differ in all 16 full cases: preserve partition/entry, extents and
   residency before claiming a whole-graph summary. See P21_RESULTS.md.
   **Exploratory follow-up:** five chosen bottom-cut families recover the 16
   seen curves, with 560 exact witness replays. The final family was selected
   from misses. A conditional tail distinguishes `group` from `solve` entry,
   and an input needed only at entry from one pinned through the whole span.
   See P21_CUT_ANALYSIS.md.
   **P21d, frozen and tested:** the whole-prefix/suffix rank-change plus
   last-crossing-use cut rule fails on four independently replayed cases;
   two cases have equal curves, two have inherited duplicate final-write
   charges, and four depth-12 cases time out at the frozen 600-second limit.
   A cut pair can expose a useful local rank even without a whole-prefix/
   suffix event at both endpoints. This tests that generator, not the
   sufficiency of lifecycle labels. First repair unique final-store ownership
   in recursive accounting and its cache state; then freeze a separate
   contract test. Repricing saved witnesses is not a solver repair. Do not
   add cut families to rescue this score. See P21D_RESULTS.md.
   **P21e / P21f outcomes:** P21e's existence prediction passed 16/16,
   but full-curve equality and the original plateau prediction each failed
   13/16. Keeping the independent d row suggested a post-hoc plateau
   candidate L>2K without X reads, versus L>K with X reads.
   Frozen P21f now fails the plateau prediction: independent-between is 7/8,
   the other three strata are 8/8; each required 8/8. Existence passes 32/32.
   All 140 arms complete with 1,919 exact replays. The (6,4,6), independent-H
   counterexample has plateaus 61/62 B: both peaks already reserve H1, so the
   incremental free cost is D plus scalar H0, not two new K rows. This is
   attribution, not a replacement threshold. The 16 new and three seen tile
   diagnostics remain separate from the primary score. See P21F_RESULTS.md.
   **Width study:** 29/34 curves complete with exact replays; five searches
   time out at 60 s. Fixed-width residuals are not linear in this DP; global
   obligations grow as 2L in forward stacks, and valid FFN training has cut
   width 5L. A one-op control has local obligation width one but 3^k solve
   contexts. The next theorem must bound or quotient joint ancestor residency
   and rank/extent contexts, in addition to local branching and interval work.
   See WIDTH_RESULTS.md. Do not reintroduce cut heuristics or cap fusion spans
   to obtain an apparent linear scaling result.
   **Conditional-state census:** the complete tiny six-consumer same/mixed
   audits record 106,604 states each. The independent-solve theorem covers
   7.4% of the four dominant buckets; in producer-containing whole spans,
   X cannot become external because all whole-span loops are over I or K,
   both carried by X. The next structural target is equivalence or dominance
   in those coupled states, preserving producer-prefix partition behavior
   and parent reservation/spill costs. Count histograms alone fail in 90/171
   coupled classes. See RESIDENCY_STATE_AUDIT.md; no compression is enabled.
   **Scalar-X progress:** when I=K=1, X is not external, and the original
   whole-span scalar leaf does not apply, an unrestricted solve has internal
   frontier `(max_o |access(o) minus R|, 0)`. Retaining one X cell and streaming
   each singleton operator attains both lower bounds. The opt-in prototype
   matches 29,067 recorded states per tiny six-consumer case and removes 81.3%
   of DP transitions there. Parent alternatives reduce to cost pairs
   `(reservation + child_capacity, parent_extra_traffic)`, giving an exact
   local dominance condition. A non-scalar extension now applies when all
   missing-axis obligations are already externally resident and the reduced
   solve attains that bound; it matches 565 conditional states but yields only
   0.27–0.55% additional cache reduction in four small cases. The original
   scalar leaf supplies a concrete exclusion. Next target one unresolved
   obligation with a matching lower bound, not just a constructive upper bound.
   General larger-X states and outer mask enumeration remain open; see
   STREAMED_BRIDGE_RESULTS.md and SCALAR_BRIDGE_RESULTS.md before generalizing.
   **Order-complete symmetry quotient:** an independent Fork solver now searches
   group membership by role/joint-residency counts and restores a consistent
   global consumer order. Five complete reference envelopes and all 128 tiny
   conditional queries match; 685 saved executions across two studies are
   exact. Its three response caches admit the bound
   `96 D binomial(a+4,4) binomial(b+4,4)`, including ancestor residency, for
   fixed four-rank Fork shape domains. The positional counterexample remains
   valid in the old grammar and collapses in the order-complete one. Next seek
   the stabilizer of boundaries with additional dependencies/shared partial
   sums; preserve joint profiles, ownership and execution entry. Do not apply
   count merging to fixed-order `curve.py`, infer greedy guarantees, or claim
   that this settles minimal physical state. See FORK_QUOTIENT_RESULTS.md.
   **Dependent-branch follow-up:** whole-branch permutations remain valid with
   two-op tails and a symmetric product join. Joint continuation types give
   81→45 / 100→55 boundary states; all 221 completed literal-order comparisons
   match. Separate counts lose input pairing and progress/residency correlation.
   A completed asymmetric prefix can expose a symmetric remaining subgraph:
   local certification halves two conditional solves in that control. The
   remaining typed problem and boundary contracts, rather than only the full
   graph's group, are the next quotient target. Progress is already encoded
   by remaining operators, not a new history coordinate. Global order orbits
   still number (2m-1)!! for two-op chains, and the three-branch join times out
   at 60 s. Next prove transition closure for a dynamic remaining-state quotient
   before claiming a scalable search; preserve joint profiles, lifetime,
   ownership and entry. Shared multi-writer sums remain a separate model.
   See BRANCH_SYMMETRY_RESULTS.md for 852 exact replays and all attempts.
4. **P22, after P21: overlap and buffer occupancy.** A single-channel extension
   must charge double buffering and in-flight tiles against the same capacity
   budget as retained tensors. Prefetch scheduling follows this model; it does
   not precede the retain/spill experiments. Interval information may be needed
   at the interface; a single (compute, traffic) pair is not generally enough.
5. **Real scale and an architecture decision, last.** Only after small-graph
   composition checks, extend from 16 to 128 operators. Predict S_G(q) for GPT-scale FFN
   and attention from validated structural formulas, and check them against
   exact curves at sizes the model can still solve. Then give one buffer-size ×
   bandwidth co-design example. That closes the loop from graph structure to an
   architecture choice.

## Bandwidth boundary

In the current serial, no-recomputation model every mapping has the same
compute work W. With constant throughput P, T = W/P + Q/B, so the Q-minimizer
is optimal at every positive bandwidth B. Bandwidth rescales traffic-related
time differences; it cannot reverse their sign. Do not claim bandwidth-driven
mapping crossovers without recomputation, shape-dependent utilization, or
compute/transfer overlap.

Even the aggregate roofline T = max(W/P, Q/B) cannot reverse rankings when
W/P is identical for every mapping: it remains monotone in Q. An overlap-based
crossover needs mapping-dependent overlap opportunities or phase timing, with
their buffer occupancy represented; merely replacing plus by max is insufficient.

For serial stages, fixed-interface (capacity, compute time, traffic) Pareto
summaries compose by max capacity and additive compute/traffic. Their supported
lower hull answers all positive-bandwidth linear objectives without re-search.
With overlap, sum(max(c_i,q_i/B)) is not generally
max(sum(c_i),sum(q_i)/B); a time/occupancy interface needs its own proof.
DRAM is a test setting for composable summaries, not a broadened research theme.
SoMa, SFD and LoopTree comparisons require reading the papers before claims.

## What would change the plan

- **P19a fails, with kkkiii's maximum equal to n·L.** The first-split account
  is wrong beyond b <= 2. Step 2 then targets retention scopes and loop
  skeletons (LOOP_NORMAL_FORM.md, SCALAR_RETENTION_PROOF.md) instead of role
  counts.
- **Tested coarser interfaces fail, and states do not shrink below the
  projected key.** Keep that sufficient key without claiming minimality. The
  contribution rests on the invariant and the analytic formulas, not on
  compression.
- **The FFN gap is not explained by sharing (P14-FFN′ fails as well).** The
  FFN mechanism is then classified from executed witnesses before it is used
  as evidence.

## Not goals

- Faster search as the headline. Speed is a consequence to report, not the claim.
- New hand-made mapping families for one fork shape.
- Multi-bank or 3D DRAM, broad joint hardware/data-placement optimization.
