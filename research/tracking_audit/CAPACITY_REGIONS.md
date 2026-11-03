# Capacity policy regions: what is proved and what is implemented

## Fixed complete candidates and ordered fallback

Let M be a finite, fixed set of **complete** candidates. Every candidate m has a
fixed integer resource requirement r(m), fixed usage attributes u_j(m), and fixed
thresholds t_j. All other hard constraints have already been applied and do not
vary with capacity C. Initially keep exactly the candidates with r(m) <= C.
For each usage constraint j in the specified order, keep all candidates satisfying
u_j >= t_j if any exist; otherwise keep all candidates attaining the current
maximum u_j. Ties are not broken. No other pruning is interleaved with this policy.

Define s_j(m) = (1, 0) when u_j(m) >= t_j, and (0, u_j(m)) otherwise.
Let s(m) be the tuple of these scores in policy order, compared lexicographically.

**Lemma.** After stage j, the survivors are precisely the feasible candidates
maximizing the first j scores. At j=1 the claim is the definition of the fallback:
all passing candidates share score (1,0), which exceeds every failing score; if
none pass, maximizing (0,u_1) keeps the maximum usage and all ties. Inductively,
all survivors have equal optimal first j-1 scores. Applying stage j maximizes
the next score within that set. This proves the claim for every stage, including
an empty feasible set and zero stages.

Consequently, m survives at C iff r(m) <= C and no candidate q with s(q) > s(m)
is feasible. Put U(m) = min {r(q) : s(q) > s(m)}, with min(empty) = infinity.
The exact policy membership region is therefore **[r(m), U(m))**, or empty when
U(m) <= r(m). Equal-priority candidates never exclude each other. This is a
membership result, not a statement about optimal EDP regions.

`ordered_fallback_regions.py` implements this result by grouping equal scores,
visiting score groups in descending order, and maintaining the minimum resource
of all strictly better groups. The minimum is updated only after emitting a whole
tie group. Sorting takes O(n log n) tuple comparisons, each O(d) in the worst
case; storing scores takes O(nd). The result has one interval or an empty marker
per candidate. This small algorithm is a reference for this restricted policy,
not a replacement for FFM's symbolic enumerator.

The reference requires integer resource inputs and integer capacity queries.
It does not recover bits from normalized float reservations. Tests include
65,535/65,536/65,537-bit boundaries, tied candidates, and an unbounded final
region. An independent direct policy oracle checks 5,832 three-candidate
universes with two fallback stages at four capacities each (23,328 projections).

## Why this does not prove an FFM interval theorem

FFM evaluates constraints while symbols are partially assigned, uses optimistic
bounds, removes completed objectives and performs history-sensitive Pareto
pruning. A candidate's continued existence at a later stage can depend on which
prefixes survived at earlier capacities. The fixed-universe lemma does not
justify replacing those stages with one complete-candidate lexicographic sort.
Nor does it justify enumerating all complete Tiles without FFM's early pruning.

`audit_interval_structure.py` systematically checks 288 programs: all ordered
pairs of six usage expressions, with two cost objectives, four threshold profiles
(including unattainable and mixed thresholds), and a three-symbol divisibility
space bounded by 120. It compares each program at 32 sorted target
capacities with the independent FFM enumerator and observes merged intermediate
cohorts as well as final candidate membership. Results are saved under
`results/finite_intervals/partial_state_audit.json`. All 9,216 projections match
independent FFM. 200 programs execute Pareto; 146 do so before all symbols are
assigned. **Four programs produce noncontiguous final membership.** Thus the
single-interval claim is false for the general existing FFM enumeration policy.

`repro_noncontiguous_membership.py` reduces one witness to three capacities:

- Integer tiles satisfy y divides x divides 120, and z divides 120.
- Resource r=x*z+y, implemented as r/14520; changing capacity is C/14520.
- Ordered usages x/(2*y), then z/(2*x), both with minimum 1 and fallback.
- Retained cost objective x+z. Resource units here are abstract, not physical bits.

| Capacity C | Independent FFM result | Tile (2,1,2) present? |
| ---: | --- | --- |
| 6 | (2,1,2) | yes |
| 10 | (2,1,4) | no |
| 28 | (2,1,2) | yes |

Event enumeration reproduces all three sets exactly. The witness has resource
requirement 5, so it physically fits at all three capacities in this symbolic
program. Its absence at the middle point is policy membership, not feasibility.
The run executes exactly one Pareto call, after two of the three symbols are
assigned. Disabling that call changes the witness's membership to yes/no/no.
This isolates the re-entry to prefix pruning for this program; it does not prove
which other programs admit convex regions or establish a reconstructed-workload
quality defect. No FFM pruning rule is changed by this work.

Every observed cohort in the bounded audit has contiguous target IDs, yet final
rows can have two runs: different surviving states can contribute the same final
Tile in separated regions. A final deduplication must union those regions exactly.
The finite interval backend detects this real FFM hole and retains Bitsets; the
regression checks the hole is not filled by a hull.

A future continuous-region enumerator must preserve the ordered candidate arrays,
dtype, active program position and Pareto history. States with disjoint applicable
regions require a union of intervals, even if some sampled workloads happen to
have single-interval final candidates. Region splits must use exact supported
capacity comparisons; sampling targets and filling gaps is not valid.

## Finite interval backend

`AF_CAPACITY_MEMBERSHIP=interval` is an opt-in representation for **declared target
indices**, sorted by their original normalized capacity labels. It does not
change Tile enumeration or its numeric capacity comparisons.

Every candidate stores two uint32 endpoints [L,U). A shared schema column carries
the memory name and the exact list of declared target labels. Empty membership
is canonical [0,0). In a frame where every row is contiguous, the row payload is
8 bytes regardless of K (K < 2^32). Schema metadata is still O(K). At K<=64 this
has the same row payload as one uint64 word, not a storage reduction.

Join intersects intervals as [max(L1,L2), min(U1,U2)), canonicalizing an empty
intersection. Pareto uses set containment, Lp<=Lq and Up>=Uq for nonempty q,
plus the empty-set case. As in Bitset mode, numeric costs must be no worse and
the original FFM output boundary must agree. Endpoints are never scalar cost
objectives. Equal costs and membership keep the earlier reconstructable source.
Unsupported incremental scalar reducers retain their generic Pareto fallback.

Every input frame is checked for holes. If any row is noncontiguous, that whole
frame retains exact Bitsets. Join or concat between codecs first verifies equal
declared target domains, then losslessly converts interval frames to Bitsets.
Parents are not modified by codec conversion. A domain mismatch, malformed
schema, non-uint32 endpoints or nonzero Pareto tolerance fails closed. The code
never replaces a noncontiguous set by its enclosing interval.

This first backend consumes the existing direct Packed output, scans its target
bits, and optionally compresses it. It still has O(N ceil(K/64)) temporary packed
storage and O(NK) contiguity detection. It is **not** direct event-region generation,
not a K-independent enumerator, and not a process memory bound. Unlisted capacity
queries remain errors. Existing normalized float comparisons, conservative Fusion
filtering, and finite latency scenarios are unchanged.

## Next algorithmic gate

Before offering unsampled capacity queries, define which partial-program
operations admit exact event boundaries and prove projection equivalence for
that subset. Retain multiple intervals and the independent enumerator fallback
when the proof does not apply. Integer physical resource expressions must be
carried from generation; multiplying rounded reservations by capacity is not an
exactness proof. Fusion boundary completeness remains a separate prerequisite
for claims about the original unrestricted Mapping space.
