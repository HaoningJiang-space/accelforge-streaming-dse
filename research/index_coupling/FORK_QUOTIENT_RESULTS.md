# Consumer symmetry removes substantial exact-search redundancy

An independent order-complete Fork solver now implements the proposed symmetry
quotient, including recursive partitions and loops. Five complete reference
envelopes agree point for point. All 128 conditional three-consumer queries
agree with the union of all six literal consumer orders. The original positional
counterexample disappears in this grammar. None of the fixed-order solver's
defaults or frozen prediction scores changed.

This establishes an exact algorithmic opportunity within the specified Fork
grammar. It does not quantify a fraction of intrinsically necessary physical
states, prove minimality, or establish applicability to arbitrary accelerator
schedules. The theorem, recurrence and context-count bound are in
[FORK_QUOTIENT.md](FORK_QUOTIENT.md).

## 1. The conditional symmetry is realized, with executable identities

For fork(2,2,2,2,kkk), the fixed-order responses at the same remaining capacity
are `(3,56)` for external {C0,C2} and `(3,52)` for {C1,C2}. Both order-complete
responses are exactly

    ((3,52), (4,32), (7,24)).

After the first query, the second adds zero response-cache misses. Its witness
is reverse-mapped to the requested tensor identities and chosen operator order;
it is not executed using the representative's tensor names.

The implementation retains joint `(input resident, output resident)` profiles
per literal k/i role, plus shared A/B/X residency, extents, producer presence,
entry kind and X write ownership. The two private bits cannot be replaced by
separate marginal counts. Structural enumeration confirms:

| Six-consumer boundary | Labeled assignments | Canonical boundary keys |
| --- | ---: | ---: |
| All k, input bit only | 64 | 7 |
| Three k / three i, input bit only | 64 | 16 |
| All k, both private bits | 4,096 | 84 |
| Three k / three i, both private bits | 4,096 | 400 |

In the complete three-consumer query census, the 64 joint assignments become
20 keys for kkk and 40 for kki; every response agrees with all-order enumeration.
These boundary-key counts are not end-to-end speed ratios.

## 2. Root search measurements and exact references

Source `0f36b969`, all dimensions two, halving tiles, fresh Linux workers,
Python 3.10.12, hash seed zero, 60 seconds including replay and 6 GiB each,
at most four simultaneous jobs. The declared 59 jobs yield 58 complete and
one timeout. All 646 saved frontier executions, including conditional wrappers,
are exact. Five reference envelopes require respectively 1,6,1,20,20 decorated
orders; every required order completed. The score retains the mixed-eight
timeout as incomplete, not a pass.

| Case | Reference orders | Sum of reference memo entries | Quotient solve + group + sequence entries | Equal curve? |
| --- | ---: | ---: | ---: | --- |
| Four all-k consumers | 1 | 7,585 | 2,130 | yes |
| Two k / two i | 6 | 45,510 | 6,442 | yes |
| Six all-k consumers | 1 | 106,604 | 6,092 | yes |
| Three k / three i | 20 | 2,132,080 | 33,815 | yes |
| Six all-k, C0/C2/C4 pinned | 20 | 420,250 | 6,484 | yes |

Reference counts sum the solve/group response caches across independently
searched orders. They are cumulative construction counts, not simultaneous
memory use. Prototype counts also include its sequence response cache; neither
column counts incidental metadata caches or proves a minimal quotient.

The homogeneous six-consumer curve is `((3,136),(4,84),(7,56))`. Because the
unconditional homogeneous root is invariant under every consumer permutation,
its one fixed-order reference already has the complete optimum. The improvement
here is discovery cost, not a better communication schedule. The prototype
completes in 1.219 s including replay, with 28.7 MiB peak RSS in this run.

The mixed-six prototype completes in 9.957 s including replay (69.4 MiB), and
agrees with the envelope of all twenty role orders. Eight all-k consumers finish
in 5.725 s with exact witnesses and curve `((3,176),(4,108),(7,72))`; no exhaustive
eight-consumer oracle was budgeted. Four k / four i reaches 60 seconds during
search and is incomplete. Different joint profiles and group-membership
choices still make the mixed family expensive.

First-study reference timings include detailed Pareto/merge instrumentation,
whereas the prototype has lighter counters. They are not used for the controlled
speed claim below. Summing parallel reference-job elapsed times is also not
end-to-end wall-clock latency.

## 3. Isolating symmetry from the new partition recurrence

Source `af5f5826` adds a labeled mode of the SAME all-order recurrence. It keeps
every consumer identity, enumerates labeled group subsets and retention masks,
and uses the same witness construction. Thus this control isolates the combined
state/transition symmetry quotient without reverting to a fixed-order grammar.

| Complete ablation pair | Labeled response entries | Quotient entries | Labeled / quotient search seconds |
| --- | ---: | ---: | ---: |
| Four all k | 17,203 | 2,130 | 2.0046 / 0.1879 |
| Two k / two i | 17,203 | 6,442 | 1.2305 / 0.6718 |

Both complete pairs have identical full curves and executable witnesses.
Both six-consumer labeled jobs time out at 60 seconds. Their partial counters
are archived, but no completed-state reduction ratio or speed ratio is claimed
for those pairs. Unordered subset search without symmetry can itself be more
expensive than the original fixed-order DP.

After those jobs, six fresh processes ran sequentially, alternating fixed-order
DP with the quotient, three times each for homogeneous m=6. Reference profiling
was disabled; prototype counters stayed enabled. Every curve and witness agrees.

| Arm | Search seconds, all three samples | Median |
| --- | --- | ---: |
| Original fixed-order DP, no profiling | 11.6478, 11.6508, 22.5381 | 11.6508 |
| Order-complete quotient | 1.1883, 1.1902, 1.1880 | 1.1883 |

The ratio of medians is **9.80x** on this control. The slower third reference
sample is retained; its cause was not diagnosed. This is a small, scoped timing
comparison, not a hardware-independent or general-graph speedup claim. The
14-job follow-up has 12 complete jobs, two timeouts and 39/39 exact replays.

## 4. A structural bound stronger than a local branching count

The canonical response key has two four-profile count vectors with sums at
most a and b. With D four-rank extent configurations, the three response caches
have the loose upper bound

    96 D binomial(a+4,4) binomial(b+4,4).

This counts absent consumers as well as all four residency profiles, and
includes producer/shared-residency/ownership/entry flags. Thus accumulated
ancestor residency is represented without a hidden labeled 2^m factor here.
For fixed shape domains, response-state growth is bounded by O(m^4) in the
homogeneous family and O(a^4 b^4) with two roles. Group membership transitions,
frontiers, integer dimensions and witness construction are additional work.

This is not the earlier proposed linear-width theorem. It is a bound for an
explicit new quotient and grammar. The mixed-eight timeout remains consistent
with a high-degree polynomial bound. It does not apply to growing-rank stacks,
nonterminal/private-output dependencies, identity-specific costs or externally
fixed order constraints. Those structures can break the permutation group or
increase the number of distinct boundary types.

## 5. Reproduction and next proof boundary

- [First study raw records](results/fork_quotient/), including its manifest,
  source hashes, all chosen orders/witnesses, the timeout and [score](results/fork_quotient/score.json).
- [Ablation/timing raw records](results/fork_quotient_ablation/) and
  [score](results/fork_quotient_ablation/score.json).
- Seven unit tests pass: literal-order oracle agreement, rectangular/nonbinary
  tile controls, all joint two-consumer profiles, the positional counterexample,
  shared residency/ownership/entry distinctions, labeled-ablation equality,
  and the six-consumer orbit cardinalities. Conditional witnesses execute in
  a real retaining-loop wrapper restoring caller allocation and transfers.
- `graph/curve.py`, `simulate_nest.py` and the frozen protocol are unchanged.

```sh
python3 -m unittest research.index_coupling.test_fork_quotient
python3 -m research.index_coupling.score_fork_quotient research/index_coupling/results/fork_quotient
python3 -m research.index_coupling.score_fork_quotient --ablation research/index_coupling/results/fork_quotient_ablation
```

The scorers intentionally return a nonzero status for the retained timeouts;
their completed comparisons and replay failures are reported separately.

The next mathematical target is the stabilizer of a decorated boundary when
some consumers become distinguishable through downstream dependencies or
shared partial sums. Establish a cost-preserving action before merging those
states. The present result settles a useful special case; it provides no new
greedy guarantee and makes no literature-novelty claim.
