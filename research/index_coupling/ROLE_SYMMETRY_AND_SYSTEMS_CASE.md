# Role symmetry, exact accounting, and the systems claim

Source reviewed: `2d268606`. This is a derivation from `curve_model.py` and
`nest_model.coupling`, not a new experiment or a report of P17 outcomes.
It leaves the frozen protocol and running experiments unchanged.

## 1. What can already be proved about P17

Consider the exact recursive model (`grid=None`, no extra caller-supplied
`written` tensors), with the same capacity limit and sharing switches for both
graphs. Let `lambda = spill_cost`. The default physical accounting uses 2;
the role-neutral accounting experiment uses 1.

The terminal tensors D and V occur only in EV. Their index sets are:

| Graph | D, read-only input | V, accumulated final output |
| --- | --- | --- |
| same | K,L | I,L |
| cross | I,L | K,L |

**Proposition.** At lambda=1, the complete numerical capacity/traffic frontiers
of these two graphs are identical in this recursive model, for every positive
integer shape accepted by it. I=K is not required. The result concerns the
tile domain actually visited by the implementation, not all integer tilings
or all physical executions.

**Proof.** Map a same-graph recursive construction to a cross-graph construction
by swapping the tensor names D and V in every held/refetched/external set.
Leave the operation groups, rank variables, tile sizes and other tensors fixed.

1. Tensor incidence and index sets, interpreted as sets, correspond under this
   swap. Both graphs have the same rank variables per operation. Every tile
   footprint and every sum of simultaneously held footprints is preserved.
2. D and V each occur in only EV. Neither can be shared across sibling groups.
   Thus all inter-group materialization charges and the write-through and
   multi-consumer restrictions concern the same other tensors in both graphs.
3. The only intermediate produced and consumed inside a group is X. The rule
   that prevents consumption of an unfinished reduction is therefore unchanged.
4. At a loop, every lacking-index tensor is either retained or refetched. The
   footprints agree. When lambda=1, an input and an accumulated output have the
   same extra charge `(trips-1)*size`; their swapped roles cannot change it.
5. The scalar base case counts live objects, so it also agrees. The compulsory
   term is the sum over graph inputs and outputs. D and V both belong to this
   union, so exchanging their roles preserves the sum even when I differs from K.

Induct on the recursive construction. Each split reduces an extent and the
base cases agree, so each construction has a partner with identical peak and
traffic. Swapping again gives the inverse. Taking the Pareto set preserves
equality. Witness ordering and which tied representative is returned need not
be equal. This argument does not exchange D and V values in a numerical
execution; it pairs schedules for two different computations. End of proof.

P17 remains a useful implementation check of this symmetry. Its outcome cannot
by itself establish that a real memory system implements lambda=1. The broader
shape statement above is a derivation after the original prediction was frozen;
it is not an additional held-out experimental success.

## 2. A more informative identity at the ordinary cost

For a paired, fixed recursive construction m, define:

- B_KL(m): extra revisit volume of the terminal K,L-plane object, with coefficient 1;
- B_IL(m): the corresponding volume of the terminal I,L-plane object;
- B_common(m): extra partial-sum revisit volume of the unchanged outputs X/U;
- Q_1(m): total traffic with lambda=1.

Volumes include outer-loop multiplicities. They exclude compulsory transfers
and ordinary inter-group materialization. These quantities can be defined
recursively from the same additions and trip-count multiplications as the code.
Then, exactly within the model,

    Q_same(m, lambda)  = Q_1(m) + (lambda-1)*(B_common(m) + B_IL(m))
    Q_cross(m, lambda) = Q_1(m) + (lambda-1)*(B_common(m) + B_KL(m))

and hence

    Q_cross(m, lambda) - Q_same(m, lambda)
        = (lambda-1)*(B_KL(m) - B_IL(m)).

For the row-strip construction with p strips, B_KL=(p-1)*K*L and B_IL=0.
At lambda=2 this recovers the exact `(p-1)*K*L` premium. A column-oriented
construction can expose the opposite plane. Thus this identity does NOT prove
that the optimized cross curve is everywhere worse. The two graphs may select
different constructions at the same capacity.

A universal ordering would require a replacement argument covering *every*
cross construction with some no-worse same construction. Neither the paired
identity nor a high empirical success fraction supplies that argument.

There is also a useful sensitivity property. At a fixed feasible capacity, the
optimal traffic is the minimum of affine, nondecreasing functions of lambda.
It is therefore nondecreasing and concave in lambda within this fixed grammar;
the chosen construction can change at intersections. A memory feature's benefit
must consequently be evaluated after reoptimizing the mapping, not just by
changing a coefficient on the old winner. This is an accounting sensitivity
result, not a calibrated hardware performance model.

## 3. Correct transfer accounting before generalizing the solver

For N elements revisited in R separate residence episodes:

    read-only input:                         N*R
    zero-initialized accumulated output:     N*(2*R-1)

The latter has R stores and R-1 reloads, assuming the first partial sum is
initialized locally and the final result must be stored. Relative to compulsory
traffic, the charges are N*(R-1) and 2*N*(R-1). An externally initialized output
has different boundary accounting. Intermediate materialization and shared
consumers require their own explicit boundary events.

This explains why the cross *premium* in a paired row schedule is (p-1)*K*L,
not 2*(p-1)*K*L. The second expression is the output's whole extra spill cost;
the corresponding input already incurred one copy of that revisit cost.

Likewise, memory capacity counts distinct simultaneous physical allocations,
including their scopes. A producer buffer may be replaced by retained operand
and accumulator slices, as the scalar-retention proof demonstrates. Counting
only tensor edges across an operator cut misses this substitution.

## 4. What the proposed skeleton/size split still has to establish

The split is a useful implementation direction; it is not yet a completeness
or complexity theorem.

**A bounded structural representation.** The present recursive model can split
the same rank repeatedly at different scopes. A fixed-depth skeleton family is
finite by definition, but may omit useful schedules. To claim a size-independent
complete family, prove a normal-form transformation that removes redundant
levels without increasing traffic or peak, and bounds the remaining depth by
structure. Otherwise declare the depth bound and measure the coverage loss.
Even a fixed number of arithmetic operations is not constant bit complexity.

**Safe structural pruning.** An index appearing in all outputs identifies a loop
that does not revisit those outputs' partial sums. It is not, by itself, a proof
that this loop should be outermost: input reuse, intermediate completion and
other live allocations also change. Require a full-traffic and footprint
replacement witness before using this observation as a pruning rule.

**An appropriate size solver.** Fixed regular rectangular tilings with positive
monomial terms can admit geometric programming. A peak written as a maximum is
handled by separate capacity inequalities for each live phase. Ceilings, divisor
restrictions, ragged tails and discrete scope changes are not ordinary continuous
GP constraints. Boundary corrections such as 2R-1 also need explicit handling.
Rounding must restore capacity and execution legality, then report its traffic
loss. The existing exact ceiling-quotient elimination should remain exact; it
does not need to be replaced by continuous optimization and rounding.

**A valid lower bound.** An output can remain resident, so charging every
accumulator plane twice is not a universal I/O lower bound. A proof must show
which partial sums necessarily cross an execution partition, with correct first
and final transfer charges. The lower and upper bounds must refer to the same
memory, computation, recomputation and legality assumptions before equality
certifies optimality. This stronger result is valuable but need not block a
useful executable planner with an honestly restricted search contract.

The role-neutral projection summary above cannot distinguish the graphs. That
does not establish that Hong-Kung/CDAG or HBL-based analyses can never do so.
In particular, [SOAP](https://spcl.ethz.ch/Publications/index.php?pub=418)
explicitly addresses multiple statements and input/output reuse. The
[IOOpt tool](https://iocomplexity.corse.inria.fr/ioub) already accepts read/write
occurrence counts, constructs symbolic traffic expressions, and selects loop
permutations and tile sizes. These are direct tools/baselines to investigate;
their support for this exact shared-tensor execution space still needs checking.
[Boyd et al.'s GP tutorial](https://web.stanford.edu/~boyd/papers/gp_tutorial.html)
distinguishes exact GP formulations from approximations.

## 5. The systems result worth building toward

The useful outcome is an executable mapping with better resource/performance
tradeoffs, produced at an affordable search cost. Explaining two small curves
is a mechanism result; it is not the complete systems result.

The current evidence has three different strengths:

| Claim | Existing evidence | Remaining gap |
| --- | --- | --- |
| Roles and scopes affect traffic | Fork contrasts, scalar-retention proof, role symmetry above | Generality beyond the fork and current abstract memory |
| Internal size decisions can be eliminated cheaply | Exact six-family solver; matched-family compressed compilation is 7.2-8.3x faster | Automatic structural coverage; no native-search speedup follows |
| The resulting planner improves whole workloads | FFN/attention investigations and sharing witnesses | Correct complete workload semantics, broader coverage, realized hardware benefit |

The wider-grammar tests still fail their quality gates: on 16 fresh instances,
the full-plus-scalar family covers 84.96% of tested integer budgets within 5%
traffic, and its worst excess is 42.64%. Those numbers should be visible beside
the matched-family speedup. See [the results](SCALAR_RETENTION_RESULTS.md).

Organize the next evaluation around separate causal questions:

| Question | Controlled comparison | Report |
| --- | --- | --- |
| Does the structural generator cover useful plans? | Freeze generation rules; use exact recursive reference on small held-out structures | Full traffic/capacity curves, worst gap, missed scope patterns, executable witnesses |
| Does size elimination avoid work? | Same skeletons, cost model and integer domain; cached exhaustive sizing versus analytic sizing | Construction plus queries, actual evaluations, memory, rounding/repair loss if any |
| Do richer sharing semantics improve solutions? | Same search machinery, sharing mechanisms on/off; distinguish native FFM's supported space | Traffic gain attributed to representation, not misreported as search acceleration |
| Does the system improve hardware execution? | Fixed hardware and mapping budget first; then calibrated architecture choices under a common budget | Latency, energy, traffic, PE utilization and search time, including negative cases |

Hold out graph structures as well as dimensions. For attention, the current
elementwise softmax approximation is not sufficient execution evidence: online
statistics and output rescaling must be part of the contract. For FFN, alias
ownership and lifetime must be accounted for before claiming a capacity saving.
Traffic savings alone do not imply latency savings when compute or another
memory level dominates. Different SRAM sizes also do not imply equal chip cost
without a calibrated area/cost model.

[TASO (SOSP 2019), section 7.5](https://www.cs.cmu.edu/~zhihaoj2/papers/sosp19.pdf)
offers a relevant evaluation pattern: compare each optimization alone, their
sequential application, and their joint application, then connect the difference
to actual executed graphs. The lesson here is to isolate graph-level residency
choices and local tile-size choices in the same way. Exact nested optimization
is a valid joint-search baseline; a weak one-shot sequential choice is not a
substitute for it. This is an experimental design analogy, not a novelty claim.

The next narrow deliverable should therefore be a structural generation rule
with a declared scope bound, executable plans, and the existing exact sizing
rules where applicable. Its first test is coverage of previously unseen useful
residency structures, before making a new claim about all schedules or hardware
accumulation. No new optimizer name or universal lower-bound claim is needed.
