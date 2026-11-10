# Convergent prefix dominance: local audit and remaining work

The prefix dominance rule is valid and detects real redundancy. In the frozen
one/two-loop census, however, much of that redundancy has already disappeared
at the intermediate solve's Pareto frontier. The remaining identified parent
candidates account for 6.96% and 2.47% of all original Pareto candidates in
the M8 cases. These are candidate counts, not runtime savings or a bound on
what longer-prefix methods could achieve.

The experiment was specified in [PREFIX_DOMINANCE_PROTOCOL.md](PREFIX_DOMINANCE_PROTOCOL.md),
committed and pushed as `3628f51d` before measurement. The decomposition
certificate experiment was deferred before implementation or testing. This
work is on `research/main`; no additional research branch was retained.

## 1. The prefix theorem has a useful simplification

For pure loops over an unchanged operator span, with full conditional start
and end states fixed, the trip multiplier telescopes:

    R = product_v extent_start[v] / extent_end[v].

It does not depend on loop order or the number of loop levels. Ownership
and operator membership remain unchanged along these paths. Ancestor
reservations persist through the suffix, so allocations add; local traffic
is multiplied by the enclosing trip counts:

    (a1,d1,r1) composed with (a2,d2,r2)
      = (a1+a2, d1+r1*d2, r1*r2).

Thus convergent pure-loop prefixes need an `(A,D)` Pareto set, with a common
R. If A1 <= A2 and D1 <= D2, the first prefix dominates for every
nonnegative, capacity-monotone suffix response. This includes infeasibility
by defining the suffix response as infinity below its feasible capacity.
The rule does not apply across different suffix states or general partitions.

All 91,079 start/end buckets in this audit have the predicted common R.

## 2. Frozen local census

The audit reconstructs every loop action from graph incidence and complete
states, including its exact allocation, traffic and trips. Reconstructed
actions reproduce every group frontier and the full baseline loop-choice
counter. Two-loop paths use only an observed zero-cost same-state
solve-to-group bridge. Proper partitions and scalar redirects are excluded.

| Case | Original loop actions | Audited one/two-loop paths | Strictly dominated paths | Duplicate surviving labels | Start/end buckets |
| --- | ---: | ---: | ---: | ---: | ---: |
| FFN M8-1 | 5,578 | 27,730 | 6,646 | 6,242 | 14,842 |
| FFN M8-2 | 15,636 | 72,373 | 17,685 | 16,390 | 38,298 |
| FFN training | 20,881 | 46,450 | 8,508 | 4,144 | 33,798 |
| Mixed-role Fork `kki` | 2,487 | 5,675 | 1,050 | 484 | 4,141 |

Strict dominance is not confined to single operators: the M8 cases contain
2,554 and 8,852 strictly dominated multi-operator prefixes. All strictly
dominated paths in this census have two loops; no original one-loop action
is strictly dominated in its own common-start/common-end bucket. Equal-label
representatives follow enumeration order; selecting a nested representative
instead of an equal direct path is not a recommendation to expand that path
in an implementation.

Every bucket happened to have one nondominated label in this bounded sample.
This does not hold for longer prefixes (§4).

All **52,209** convergent buckets retain exactly the same transformed-child
frontier after filtering. The parent group's full frontier dominates the
audited subset, as it must. These checks preserve the local prefix envelope;
they are not a test of an online solver that deletes these paths.

A concrete multi-operator M8 example is the span `EH0,EZ0`, with Z resident:

- F first, keep X, then M: `(A,D,R) = (32,32,4)`;
- M first, then F and keep the smaller X tile: `(16,32,4)`.

Both reach the same extents, resident set and ownership. Their suffix is
identical; the second prefix has a strictly smaller reservation.

## 3. Map the apparent redundancy back to original work

The following diagnostic was added after the frozen census. For each
strictly dominated two-loop path and each endpoint frontier point, reconstruct
the intermediate `(capacity,traffic)` pair. A pair absent from the
intermediate solve's frontier was already filtered before the original
parent saw it. For pairs that remain, count unique `(first action, child
point)` instances, not the number of expanded provenance paths.

| Case | Strict expanded point instances | Already filtered at intermediate solve | Unique actual parent candidates implicated | Fraction of original group candidates | Fraction of all original Pareto candidates |
| --- | ---: | ---: | ---: | ---: | ---: |
| FFN M8-1 | 9,446 | 6,032 (63.86%) | 2,136 | 22.38% | 6.96% |
| FFN M8-2 | 31,891 | 23,231 (72.85%) | 5,414 | 15.92% | 2.47% |
| FFN training | 13,062 | 11,163 (85.46%) | 1,862 | 4.89% | 0.09% |
| Mixed-role Fork | 1,076 | 744 (69.14%) | 321 | 11.97% | 1.03% |

All implicated parent candidates are indeed absent from their parent's final
frontier. Recovered group candidate counts exactly equal the archived group's
exclusive `pareto_candidates` counters. The last denominator includes
partition work as well as group work.

This is an attribution of candidates that the baseline generates and later
rejects. It is not an implemented way to avoid generating them: identifying
which suffix points contribute currently uses archived child responses.
It also excludes equal-label duplication and prefixes longer than two loops.
It is neither a runtime estimate nor a ceiling on the general prefix method.

Deleting a dominated nested prefix cannot simply delete its first call:
the intermediate solve also contains proper partitions. Its second call
may serve other callers. The current memoization already evaluates each
complete child state once. A correct online restructuring must preserve
these alternatives and charge its own path/label construction costs.

## 4. A native three-loop control needs two incomparable labels

The following analytical control was constructed after the local census.
It is not a frozen held-out prediction. For one GEMM
`Y[M,F] += X[M,D] W[D,F]` with `(M,D,F)=(4,1,4)`, compare:

| Prefix | Loop/retention sequence | (A,D,R) |
| --- | --- | --- |
| Keep W early | M:4→1 keep W; F:4→1 keep X | (5,0,16) |
| Keep W later | M:4→2 refetch W; F:4→1 keep X; M:2→1 keep W | (3,4,16) |

Both start at the same empty-residency group state and end at the same solve
state: all extents one, X and W resident, no write ownership. The suffix
needs one cell for Y and zero extra traffic. Compulsory root traffic is 24.

The complete plans replay at `(C,Q)=(6,24)` and `(4,28)`, respectively.
The independently computed grammar frontier is `(3,36), (4,28), (6,24)`, so
both plans are root Pareto points. Neither prefix can replace the other for
all capacities. The equal-R simplification is valid, but a single canonical
prefix label is not sufficient even for this one-operator example.

Source: [prefix_dominance_control.py](prefix_dominance_control.py).
Evidence: [longer_prefix_control.json](results/prefix_dominance/longer_prefix_control.json).

## 5. Post-hoc chosen-witness state union

The audit tags every selected native conditional-state witness, then strips
the tags before executor replay. Root frontiers and all four archived
exclusive counters remain equal. **46/46** root points replay exactly across
the four cases. This validates the instrumentation and original witnesses;
there is no online prefix-deleting solver in this experiment.

The following table uses `PYTHONHASHSEED=0` for reproducible tie selection:

| Case | States in chosen root witnesses / all cached states | Original DP work attached to that union | Original loop-choice work attached to that union |
| --- | ---: | ---: | ---: |
| FFN M8-1 | 214 / 2,108 | 14.48% | 11.20% |
| FFN M8-2 | 395 / 6,176 | 5.00% | 7.23% |
| FFN training | 172 / 17,225 | 0.66% | 1.54% |
| Mixed-role Fork | 46 / 2,237 | 0.79% | 4.83% |

This union selects one witness per root point, not all optimal witnesses.
Other equal-cost choices change the union; the preliminary runs retain that
variation. Furthermore, a selected state's original exclusive work includes
searching its rejected alternatives. These fractions are neither minimum
witness-generation costs nor achievable pruning rates. They establish that
much baseline work is outside the particular chosen-witness states, without
providing an oracle-free way to identify those states in advance.

## 6. Research decision and timing terminology

The audit supports studying conditional search with resource labels, but
does not justify presenting a two-loop filter as a major M8 accelerator.
Its remaining identified candidate workload is modest, and introducing
explicit path expansion could cost more than the candidates it removes.
The next algorithmic question is whether a shared representation of
`(start, complete suffix state, Pareto(A,D))` can avoid that expansion while
preserving proper-partition alternatives and multiple incomparable labels.
That is a representation problem, not another per-edge bound.

This local result does not prove that global prefix reasoning fails, nor
that a parametric/quotient solver will succeed. A prototype needs a cost
model for constructing and merging its labels before a broad implementation
or hardware benchmark is warranted.

The 6.81x unit-M result is **frontier search speedup**:
`exact_search.once()` calls the solver with `witness=False`. It excludes
native witness recovery. The separate `expand_seconds` measurement in
`run()` includes both recovery and executor replay, and cannot be reused as
an isolated recovery-only timing. A complete mapping-generation comparison
must time witness-bearing search and reconstruction together.

## Reproduction and artifacts

```sh
PYTHONHASHSEED=0 python -m research.index_coupling.prefix_dominance_audit --out NEW_DIRECTORY
python -m research.index_coupling.prefix_dominance_control --out NEW_CONTROL.json
```

- `results/prefix_dominance/run4_seed0`: final deterministic witness control,
  unchanged census and post-hoc parent attribution; per-input/source hashes.
- `run2`: complete frozen census and first witness control.
- `run3`: added parent-candidate attribution; unfixed witness tie seed.
- `run1/FAILURE.json`: initial instrumentation error from mixing private
  witness concatenation sentinels across dynamic modules, fixed by using
  the instrumented module's own `cat`. It is not counted as a replay pass.

The first three cases use existing immutable baseline archives. The Fork
control is freshly collected with the same unmodified recorder. The repeated
runs preserve census and attribution counts; witness unions vary with tie
selection. No default solver, unrelated in-progress files, or frozen
historical conclusions were changed.
