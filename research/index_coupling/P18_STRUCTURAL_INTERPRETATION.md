# Structural interpretation of the frozen P18 experiment

Reviewed source: `a35667ca`. This note does not change P18, use its numerical
outcomes, or introduce another prediction success. It separates consequences
of the grammar from the empirical claims the frozen experiment is testing.
The untracked scoring script is left unchanged.

## 1. The first-split formula is exact for its stated local choice

Let a consumers contract K and b consumers contract I, with m=a+b. For the
whole producer/consumer group, with nothing retained across the first split,
the extra traffic per additional trip is

    W_I = J*K + (a+2*b)*K*L
    W_K = I*J + (2*a+b)*I*L.

With I=K=n, the two axes have identical split domains and

    min(W_I,W_K) = n*J + n*L*(m+min(a,b)).

This is a statement about one unretained split, not the optimized capacity
curve. The optimizer can change its partition, tile sizes, retention masks
and nested scopes. Thus it does not establish P18b, P18c or P18d. In particular,
linear growth of this local coefficient in min(a,b) does not imply linear or
monotone growth of the optimized inverse-curve gap.

The whole-tile retention decision is already discrete when inner costs are
fixed. If changing retention also changes the continuation, even a standalone
0/1 knapsack is only a local subproblem, not the full optimization problem.

## 2. Two exact symmetries of this fork grammar

Write F(r;I,J,K,L;lambda) for the numerical capacity/traffic frontier of the
ordered roles string r and partial-sum revisit coefficient lambda. There is
one private input and one terminal output for every consumer, and X is their
only shared tensor. Layout, bank and tensor-name-specific costs are absent.

**Independent role swaps at lambda=1.** For fixed extents and a fixed number
of consumers, F is the same for all 2^m roles strings when lambda=1. For each
changed consumer, swap its private K,L-plane and I,L-plane object names, as in
the two-consumer P17 proof. Neither object has another consumer. This preserves
footprints, partitions, X's completion requirement and materialization charges.
At lambda=1 their input/output distinction cannot change loop revisit charges.
The swaps commute across consumers and have inverses, proving equality of the
complete numerical frontiers inside this grammar. This is a proof extension,
not a measured extension of P17 or a physical accumulation-engine result.

For a fixed paired construction, changing a set C of 'k' consumers to 'i'
consumers gives the more informative identity

    Q_changed - Q_original
        = (lambda-1)*sum_{j in C}(B_KL,j - B_IL,j).

The B terms include outer-loop multiplicities, but not compulsory transfers.
This identity is linear for a *fixed construction*. Minimizing over different
constructions need not preserve such linearity.

**Axis/complement symmetry at ordinary costs.** Let bar(r) complement each
character, preserving its position. Then

    F(r;I,J,K,L;lambda) = F(bar(r);K,J,I,L;lambda).

Exchange ranks I and K, rename the producer's A/B inputs, and rename every
consumer's private input and terminal output to their corresponding names.
Input roles remain inputs and output roles remain outputs; lambda need not be
1. Projective footprints and traffic are unchanged. Operation positions are
unchanged, so every contiguous group partition has a matching partition. The
unfinished-X rule and all sharing switches agree. The inverse transformation
proves frontier equality.

At I=K this establishes P18e: kki and iik have equal curves. P18e therefore tests
implementation symmetry, while P18b-d test additional, unproved optimization
claims. Their scientific roles should not be combined into one pass count.

## 3. Consumer order is a separate restriction

The consumers in this fork have no dependence on one another. If the legal
schedule space includes every topological consumer order and costs are invariant
under tensor/operation renaming, roles strings with the same a,b define
isomorphic optimization instances. Map each 'k' consumer to a 'k' consumer and
each 'i' consumer to an 'i' consumer; rename its private input and output. This
bijection preserves every physical execution and its costs. In that space,

    F_all_orders(kki) = F_all_orders(ikk).

The implemented `curve_model` instead partitions the supplied `graph.ops`
sequence into contiguous groups. That candidate-space restriction need not
survive the consumer permutation. Hence a difference between the archived kki
and ikk curves is evidence of *fixed-order grammar sensitivity*, not evidence
that their dependency graphs have inherently different optimal communication.

For this restricted fork, an order-complete reference can be defined as the
Pareto union of curves over all distinct role orderings with the same a,b.
There are binomial(m,a) such strings rather than m! distinguishable cases,
because equal-role consumers are identical up to private tensor renaming.
This describes a correctness reference, not a proposed scalable optimizer.
It must be reported as a separate follow-up; do not use it to replace the
already frozen P18 baseline or repair failed predictions retroactively.

In particular, a future order-complete four-consumer check would require the
other placements of the one or two 'i' consumers. P18 intentionally does not
enumerate all those placements. That does not invalidate P18, but limits which
claim its results can establish.

## 4. How to interpret the other frozen predictions

| Prediction | What it would support | What does not yet follow |
| --- | --- | --- |
| P18a | The proposed terminal-accumulator capacity bound survives the tested larger forks | Grammar closure of reservation promotion for all constructions |
| P18b | Near-monotone capacity ordering on this domain and these orders | Global monotonicity from first-split obligation weights |
| P18c | The two-consumer maximum-gap expression transfers to these three-consumer cases | A derivation of the whole curve or arbitrary-size equality |
| P18d | The tested maximum gap grows with the minority count | Pointwise monotonicity at every traffic target |
| P18e | Correct axis/complement symmetry in the implementation | An additional systems-performance advantage |

If the reservation-promotion closure lemma is established, flipping b terminal
pairs gives the proposed -b*I*L / +b*K*L capacity bounds by repeated replacement.
At square shapes, complement symmetry can additionally exchange b with a. This
would strengthen the symmetric bound to min(a,b)*n*L. It is conditional on that
closure lemma, and is not added as a new frozen P18 claim.

## 5. Scoring and the next useful distinction

Before scoring, require exactly 84 unique (shape,roles) records: 12 shapes times
7 roles. Reject duplicates, missing combinations, malformed frontiers and
incomplete files. The current scorer groups records but does not enforce that
manifest. P18a/b have 60 mixed-versus-pure comparisons; c/d/e have 12 shape
comparisons. P18c requires BOTH at least 10 exact shapes AND all 12 within 5%.
Comparing inverse curves at the union of traffic breakpoints covers the full
step functions, including the constant intervals between breakpoints.

These forks test new fan-outs, which is useful structural generalization. They
still have only one shared producer and terminal independent consumers. A
reconvergent GLU-style graph is a different next test: the private outputs become
intermediates, and their completion/lifetime constraints can invalidate a simple
terminal role swap. That test should be designed from its actual index and
execution semantics, rather than inferred from a high P18 pass fraction.

For the systems claim, keep three causes separate: mixed contraction roles,
fixed-order mapspace restrictions, and the cost of discovering a mapping. The
loop-normal-form theorem addresses redundant structure inside the existing
grammar; it neither removes the ordering restriction nor establishes search
acceleration on these forks.
