# Conditional residency equivalence: complete joint-state audit

The independent-operator equivalence covers a useful subset of the observed
states, but it does not cover the main producer-containing spans. Both small
six-consumer forks have 106,604 completed cache entries. Only 4,350 of the
58,884 entries in their four largest span/entry buckets satisfy the current
non-scalar independent-solve proof contract. Neither producer-containing
whole-span bucket ever has X externally resident. This last exclusion follows
from the loop grammar, not just the measurements.

Implementation: `5718d46c`; previous evidence: `63ca3bf2`.
Raw joint states, complete frontiers, root witnesses, summaries, failed attempts
and verification records are in [results/residency_states/](results/residency_states/).
This is an exploratory implementation/state-space audit, not a new frozen
P prediction. P21f's protocol, manifest, solver sources and held-out cases
are unchanged; its manifest still verifies.

## 1. What was recorded

`audit_residency_states.py` parses the existing solver and adds a recording
decorator **inside** each existing LRU cache, in memory only. It records each
completed miss once, after obtaining the original return value. No transition,
retention decision, cache key, pruning rule or witness is replaced. The
production `graph/curve.py` file is not edited.

Every row retains the joint state

    (entry, ordered span, extents, external tensors, owned writes, constrained)

and its complete numeric frontier. These are the internal recurrence's
**extra-traffic** frontiers: caller-owned reservations and whole-graph compulsory
transfers are excluded. They must not be reported as standalone physical DRAM
traffic without restoring the boundary charges. Full graph frontiers and
executed witnesses are saved separately in each `run.json`.

Exact DP, historical halving tiles, ownership projection and witnesses are
enabled; name canonicalization and independent splitting are disabled, so the
census sees the original reachable states. `PYTHONHASHSEED=0`. Cases are only
the already-studied tiny fork dimensions `(I,J,K,L)=(2,2,2,2)`, with roles
`kkkkkk` and `kkkiii`. No large P19 workload or P21f case was run.

Two concurrent local attempts capped at 20 seconds stopped after 99,769 and
99,538 completed misses; they remain archived as incomplete. Separate serial
attempts, with unchanged implementation and a declared 40-second cap, completed
in 22.26 and 30.75 seconds including replay. The memory budget was 1 GiB, checked
by sampled peak RSS on this macOS host; observed peaks were below 193 MB. Linux
runs additionally enforce RLIMIT_AS. These instrumented local times include
JSON/gzip recording and are not solver speedup measurements.

## 2. The proved equivalence being measured

Fix the graph, ordered span, current extents, owned-write set, entry kind and
solver options. Also preserve the literal external status of nonprivate
tensors. In a fork, each consumer has private input C_a and terminal output
U_a. Its profile is

    (dimensions(C_a), dimensions(U_a), C_a in external, U_a in external).

Literal rank dimensions retain the k/i reduction-role distinction. Candidate
keys replace the ordered private residency profiles by their multiset, while
keeping every other state field above exact. In all recorded reachable states,
owned writes are a subset of {X}; this was checked explicitly, so no private
ownership distinction is lost by the profile permutation.

**Sufficient condition.** The entry is unconstrained `solve`, at least two
operators are present, the whole-span scalar shortcut does not apply, and
every tensor shared by different operators is already external. The remaining
private tensor sets are then disjoint. The existing independent-operator
decomposition gives

    F_S(C) = F_fixed(C) + sum_rho n_rho f_rho(C),

where each f_rho is the matching singleton **group-entry** response, with the
same boundary accounting. F_fixed covers any fixed producer component. Serial
composition uses max capacity and summed traffic, so each singleton can choose
its optimum within the same available capacity C. Equal type multiplicities
therefore give equal conditional curves for every C, including infeasibility.

The construction realizes the result in the original operator order: assign
each singleton its type's schedule and compose the original-order groups.
It does not authorize changing legal orders or reusing a witness with the
wrong external tensor names. A future memo quotient must reconstruct the
caller-specific witness as well as reuse its numeric response.

Scalar leaves are reported separately because the original shortcut reserves
all live scalar tensors at once. Group entry is also separate: the current
proof invokes solve-entry independent decomposition, not arbitrary entry
substitution. Numerical equality in those diagnostic buckets does not extend
the implemented proof contract.

## 3. Complete census results

| Quantity | All k | kkk/iii |
| --- | ---: | ---: |
| Completed joint states | 106,604 | 106,604 |
| States satisfying the independent-solve condition | 15,185 | 15,185 |
| Candidate classes among those states | 1,508 | 3,429 |
| Repeated candidate keys among those states | 13,677 | 11,756 |
| Classes violating equality under the sufficient condition | 0 | 0 |
| Coupled/constrained states outside that condition | 61,018 | 61,018 |
| Candidate classes in the coupled/constrained bucket | 3,280 | 9,362 |
| Coupled/constrained classes containing unequal responses | **90** | **171** |

The repeated safe keys are 12.8% and 11.0% of the observed total entries.
These are retrospective counts of matching keys, **not** a measured cache
reduction, runtime improvement, or bound on a future optimized execution.
Changing memoization also changes which descendants are evaluated. The counts
do not establish how much time is saved or how they overlap name reuse.

Both cases have the same four largest entry/span buckets:

| Entry / span | States | Independent-solve eligible | X externally resident |
| --- | ---: | ---: | ---: |
| solve / all six consumers | 16,897 | 4,350 | 8,448 |
| solve / producer + all consumers | 16,641 | 0 | 0 |
| group / producer + all consumers | 16,640 | 0 | 0 |
| group / all six consumers | 8,706 | 0 (entry excluded) | 4,352 |
| Total | 58,884 | 4,350 (7.4%) | 12,800 |

Within these four buckets, safe repeated keys number 4,240 (all k) and 3,888
(mixed). The remaining 41,985 non-scalar coupled states are the larger target.
The group-separated bucket has 15,503 states overall and no observed
within-class disagreements in either case; its possible extension requires a
separate argument about group-loop choices, not only the solve-entry formula.

## 4. Why the full producer span cannot satisfy this condition

Let S = (EX,E0,...,E_(m-1)) be the entire fork, entered with no external X.
For both role mixes here, EX uses ranks {I,J,K}, and every consumer uses
{I,K,L}. Consequently the only whole-span loop axes are I and K. X carries
both axes.

The loop recurrence adds to external only tensors **lacking** its chosen
axis. Thus a whole-span loop cannot add X to external. A one-group partition
introduces no new cross-group reservation. A nontrivial partition moves into
proper child spans; recursion never expands a child back into S. Induction
over all routes retaining S therefore gives

    X not in external for every reachable whole-span solve/group state.

Unit extents can remove loop choices or trigger a leaf, but cannot create a
new way to retain X. Ownership of a final write is not external residency.
The 33,281 whole-span entries per completed case contain **zero** exceptions.
This explains why testing arbitrary externally pinned-X interfaces can show
a large conditional simplification while missing these dominant reachable
contexts. The lemma is for this fork grammar and root interface, not for an
arbitrary subgraph supplied with resident X by its parent.

## 5. Parent-adjusted dominance is a separate obligation

For a fixed parent loop axis/tile with r trips and keep choice M, let A_M be
the caller's reservation and D_M its extra refetch/spill charge. The recurrence
compares

    G_M(C) = D_M + r F_sigma_M(C - A_M).

The F terms here use the internal extra-traffic convention of the raw records.
For alternatives at the same parent with compatible continuation interfaces,

    A_1 <= A_2, D_1 <= D_2, and F_1(c) <= F_2(c) for all c

are sufficient for G_1(C) <= G_2(C): F is nonincreasing in available capacity.
Bare child dominance does not establish this result when parent charges or
continuations differ. This audit implements no cross-mask pruning, and the
raw state census alone does not supply every incoming parent transition cost.

## 6. Validation, limits and next target

- Four unit tests pass. They check observer transparency on five tiny graphs,
  exact frontier witnesses and cache/transition counts, entry/ownership/extent
  distinctions, and all 64 private residency patterns of the seen three-consumer
  graph with and without external X. The latter yield 20 histogram classes;
  zero versus two classes contain unequal curves.
- Every completed census has unique full keys and exactly as many records as
  the sum of completed solve/group cache entries. No sampled keys were used
  for the reported complete denominators.
- The all-k root frontier and cache count equal the archived profile. A fresh
  uninstrumented mixed run returns identical root frontier **and witnesses**,
  cache counts, loop-choice count and DP-transition count.
- All seven returned whole-graph frontier witnesses replay with exact peak
  and traffic. This does not independently replay every conditional state;
  such a replay needs its parent reservations, charges and entry context.
- Source hashes, raw-stream hashes, ownership-scope checks and the unchanged
  P21f freeze check are in `results/residency_states/validation.json`.

The next compression target is the coupled producer-containing span, where X
cannot become external. Any proposed signature must preserve the legal
producer/consumer prefix partitions and their conditional loop costs, and
must separate the archived count-profile counterexamples. First prove a
cost-preserving transition relation or a parent-adjusted dominance rule there;
then measure its coverage on these complete joint-state records before adding
an optimizer. No count-only merge is enabled by this audit.

Reproduce from the implementation commit in a fresh output directory:

```sh
python3 -m unittest research.index_coupling.test_residency_states
PYTHONHASHSEED=0 python3 -m research.index_coupling.audit_residency_states \
  --case same6 --out /tmp/residency-same6 --seconds 40 --mem-gib 1
python3 -m research.index_coupling.summarize_residency_states /tmp/residency-same6
```

Repeat separately with `--case mixed6`. Runtime limits are explicit audit
budgets, not performance predictions. For larger shapes use the designated
experiment server with independently recorded bounds.
