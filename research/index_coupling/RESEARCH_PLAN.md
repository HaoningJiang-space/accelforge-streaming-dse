# Research plan: a memory-demand invariant of computation graphs

Status: plan, agreed 2026-11-09. Predictions named here are drafts until written into
PROTOCOL.md before their runs. See STATUS.md for the ledger and FIRST_PRINCIPLES.md for
the derivations.

## Question

What is the least information about a computation graph that determines its
capacity-traffic curve S_G(q)? A secondary question is how compact that
information is at a cut, so that summaries of subgraphs compose.

Inside the curve model the curve is, by construction, a function of three
things: tensor sizes, the incidence between einsums and ranks, and the role of
each tensor (input, intermediate, accumulated output). Saying "the graph
determines the curve" is therefore empty. The content lies in which parts of
that description can be dropped without changing the curve:

- P17. With spill cost 1, roles can be dropped entirely, and same equals cross.
- P18e. Exchanging I and K together with flipping every role preserves the curve.
- P18 and P19. In forks, roles may enter only through b = min(#k, #i), and the
  maximum gap through ceil(b/2). P19 tests this.

The classical results are I/O lower bounds for one fast-memory size: red-blue
pebbling (Hong-Kung), IOLB/IOOpt, SOAP and HBL. They do not separate the read and
write costs of accumulation. This plan targets the whole curve, with reduction
roles explicit. The literature check in FIRST_PRINCIPLES.md §5 must place it
against those works before any novelty claim.

## Why this is the composable summary

Curves of sibling groups compose by (max capacity, sum traffic), which is
`combine_max_sum` in graph/curve.py. That rule is valid only for a fixed
interface: which tensors stay live across the cut, their roles, and their slice
granularity. The projected cache key (`7b891c7c`) is one exact interface state
for the current grammar. It cut a four-consumer control from 568,721 to 37,710
states, with all 475 archived curves unchanged.

So "how compact can a demand summary be" becomes a measurable question: how many
distinct interface states are there, and how coarse can they be while staying
exact? P17 already shows that a role-blind interface is not exact when spill
cost is 2. Same and cross would merge, yet their curves differ in 95/95 shapes.

## Why it is architecture-mapping co-optimization

S_G(q) is the interface between a graph and an architecture: the buffer size
fixes the capacity, and the bandwidth fixes the traffic that can be afforded.
Suppose the breakpoints of S_G follow from graph structure, for example
n·min(ceil(b/2)·L, n/2). Then architecture search can read demand off the graph
instead of searching mappings per architecture. This matters most at sizes where
FFM cannot run.

## Steps

1. **Close the open tests.** These decide whether the next steps build on the
   first-split account or on multi-level retention scopes.
   - P19: whether the first-split knapsack generalizes.
   - P14-FFN′: whether sharing accounts for the 34 FFN breakpoints below FFM.
   - An integer-tile retest of dS, since the power-of-two grid is a known
     artifact source.
2. **P20, the minimal invariant (to be frozen after P19).** Use graph pairs with
   equal sizes, operator count and MAC count. State in advance which pairs have
   identical curves and which differ. Candidates:
   - *Order.* After order completion (Pareto union over legal orders, with
     tensor identities preserved), a fork's curve depends on roles only through
     (#k, #i). This tests whether the (16,4,16,4) difference is the only order
     effect.
   - *Role count.* Pairs that differ only in b differ as P19 predicts. Pairs
     with equal b but different consumer placement do not differ.
   - *A non-fork family.* Diamonds or GLU, where a join meets the shared tensor,
     to see whether the fork invariant survives a reconvergent path.
3. **P21: retain/spill and interface-state measurement.** Start with the frozen
   residual-block tests in PROTOCOL.md, independently of P19: P21a excludes X
   from H and tests the capacity-shift identity; P21b lets H read X and tests
   whether a conditional residency/granularity interface repairs the coarse
   curve. Distinguish the fixed partition from unrestricted fusion, include
   producer/join feasibility, and report ties in the 2s inequality. Then, on
   real cuts (the FFN forward/backward
   boundary, the attention score/value boundary), count projected interface
   states against complete mappings. Then test coarser interfaces: role-blind,
   slice-blind, lifetime-blind. Each must reproduce the same final Pareto
   frontier, or the failure is reported. This reuses graph/curve.py. No new
   oracle is needed for the current grammar. A streaming oracle outside the
   grammar is a later extension.
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
- **Coarser interfaces are never exact, and states do not shrink below the
  projected key.** The summary is then the projected key itself. The
  contribution rests on the invariant and the analytic formulas, not on
  compression.
- **The FFN gap is not explained by sharing (P14-FFN′ fails as well).** The
  FFN mechanism is then classified from executed witnesses before it is used
  as evidence.

## Not goals

- Faster search as the headline. Speed is a consequence to report, not the claim.
- New hand-made mapping families for one fork shape.
- Multi-bank or 3D DRAM, broad joint hardware/data-placement optimization.
