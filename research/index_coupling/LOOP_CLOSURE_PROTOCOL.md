# Bounded factorized loop-closure pilot

Frozen before measurements. Baseline: `362e6fb9`; grammar v2, halving tiles,
serial fixed operator order, exact unlimited frontiers, spill cost 2,
single-writer graphs, default ownership projection. Default solver files and
other in-progress work are unchanged. Work stays on `research/main`.

## Semantic decomposition

Let P(s) contain proper partitions and scalar leaf/whole-scalar-hold choices,
but exclude the non-scalar whole-span group. Then F(s) is the union of P(s)
and the response from taking a loop. At a scalar state the group redirect
uses F(s)=P(s). Proper partitions call the normal group interface on their
children, not the unconstrained solve interface.

A full group response can be computed by composing every reachable pure-loop
prefix with P(t) at its endpoint t. Label sets are Pareto(A,D), with the
common multiplier R given by the start/end extent ratio. Preserve full
conditional state identity. Dynamic programming composes only surviving
suffix labels; it must not enumerate raw paths. Intermediate P(t) terms
are mandatory, including those before a loop nest reaches scalar extents.

Correctness follows by cutting a plan at its first non-loop choice. Every
ordinary grammar plan is included in one prefix-plus-P term, every such term
is a legal plan, and label dominance preserves its conditional response.
This is an algebraic refactoring, not a claim of new semantic equivalence or
of reduced complexity.

## A. Label growth

Cases: archived `ffn_forward_l1_m8`, `ffn_forward_l2_m8`, `ffn_training_l1`,
and the saved seed-0 `fork_kki` archive from the prefix audit.

Use the audited complete loop-action DAG. Report closure depths 2 (control),
3, 4, and full closure. For each mode measure state pairs, retained labels,
maximum and distribution of labels per pair, label compositions/pruning,
construction time and peak RSS. Raw path counts may be computed by integer
DAG DP, solely to describe representation; they are not saved original work.
At depth 2 reproduce the previous census pair/label counts. Recover the known
incomparable-prefix control at full closure.

## B. Limited online factorization

An opt-in in-memory kernel may reuse the existing partition DP while replacing
whole-span loop recursion with full label closure followed by P queries.
Use separate caches/counters for solve responses, group responses, P
responses, and structural label summaries. Count label construction and
response composition; reductions in one old cache alone are not savings.
Preserve native witnesses directly through label representatives and partition
composition, without rerunning the baseline solver to reconstruct them.

Before benchmarking, require root frontiers identical to baseline and replay
every returned root witness. Include the `(M,D,F)=(4,1,4)` incomparable-prefix
control. Report original counters (DP transitions, loop choices, Pareto
candidates, merge inputs) together with all added label work and cache sizes.

Three fresh-process repetitions, alternating baseline/factorized order, for
each primary case. Measure both frontier-only search and native-witness
mapping generation. Kernel installation is separately reported; executor
replay is validation outside mapping-generation timing. Fix PYTHONHASHSEED=0.
Report median wall times and peak RSS. These are a feasibility pilot, not a
statistical performance study or a hardware execution benchmark.

## Limits and stopping rule

Each case/mode process is limited to 120 seconds and 2 GiB RSS, monitored by
the runner. Retain failure and partial-output records. Do not expand shapes,
depths or graph families to rescue a negative result. A resource-limited
case does not pass correctness or performance validation.

The engineering continuation gate is at least 20% lower median time on both
M8 cases, for frontier-only and witness-bearing generation, with exact curves,
successful replay, and no more than twice baseline peak RSS. All label work
is included. This threshold is a predeclared pilot decision, not a theorem.
If the gate fails, stop extending this closure implementation and document
the remaining representation problem before any parametric-residency solver.
