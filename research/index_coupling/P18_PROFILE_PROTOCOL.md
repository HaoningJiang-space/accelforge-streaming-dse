# P18 profile reanalysis: fix the measure before extending the prediction

This is exploratory reanalysis of already archived P18 curves, following the
observed equality of the P18d maxima. It does not amend the frozen P18 criteria
or count as held-out validation. No new mappings are evaluated.

The number of positive-gap breakpoints is not the length or frequency of a
positive-gap region. Two equivalent representations can have different sample
counts. Likewise, an unweighted average over each pair's breakpoints uses a
different distribution of traffic targets for each comparison.

For each shape, fix one common interval [0,q_hi], where q_hi is the largest
extra-traffic coordinate across all seven archived role strings. Compute exact
integrals of the step functions on the union of their breakpoints. The uniform
weight on extra traffic is an explicit analysis convention, not a distribution
of real hardware requirements. It must be reconsidered for an application-
weighted architecture study.

Report, separately:

- Maximum signed capacity difference, including its intervals of attainment.
- Length and fraction of the common domain where the capacity difference is positive.
- Signed area A = integral (S_mixed(q)-S_pure(q)) dq, in capacity*traffic units.
- A/q_hi, the mean absolute capacity difference on that domain.
- The integral of (S_mixed-S_pure)/S_pure divided by q_hi, a relative mean.
- Positive-area / positive-domain-length, the mean magnitude where a penalty exists.
- The unweighted pair-knot average, labeled as such, for comparison with prior summaries.

For these curves the compulsory traffic and minimum feasible capacity agree
within each pure/mixed comparison. The difference is zero after both reach the
minimum capacity, so A is independent of adding a longer zero-gap tail. As an
independent arithmetic check, compute the same signed area as

    integral (Q_mixed(S)-Q_pure(S)) dS.

The two expressions are the areas between the same monotone staircases, viewed
along opposite axes. Adding extra interior q samples must leave all integrated
metrics unchanged; the driver checks this as well.

Before scoring, verify exactly 84 unique expected records, strictly increasing
capacity / decreasing traffic frontiers, and the correct compulsory traffic
IJ+JK+m*L*(I+K). Keep all failed assertions visible.

Comparing one and two minority consumers at m=4 isolates the mixture count
within this fixed-order grammar. Comparing m=3 and m=4 also changes the pure
baseline and workload size. A lower relative mean alone cannot establish that
the absolute penalty was reduced. Report the absolute areas too.

Equal maxima do not identify a unique cause. The existing table has, for
example, maximum gap 8 for n=4,L=8, whereas n*L=32. The observed expression is
n*min(L,n/2); interpreting every maximum as one complete accumulator's size
would discard the second branch. Establish the responsible allocation/loop
change from executable witnesses before making a causal claim.

Consumer-order completion is a separate follow-up. It must take a Pareto union
over legal orders with tensor identity preserved, and use the same order set
for every mixture being compared. Do not replace only the worse archived order
or silently rewrite the P18 scores.

## Narrow order-complete control fixed before its execution

Use only the already identified order-sensitive shape (16,4,16,4), with two
K-contracting consumers and one I-contracting consumer. Evaluate kki, kik and
ikk with the unchanged curve model. Preserve the original operator names,
tensor names and data bindings while permuting independent consumer operations;
do not implement the control by changing the computation's input identities.

Within this fork's name-invariant cost model, permutations of the two equal-role
consumers are equivalent, so the three orders cover all six physical operation
permutations up to that symmetry. Check the kki/ikk numerical curves against
their archives, take a Pareto union, and independently execute every point of
the resulting envelope. Report all curves and all improvements or their absence.

This case was chosen after observing an order difference. It tests mechanism
and implementation, not generalization. It does not replace P18's fixed-order
baseline, and has no predicted minimum improvement. One process is limited to
4 GiB address space and 120 seconds of CPU time; a failure remains a result.
