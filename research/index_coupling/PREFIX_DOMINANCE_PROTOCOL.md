# Convergent loop-prefix audit (frozen before measurement)

Scope: grammar v2, serial execution, fixed operator order, exact halving
tiles, spill cost 2, the complete projected conditional cache state. This
audit does not change the online solver or add a branch. It takes priority
over the proposed decomposition-certificate experiment, which has not run.

## Claims to check

A loop action maps a conditional extra-traffic response to
`T[F](C) = d + r F(C-a)`. Two nested loops compose to
`(A,D,R) = (a1+a2, d1+r1*d2, r1*r2)`.

For the same start and end state, with an unchanged operator span and only
loop transitions, `R = product(ext_start / ext_end)` telescopes. Thus R is
identical for convergent paths, including paths of different lengths. A
weakly smaller A and D, with at least one strict inequality, suffices to
dominate a prefix for every nonnegative, capacity-monotone child response.
Equal labels are duplicates; incomparable labels must remain. Different
terminal states are never compared, even if their archived curves coincide.

## Fixed first experiment

Primary cases: `ffn_forward_l1_m8`, `ffn_forward_l2_m8`. Independent rank and
dependency control: `ffn_training_l1`, using the existing v2 call archive.
Also collect a small fresh `fork_kki` archive with the unchanged recorder.
Failures or resource limits will be reported, not silently dropped.

Audit all one-loop and two-loop prefixes starting at each archived group
state. Two-loop paths require an actual zero-cost, same-state solve-to-group
call between them. No proper partition, scalar redirect, ownership change,
or changed operator span may enter a prefix. This is a bounded local census,
not enumeration of all loop prefixes at arbitrary depth.

Recover each action's axis, tile, kept tensors, allocation, refetch/spill
traffic and trip count from the full states and graph incidence. Check every
action against legal tile/retention choices, reproduce each group frontier,
and match the baseline loop-choice count. Merely matching child IDs is not
sufficient. Include all-resident anchors and empty-retention choices.

For each common (start, end), report:

- path count, distinct labels, strict dominance, duplicate labels, and the
  surviving Pareto labels;
- single- versus multi-operator spans, and repeated- versus distinct-axis
  two-loop paths;
- exact equality of the transformed-child frontier before and after local
  label filtering;
- original direct-action counts separately from expanded prefix counts.

No conversion of removed expanded paths into saved cache misses, original
loop choices, or wall time is allowed. Removing a nested prefix does not
authorize deletion of its first edge: the intermediate solve may also choose
a proper partition. Its second edge may serve other callers. An online
prototype needs a complete accounting of these alternatives before applying
the result.

## Post-hoc witness control

On the same cases, tag selected native witnesses with complete conditional
state identities. Strip tags and replay root points; verify root curves and
the four exclusive work counters against the unmodified archive. Report the
union of states appearing in the chosen root-frontier witnesses, and the
original exclusive work attached to those states. This is an attribution of
the existing search, not an achievable pruning rate or minimum witness cost.
Ties select one witness per frontier point; this does not enumerate all
optimal witnesses.

## Timing terminology

`exact_search.once()` times frontier-only `witness=False` search. Its 6.81x
result excludes later native witness recovery. `run()`'s `expand_seconds`
combines expansion and executor replay, so it is not a separate recovery-only
benchmark. Report frontier search and complete mapping generation separately.
