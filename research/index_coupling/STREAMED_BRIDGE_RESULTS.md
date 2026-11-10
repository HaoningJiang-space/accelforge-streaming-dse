# An exact non-scalar-X response when loop obligations are already resident

A restricted extension of Scalar-X Bridge is possible in the **existing fixed
operator order**. If every tensor missing an active X axis is already reserved
by the caller, that axis can be streamed at unit tiles without additional local
capacity or extra traffic. When the reduced solve attains the operand-count
bound, the original non-scalar solve has the same one-point internal frontier.

This is a sufficient condition, not a solution for arbitrary non-scalar X.
It matches 565/565 eligible states in four complete small censuses, with 98/98
full parent-frame executions and 69/69 root frontier executions exact. Its
additional coverage and search reduction are small: neither old six-consumer
all-extents-two census contains an eligible non-scalar state. Relative to Scalar-X
Bridge alone, the four new cases lose only 0.27–0.55% of cache entries and
2.24–4.91% of DP transitions. No speed benchmark or general complexity claim
follows from this study.

The implementation and evidence are in [streamed_bridge.py](streamed_bridge.py),
[audit_streamed_bridge.py](audit_streamed_bridge.py),
[test_streamed_bridge.py](test_streamed_bridge.py), and
[results/streamed_bridge/](results/streamed_bridge/). This is exploratory work
with source hashes, not a new frozen prediction. Production `graph/curve.py`,
Scalar-X sources, consumer order and the P21f freeze are unchanged.

## 1. Sufficient condition

Use the standard Fork and the same cost and execution conventions as
[Scalar-X Bridge](SCALAR_BRIDGE_RESULTS.md): an unrestricted `solve` entry on
a contiguous span S of at least two operators, exact pruning, X not external,
and write ownership contained in {X}. Let e be the current recursive extents,
R the caller-resident tensors, and T(S) all tensors accessed in S. Define

    A = {v in {I,K} : e_v > 1},          A nonempty;
    O_v(S) = {t in T(S) : v absent from dims(t)};
    d = max over o in S of |access(o) minus R|.

The residency requirement is

    O_v(S) subset R, for every v in A.

Set I=K=1 to obtain reduced extents e'. One additional condition is required:

1. Some nonexternal tensor is nonscalar at e', so Scalar-X Bridge applies; or
2. Every nonexternal tensor is scalar at e', and |T(S) minus R| = d, so the
   original whole-span scalar leaf itself attains the same bound.

Then the **complete internal** frontier of the original non-scalar solve is

    {(d, 0)}.

Thus the extra-traffic response is infeasible below d and zero at every
capacity at least d. The caller's reservations and compulsory transfers are
excluded. In particular, a one-cell internal response for matrix X does not
mean the entire mapping uses one cell or performs no DRAM transfers.

### Proof within this grammar

Every Fork operator uses both I and K. For each v in A, select the one-group
partition and a whole-span unit-tile v loop. Every nonexternal tensor carries
v, so there is no live tensor in that loop's lacking-axis set. The loop adds
zero reservation and zero refetch/spill traffic. The same condition also
satisfies the internal-producer legality check. Unit tiles are available in
both supported tile domains.

Repeat for the other active axis, if present. Until the last axis is reduced,
X remains nonscalar, so the original scalar-leaf rule does not terminate the
construction early. At e', condition 1 supplies the constructive Scalar-X
response; condition 2 supplies the original scalar leaf. Either child has
capacity d and zero extra traffic. Loop repetition multiplies zero and adds
no capacity, yielding an attainable `(d,0)` at the original extents.

Conversely, a scalar operation requires one local cell for each of its
nonexternal operand/output tensors. Hence every legal mapping needs at least
d local cells; extra traffic is nonnegative. The construction attains both
lower bounds and therefore establishes the whole frontier, not only a plateau
upper bound.

States satisfying these conditions and having equal d have equal internal
numeric responses. Their identities, caller costs and witnesses can differ.
The prototype evaluates the formula without merging cache keys. For parent
alternatives with the same continuation interface, the earlier exact comparison
of `(parent reservation + d, parent extra traffic)` also applies here; comparing
only d or resident counts remains invalid.

## 2. Examples and an essential failure boundary

For `fork(4,2,1,3,'kkk')`, let R={B,C0,C1,C2}. Every tensor lacking I is already
resident. Stream I at unit tiles, then use the scalar bridge to stream the
private J/L axes. The internal response is `(2,0)`; the public conditional
frontier is `(2,44)` after restoring compulsory transfers. In the full two-trip
parent frame, those resident tensors occupy 11 cells, so the observed total
peak is 13 and total traffic is 110, with exact numerical execution.

The dual vector example `fork(1,2,4,3,'kii')`, R={A,D1,D2,U0}, also has internal
response `(2,0)`. A matrix example `fork(3,2,4,3,'kki')` works when every private
tensor is external, leaving only X locally live. Its internal response is
`(1,0)`; the frame's total peak is 78 and traffic is 124. This matrix case
requires strong parent residency, which limits its practical coverage.

The reduced scalar-leaf condition cannot be omitted. Consider

    fork(2,1,1,1,'kkk'), R={B,C0,C1,C2}.

There are no unreserved missing-I obligations and d=2, but the exact response is

| Local capacity | Public conditional traffic | Internal extra traffic |
| ---: | ---: | ---: |
| 2 | 16 | 8 |
| 3 | 8 | 0 |

After reducing I, the mandatory scalar leaf sees five live tensors
{A,X,U0,U1,U2}; it returns capacity five before considering partitions. Other
legal root decompositions achieve the displayed frontier, but none achieves
`(2,0)` internally. Residency/incidence alone does not permit ignoring the
entry and leaf semantics. The prototype explicitly rejects this case and
preserves its two-point curve.

## 3. Coverage and implementation work

The two existing raw six-consumer censuses each contain 106,604 states and zero
eligible states for this **new non-scalar** rule. This does not affect the
29,067 eligible scalar-X states already reported for each census.

New exploratory roots use J=L=2. All completed baseline solve/group cache
misses were observed, with observer count equal to cache size. All eligible
conditional responses and all three variants' root witnesses are archived.

| I,K,roles | Baseline entries | Eligible non-scalar solves | Wrong predictions | Eligible on full producer span |
| --- | ---: | ---: | ---: | ---: |
| 4,2,kkk | 4,199 | 54 | 0 | 16 |
| 4,4,kki | 8,024 | 117 | 0 | 33 |
| 4,2,kkkk | 15,389 | 126 | 0 | 32 |
| 4,4,kkii | 30,374 | 268 | 0 | 65 |

The new rule is composed with Scalar-X Bridge, so its incremental contribution
must be measured against that prototype, not entirely credited with the
existing scalar shortcut's savings.

| I,K,roles | Scalar / extended cache entries | Scalar / extended DP transitions |
| --- | ---: | ---: |
| 4,2,kkk | 3,761 / 3,741 | 12,499 / 11,885 |
| 4,4,kki | 7,586 / 7,544 | 31,038 / 29,733 |
| 4,2,kkkk | 13,590 / 13,553 | 75,238 / 73,130 |
| 4,4,kkii | 28,575 / 28,499 | 195,743 / 191,351 |

All baseline, scalar and extended full curves agree. The 69 saved root
executions are exact. This is a profiled work census, not controlled timing;
regression tests ran concurrently, and stored wall times have no speed claim.
Each fresh case had a 20-second cap covering all three variants and their
replays, with a 1-GiB memory cap (sampled peak RSS on macOS; also RLIMIT_AS on
Linux). All four completed. The audit took about 13 seconds overall.

## 4. Execution and guard checks

Eight vector/matrix shapes, including odd and non-power-of-two extents, supply
98 residency cases: all supersets of the required missing-axis tensors for
those shapes. Their conditional frontiers agree with both original enumeration
and original DP. Each theorem witness is then executed inside a full parent
frame that actually reserves R, including resident outputs accumulating across
two parent-loop trips. All 98 peaks, traffic totals and numerical outputs agree.

For multiaxis resident tensors, final copy loops in the framing witness have
explicit singleton-group nodes between loop levels. This extends the old
scalar-only test helper in the new test module; the old helper and its archived
source hash remain unchanged.

The combined regression suite has 19 passing tests. It covers the scalar-leaf
counterexample, root and group entry, constrained cuts/partitions, capacity
caps, ownership, alternate cost options, tile domains and unsupported graphs.
The in-memory AST wrapper retains the original scalar leaf before both guarded
shortcuts. No production default is enabled.

```sh
python -m unittest research.index_coupling.test_streamed_bridge \
  research.index_coupling.test_scalar_bridge \
  research.index_coupling.test_residency_states research.index_coupling.test_p21f
PYTHONHASHSEED=0 python -m research.index_coupling.audit_streamed_bridge \
  --out /tmp/streamed-bridge-audit --seconds 20
```

## 5. Remaining mathematical problem

This establishes an exact non-scalar response when the parent has already paid
every missing-axis obligation. The difficult regime is precisely where some
of `O_v(S) minus R` remains: streaming then adds reservation or refetch/spill
traffic, and competing axis/partition choices need not attain the same bound.

The next useful step is to derive a response for one unresolved obligation,
with its full simultaneous reservation and repetition costs, and compare it
against alternate partitions. Merely inserting those costs into the displayed
construction gives an upper bound until a matching lower bound is proved.
Coverage of dominant spans must accompany that derivation; this study's small
incremental reduction is evidence against presenting zero-obligation streaming
as the general Fork solution.
