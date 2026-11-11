# Fixed M-to-one branch: joint weight and boundary elimination

This note fixes the mathematical scope and measurement plan before running
the audit. It distinguishes common-loop coordination from live reservations.
The default solver and its grammar are unchanged. This is not a generic
hypergraph optimizer or a claim that M>1 root search has been solved.

## Restricted claim

Use a recognised dense-contraction/elementwise chain with distinct feature
ranks, at most one elementwise op between contractions, private weights,
and no external or owned interior activation. Fix the whole-span outer
M loop to tile 1. All other row ranks, if any, must already be unit. The
tested graphs have only M. Existing caller residency and ownership stay
fixed. The loop's missing-M tensors must be precisely its nonresident
private weights, so no accumulated output is in this decision set.

Let r=M, s_i be the current size of a missing weight, and x_i indicate
retention at this loop. Existing caller-held weights have no new choice or
new reservation. In extra-traffic units the branch response is

    Q_branch(C) = min_x [(r-1) sum_i s_i(1-x_i)
                         + r F_unit(C-sum_i s_i x_i; x)].

Root compulsory traffic is added separately. This is one original group
branch, not the whole solve response. Other ranks, M tiles and proper
partitions remain outside the claim.

The existing unit-M proof reduces a conditional chain to local patterns
`c`, `e`, `cc`, `ce`, `ec`, `cec`. A selected partition assigns each private
weight to exactly one segment. Its local response depends only on the
segment's weight-streaming flags and the two boundary retention flags.

Fix final outer reservation a and parent capacity C. At **every** segment,
child capacity is c=C-a, including before the last retained weight is used.
Using only the prefix reservation would undercharge live outer weights.

For each a, let V[j,b,u] be the least traffic for the prefix through j,
with boundary flag b and u cells of retained private weights selected in
that prefix. Initialize V[0,first,0]=0. For an eligible segment [j,k), choose
its at most two missing private-weight bits x_B and outgoing flag b'. Let

    delta_a = sum_{i in B} s_i x_i
    delta_d = (r-1) sum_{i in B} s_i(1-x_i)
    rho = sizes[j]*b*[j>0] + sizes[k]*b'*[k<n]
    q = group(B, C-a-rho, b, b', streaming_flags(x_B))
    spill = 2*sizes[k] if k<n and b'=DRAM else 0.

Then update

    V[k,b',u+delta_a] = min(V[k,b',u+delta_a],
                           V[j,b,u] + delta_d + r*(q+spill)).

The final answer is min_a V[n,last,a]. Weight traffic and intermediate
write/read events are disjoint. Boundary reservations are charged before
serial peak composition, as in `forms.predict`.

### Why the state forgets identities safely here

A full retention mask and a legal child partition define one path in this
DP, with identical capacity constraints and traffic. Conversely, a DP path
assigns each private weight once and gives a legal local plan per segment;
concatenating the segments gives the original branch. Minimizing the finite
choices in either order therefore gives the same response.

At a fixed (j,b,u,a,C), past weight identities cannot affect later factors:
their consumer is already inside a completed segment, their total outer
allocation is accounted by a, and their traffic has been paid. Future
activation effects are exactly the boundary flag b. A minimizing path can
retain one representative mask for witness recovery; that mask is payload,
not part of the DP state key.

This is **joint minimization**, not a claim that all child curves with equal
weight counts/bytes are identical. Such curves may differ. It also does not
construct a small signature representing every conditional child response.

### Complexity and limitations

Use reachable reservation sums, built by subset-sum DP rather than full mask
enumeration. Integer capacity gives at most C+1 values for a and u. With
bounded local patterns and at most h reachable feature tiles, a conservative
fixed-capacity candidate bound is O(n C^2 h^2), plus reachable-sum and local
factor construction. This is pseudopolynomial, not polynomial in the bit
length of capacity. Reachable-sum domains can still be exponentially large
in the number of weights if sizes grow sufficiently rapidly. Full frontier
construction adds its capacity sweep; all such costs must be measured.

This proof uses the existing unit-M local forms as exact primitives. It does
not extend their conditions to shared weights, returning feature ranks,
external interior activations, missing-M partial sums, arbitrary M tiles,
or the original F/D loop choices. Outside the guard, retain original search.

## Bounded audit and timing plan

Primary cases: existing `ffn_forward_l1_m8` and `ffn_forward_l2_m8`. The existing
tiny `ffn_forward_l4` is a positive-control workload with more weight choices,
not a new scale study. Inspect only each root's whole-span M-to-one branch.

1. Recover its actions from the existing C2 call archive. Verify legality,
   tile, missing tensors, each unary capacity/traffic coefficient, the full
   child transition, and the branch envelope. Archive values are reference
   data, never input to the joint evaluator.
2. Compare complete fixed-branch frontiers from three methods: original
   recurrence with shared native memoization; existing unit-M substitution
   while enumerating masks; joint DP using local forms without full-mask
   child evaluations. Preserve scalar-leaf and ownership semantics.
3. Recover every selected native witness and replay independently. Both
   substitution methods charge native recovery time; they may not use an
   archived witness as a free result. Record setup, branch response search,
   recovery and replay separately. The branch comparison does not measure
   whole-root mapping-generation acceleration.
4. Three fresh-process rounds, alternating arm order, fixed hash seed 0,
   120-second worker timeout. Record unique child/whole-chain evaluations,
   local factor requests and cache misses, DP states/transitions, factor
   construction time, generation time and pre-replay peak RSS. Report costs
   of both the native and replacement representations; no single counter
   is treated as wall time.
5. At the existing full-root Pareto points, report where this branch attains
   the same traffic at the same capacity. This is retrospective relevance,
   not a prediction of global speedup: other branches may still require the
   same children.

Stop at the bounded branch audit. No automatic expansion to other loops or
online root integration follows a positive result. Negative M8 timings are
retained without increasing shape sizes to rescue them. No performance
threshold or speedup is asserted before measurement.
