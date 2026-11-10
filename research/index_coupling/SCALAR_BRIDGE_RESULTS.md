# A scalar shared X gives an exact conditional response

There is a useful coupled-state equivalence even when X is **not** externally
resident. If the current X tile is one scalar, an unconstrained fork solve can
retain it internally, run the operators in their original order, and attain
zero internal extra traffic at the operand-count capacity lower bound. The
original whole-span scalar-leaf shortcut must take precedence.

This rule matches all 29,067 eligible states in each of the two complete
six-consumer tiny-fork censuses. An opt-in implementation reduces cache entries
from 106,604 to 77,507 and DP transitions from 1,659,790 to 310,639, with equal
whole curves and exact witness execution. The production solver and frozen
P21f sources are unchanged.

Implementation was committed as `c6150950` before measurement. Evidence is in
[results/scalar_bridge/](results/scalar_bridge/). This is a proved restricted
grammar rule with retrospective checks and implementation experiments, not a
new frozen P prediction or a global mapping optimality claim.

## 1. Exact scope and response

Consider a contiguous span S of the standard ordered fork, either containing
EX first and a consumer prefix, or containing consumers only. EX computes
X = AB; consumers have either the k or i role. Private inputs and outputs
belong to single operators; outputs are terminal in the full fork. There are
no aliases, recomputation, overlap or bank constraints.

Fix extents, external residency R and write ownership W. The theorem's case is:

- `solve` entry with all singleton cut positions available;
- I=K=1 at the current recursive extents, so |X|=1, but X is not in R;
- default exact cost rules, with W a subset of {X};
- at least two operators, and at least one nonexternal tensor is nonscalar.

The final condition excludes the original whole-span scalar-leaf rule. In that
rule the recurrence returns the number of **all** nonexternal scalar tensors,
without considering partitions. Replacing it by a serial schedule would change
the declared grammar. The prototype preserves it literally.

Let

    d(S,R) = max over o in S of |access(o) minus R|.

Every operator accesses X, so d counts one X cell plus its nonexternal private
operand/output cells. Under these conditions the complete internal response is

    F_(S,ext,R,W)(C) = infinity, C < d;
                       0,       C >= d.

Equivalently, its internal frontier is the single point `(d,0)`. The traffic
coordinate is **extra traffic**, excluding compulsory transfers and caller-owned
external reservations. It is not a claim of zero physical DRAM traffic.

### Lower bound

The model charges a separate cell for every nonexternal tensor accessed by an
operator's scalar computation. No schedule in this grammar can execute that
operator with capacity below its number of nonexternal operands and output.
Taking the maximum over operators gives C >= d. All extra read/write charges
are nonnegative under the stated cost rules, so extra traffic is at least zero.

### Matching construction

Choose the singleton partition of S and retain X across its groups, reserving
one cell. If EX is present, execute it first. Its remaining private operands
vary only over J because I=K=1; stream scalar J tiles and finish the X reduction
before running consumers. Each consumer's remaining private tensors vary only
over L. Stream scalar L tiles while retaining the same X cell. Unit tiles are
available in the historical halving domain for every positive integer extent.

All live private tensors carry their operator's streaming axis, so no private
tensor is refetched or spilled by that loop. X is retained by the singleton
partition, so it introduces no intergroup transfers. The private peak of each
operator is its number of nonexternal private tensors; adding the one X cell
and taking the serial maximum yields exactly d. Ownership of X's final write,
if any, remains with the caller under the existing convention.

This realizes both lower bounds in the original operator order. Hence all
states satisfying the conditions and having equal d have equal **internal
numeric responses**, although their external allocation, compulsory transfers
and tensor-specific witnesses can differ. The prototype evaluates this formula
per existing state; it does not rename or merge cache keys.

For example, `fork(1,3,1,6,'kkk')` with no external reservations has d=3. Its
whole-graph minimum is 42 bytes of traffic at capacity 3, after restoring the
graph's compulsory transfers.

## 2. Exact parent-adjusted dominance for these children

At a fixed parent loop, let M reserve A_M cells, incur D_M extra traffic and
repeat the child r times. The child theorem gives the parent alternative

    (capacity, extra traffic) = (A_M + d_M, D_M).

Thus for alternatives with the same parent/continuation interface, candidate
1 weakly dominates candidate 2 exactly when

    A_1 + d_1 <= A_2 + d_2  and  D_1 <= D_2.

The repetition factor multiplies zero child extra traffic. This is a concrete
two-coordinate dominance condition; comparing d alone would still omit the
parent's costs. The prototype leaves existing parent Pareto pruning intact.
It does not yet eliminate the exponential parent mask enumeration in advance.

## 3. Coverage in the complete recorded state space

`audit_scalar_bridge.py` reads the saved full joint states without running a
new search. Both datasets have 106,604 entries and 29,067 eligible solve states;
all 58,134 comparisons exactly match `(d,0)`. In each dataset:

| Span | Eligible solve states |
| --- | ---: |
| EX and all six consumers | 16,383 |
| EX and the first five consumers | 4,095 |
| All six consumers, without EX | 4,095 |

Other shorter spans account for the remainder. Among the full producer-span
eligible states, 2,186 have d=2 and 14,197 have d=3. These are precisely states
that the externally-resident-X independence theorem did not cover.

The audit also clarifies a previous count-based impression: 16,383 of the
16,640 **group-entry** states on the complete producer span are infeasible,
while 16,384 of its 16,641 **solve-entry** states have a one-point response.
The group has no active common loop axis once I=K=1, whereas solve can partition
EX from the consumers. Many equal group responses are therefore empty curves.
Raw cache-entry counts must be supplemented by entry kind and feasibility;
they are not a count of equally expensive distinct optimization problems.

## 4. Conditional witnesses are executed inside a real parent

The new tests do not pass an unsupported `external` argument to the standalone
simulator. They construct a complete framing graph:

1. Each resident tensor is also consumed by a final copy, allowing a real root
   partition to hold it across the tested span.
2. Nonresident tensors carry an added T axis of extent two. Resident outputs
   accumulate across T; inputs are reused from the parent's reservation.
3. A T loop enters the intended child solve at T=1. The singleton-X witness is
   inserted there, then the final copies execute.

The expected whole peak is the sum of parent reservations plus d. Expected
whole traffic is the framing graph's compulsory transfers. For both `kkk` and
`kii` with `(I,J,K,L)=(1,2,1,3)`, all 256 private residency masks were considered.
The one fully resident scalar-leaf mask per graph is excluded from this rule;
the other **510 complete framed executions** reproduce the predicted peak,
traffic and numerical outputs exactly.

Additional tests compare both DP and enumeration on six shapes, including
non-power-of-two extents, and replay their returned whole-graph witnesses.
Guards cover group entry, constrained cuts/partitions, external X, ownership,
capacity caps, approximate grids, alternate cost flags and non-fork graphs.
Together with existing residency and P21f tests, all 16 tests pass.

## 5. Fresh-process implementation measurements

Cases are `(2,2,2,2,kkkkkk)` and `(2,2,2,2,kkkiii)`, not the larger P19 shapes.
Baseline and prototype use exact DP and witnesses, with name canonicalization
and independent-operator splitting disabled. Each job has a 40-second wall
budget and a 1-GiB memory budget (sampled peak RSS on macOS; Linux also uses
RLIMIT_AS). Compilation of the in-memory prototype occurs before search timing.
Jobs run serially with `PYTHONHASHSEED=0` in fresh processes. The three unprofiled
pairs alternate baseline/bridge, bridge/baseline, baseline/bridge. A separate
profiled pair supplies deterministic state/transition counts, not timing ratios.

All 16 jobs completed, with equal frontiers within each case and **56/56 exact
root witness replays**. Unprofiled search timings in seconds:

| Case | Baseline runs | Prototype runs | Ratio of medians |
| --- | --- | --- | ---: |
| all k | 9.824, 10.903, 11.023 | 3.364, 2.872, 7.133 | 3.24x |
| kkk/iii | 9.738, 10.732, 14.747 | 2.994, 2.833, 2.920 | 3.68x |

These are local measurements without fixed CPU affinity or exclusive machine
use. The variation, especially the 7.133-second prototype run, is preserved;
no general speed guarantee or large-P19 speedup follows from three pairs.

The profile counts are identical across the two role cases:

| Quantity | Baseline | Prototype | Reduction |
| --- | ---: | ---: | ---: |
| Cache entries | 106,604 | 77,507 | 27.3% |
| DP transitions | 1,659,790 | 310,639 | 81.3% |
| Loop/retention choices | 141,027 | 126,561 | 10.3% |

The formula is used 29,067 times per run. It avoids downstream partition work;
most outer retention choices remain. Memory reduction is much smaller than the
transition reduction, so this is not a demonstrated cure for exponential mask
growth. Larger X tiles and general positional residency remain unresolved.

## 6. Reproduce and continue

The opt-in wrapper parses the existing source, inserts the guarded formula
**after** the original scalar-leaf rule, and compiles in memory. The source
hashes of the production solver and P21f freeze still verify. No production
default, graph order or frozen prediction was changed.

```sh
python3 -m unittest research.index_coupling.test_scalar_bridge
python3 -m research.index_coupling.bench_scalar_bridge \
  --out /tmp/scalar-bridge-bench --seconds 40 --mem-gib 1 --repeats 3
```

All source hashes, per-job records, preserved witnesses, paired ordering and
derived checks are in `results/scalar_bridge/`. The next useful tests are
bounded larger-fork measurements on the experiment server and an extension of
the parent cost-pair reasoning to |X|>1. Neither has been completed here.
