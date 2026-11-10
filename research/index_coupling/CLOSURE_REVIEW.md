# Review of exact chain responses and operator projections

Reviewed main commit `39e592085d6e5522f7c916b252de25564ea69187` and the separately
developed DNN branch at `5245c9cc2eed99ca12618189c2736cb2262ae739`. This review
is isolated on `research/closure-review`; it does not modify the solver,
integration branch, simulator, or frozen experiments.

The strongest advance is an exact response for a restricted family of
conditional subproblems. It can replace expensive recursive work directly.
The new operator projection complements this response at M > 1, but its
optimistic exclusion counts do not yet measure work saved by online pruning.

## 1. Independent accounting and response checks

Run:

```sh
python -m research.index_coupling.audit_closed_terminals --out NEW_REVIEW.json
```

The archived output is [closure_review.json](results/contraction_oracle/closure_review.json).
The audit uses topological propagation, independently of the original DFS,
to keep every node with a surviving incoming path. It checks that the call
graph is acyclic, every original node is reachable, and exclusive counters
sum to the original ledger. It then evaluates every reached terminal response
at every integer capacity through its archived plateau and checks shared
structural keys against every corresponding original response. The zero
plateau and monotonic feasibility extend these comparisons to larger capacities.

- All eight archived work projections agree, for all four counters.
- 13,792 reached analytic queries agree in 98,127 integer-capacity comparisons.
- There are 9,438 structural keys summed over the eight archives. This is
  not a count of globally distinct keys or independent graph shapes.
- Re-evaluating the operator bound reproduces every archived case: 17,647
  eligible nodes, 129,717 capacity comparisons, zero violations, and 5,796
  complete response curves equal to the bound.

The original §14 prose said **17,857** and **6,416**. Its eight JSONL rows sum
to **17,647** and **5,796**, respectively; the rerun confirms the latter.
The corrected totals do not change the zero-violation result.

These are checks of the archived sample using the existing response models,
not new held-out predictions or an independent execution semantics oracle.
The formula checks do not synthesize or replay new witnesses.

## 2. Removed recursive work is not removed response queries

| Case | Original nodes | Ordinary queries left | Analytic queries still returned | Total reachable queries | Original DP transitions | DP transitions left |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FFN 1 layer | 271 | 88 | 98 | 186 | 538 | 128 |
| FFN 2 layers | 1,052 | 247 | 416 | 663 | 5,572 | 365 |
| FFN 3 layers | 3,221 | 442 | 1,410 | 1,852 | 65,254 | 638 |
| FFN 4 layers | 10,834 | 673 | 5,108 | 5,781 | 593,020 | 947 |
| FFN M8, 1 layer | 2,108 | 1,522 | 310 | 1,832 | 3,770 | 2,663 |
| FFN M8, 2 layers | 6,176 | 4,399 | 926 | 5,325 | 22,124 | 15,128 |

The FFN-4 reduction of original DP work is 99.84%, as reported. But 673
excludes analytic terminals by definition. An implementation still returns
5,108 terminal curves, plus 673 ordinary curves. It removes 5,053 original
nodes altogether. Treating 673 as the full number of remaining response
states would conflate replacement with unreachability.

For those 5,108 terminal queries, identical structural arguments reduce to
3,636 distinct formula keys within this archive. Formula evaluation, response
storage, witness construction, and the cost of recognizing eligible states
remain uncharged. Only 10.65% of the original loop-choice counter disappears.
There is no basis here for a 600x wall-time claim or linear scaling of the
whole search with layer count.

## 3. Why the unit-M result has a structural explanation

In the supported chains, contraction feature ranks are distinct along the
chain, and there is at most one elementwise operator between contractions.
At M = 1, a nontrivial common loop must use a feature rank. A loopable span
then contains at most two neighboring contractions, with the finite patterns
`c`, `e`, `cc`, `ce`, `ec`, and `cec`. The exact local responses close the
boundary DP. A streamed private weight carries both of its contraction's
feature ranks, so it adds a leaf operand slot but no **extra** traffic;
its compulsory read remains charged.

For a fixed residency context and fixed capacity, the current finite-pattern
DP has O(n d²) candidate work, where d bounds the number of reachable tile
sizes and the quadratic term covers the two-level `cec` form. This follows
from bounded segment length, two boundary states, and the local formula
enumerations. It is not a bound on the number of contexts requested by an
outer loop or on producing an entire frontier. Scanning every integer
capacity introduces another factor; a breakpoint-based implementation needs
its own cost accounting.

At M > 1, M is common to an arbitrarily long span and every weight lacks M.
The bounded-span argument no longer applies. This explains why a cheap
unit-M response can coexist with many distinct outer retention contexts.
The data locate a remaining source of work; they do not prove that this
source is irreducibly exponential.

The outer-M counterexample in §12 rules out one proposed normal form.
It does **not** prove that every exact M > 1 algorithm must cost as much as
the current grammar search. That sentence should be weakened. The keep-level
matmul model itself still minimizes over ordered keep subsets and reachable
tile states; its correctness checks are not an implementation speed benchmark.

## 4. What the operator projection captures and loses

Within the stated chain grammar, the projection retains each operator's
weight-slice stationarity while dropping inter-operator compatibility.
Private weight traffic and producer-only spill/consumer-only refetch events
provide the proposed disjoint accounting. The result should not silently
extend to shared weights, branching graphs, or different execution grammars.

A small checked example makes the remaining gap explicit. For two dense
contractions `x[4] -> h[4] -> z[4]`, with weights resident, halving tiles, and
three available cells:

| Response | Extra traffic |
| --- | ---: |
| First operator alone | 4 |
| Second operator alone | 4 |
| Sum of operator lower bounds | 8 |
| Exact chain | 12 |

The root grammar curve is `(2,40), (3,20), (5,8)` in total traffic; its
compulsory endpoint traffic is 8. The chain formula and solver both give 12
extra at C = 3. Individually optimal operator responses therefore cannot
simply be added to obtain the chain's exact response. The four-unit gap is
the cost of enforcing a compatible treatment of the intermediate. This is
a post-hoc diagnostic, not a new frozen result or a general additive penalty.

For the two M8 cases, §14's combined ideal exclusions rise from 1,383 to
2,149 and from 3,955 to 5,825. These comparisons use the final parent frontier
as incumbent. A realizable pruning experiment must instead use the frontier
available at each decision, preserve a constructive survivor for ties, and
then recompute shared-DAG reachability. It must also charge the lower-bound
queries. The unit-M terminal projection is a different experiment and does
not supply this missing operator-bound work estimate.

## 5. Integration branch: execution issues precede hardware ranking

The separate [PyTorchSim report](https://github.com/HaoningJiang-space/accelforge-streaming-dse/blob/5245c9cc2eed99ca12618189c2736cb2262ae739/research/dnn_benchmarks/PYTORCHSIM_RESULTS.md)
now contains eight actual GEMM invocations: five numerical passes and three
failures. In these controls, splitting the N subtile isolates numerical
failure; its underlying cause remains unresolved. This is not a universal
claim about N-split mappings.

A separate DMA audit rejects timing even for passing computations. The
expected float32 byte address is `B + 4(O + L)`; the ported pinned backend
expression is `(B + O + 32L + 7) >> 3`. Its predicted transaction counts match
the logged simulator counts. In the tiled passing control, intended read/write
transactions are 3,072/1,024, while logged counts are 3,456/1,216. Numerical
agreement does not validate this timing address stream.

The three generated float arrays also reserve 20,480 bytes for a tile whose
logical tensor sum is 3,584 bytes. These are array reservations, not a full
peak-SRAM measurement. A hardware adapter must explain lane layout and all
additional lifetimes before equating logical cells with physical capacity.
No latency, energy, EDP, or mapping-rank claim is currently accepted.

The [P19 timing report](https://github.com/HaoningJiang-space/accelforge-streaming-dse/blob/5245c9cc2eed99ca12618189c2736cb2262ae739/research/dnn_benchmarks/P19_SERVER_RESULTS.md)
is also negative: the precheck is 15.7%/18.4% slower on the two measured forks,
and all 12 attempts containing the remainder mechanism fail under the stated
memory budget. This distinguishes semantic validity from useful implementation
cost; it does not invalidate the equivalence theorem.

## 6. Recommended next experiment

Implement one opt-in unit-M exact-response substitution with native witnesses,
then compare full curves and replay every returned point. Its recognizer must
check graph incidence and supported patterns, not operator names or operand
insertion order. Require v2, unconstrained solve entry, the declared tile
domain, the boundary residency/ownership contract, and no resident/owned
interior activation. Preserve compulsory-versus-extra accounting. The current
archive recognizer is specialized to registered stacks, not a general graph
validation routine. Group entry remains outside this substitution's contract.

Measure ordinary cache misses, analytic queries and unique keys, truly
unreachable states, end-to-end time, and peak memory, including formula and
witness costs. Use the same grammar and cases for the baseline. Keep the
operator-bound experiment separate until its ordered pruning and shared-work
accounting are available. Repair and revalidate simulator byte addressing and
the numerical failure independently before comparing hardware performance.
