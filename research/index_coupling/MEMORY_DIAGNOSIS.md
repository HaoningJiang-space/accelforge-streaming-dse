# Memory diagnosis: recursive caches retain irrelevant context

Status: bounded diagnosis, not a production optimizer change. The original
curve recurrence and active experiment runners were not edited.

## Source and measurement boundary

The measured curve model has SHA-256
`4f5d1183f40632da87d1f8d9212079bfb2acf24efb6521fbae300c6fbd100c99`.
The isolated checkout was `cefab311`; `curve_model.py` and `nest_model.py`
are unchanged between that checkout and `6ade74f7`.

On 2026-11-09, the running P19 workers inherited an address-space limit of
10,240,000,000 bytes (9.54 GiB) **per process**. At one observation the machine
still had about 171 GiB available. Three prior worker failures had reported
MemoryError. Thus the exception is not evidence that the entire machine ran
out of physical RAM. Increasing the limit can postpone this failure without
fixing state growth.

The probe uses the same Python 3.12 environment for both modes, one process at
a time, a 2 GiB address-space cap, a 60 s computation deadline, and hash seed 0.
It records both cache sizes, the number of returned point references stored in
them, maximum frontier length, largest list passed to Pareto, and peak RSS.
Witnesses are disabled in both modes. A 4 MiB emergency reserve is included
in both RSS measurements. Instrumentation timings are not clean benchmarks.
The diagnostic retains cache handles through the final measurement; it does
not measure garbage collection between successive curves in a worker.

## Completed equal-curve comparisons

Every dimension is 4. All consumers contract K. These are diagnostic controls,
not held-out research predictions.

| Consumers | Original cached states | Projected cached states | Original peak RSS (MiB) | Projected peak RSS (MiB) | Final curve points |
|---|---:|---:|---:|---:|---:|
| 2 | 14,393 | 2,675 | 29.18 | 21.97 | 6 |
| 3 | 94,545 | 9,984 | 80.54 | 27.30 | 7 |
| 4 | 568,721 | 37,710 | 419.39 | 49.88 | 7 |

Both cache functions are included in the state counts. The complete numerical
curves agree exactly for all three pairs. In the four-consumer original run,
the two caches store 815,439 point references; the projected run stores 73,621.
These are references across cache values, not an object-identity heap census.

An additional four-consumer ablation projected **only external tensor names**.
It produced the same curve, 37,710 cache entries and 73,621 stored point
references, with 48.03 MiB peak RSS. Thus irrelevant ancestor tensor names alone
explain the state-count reduction in this control. Canonicalizing unused
dimensions is also semantically justified below, but has no additional state
reduction here; it must not be credited with the measured benefit.

For four consumers, the largest cached frontier contains only 11 points and
the largest list supplied to Pareto contains 562 points. This evidence locates
the dominant avoidable growth in the number of memoized subproblems, rather
than a single huge Pareto frontier or a stored execution trace. Temporary
candidate lists remain an additional cost, not the main explanation of this
particular completed run.

Five- and six-consumer runs are separately recorded with their completion or
deadline status. A partial run's RSS or state count must not be compared as
though it completed the same work as another run. In particular, projection
did not make the five-consumer test finish within its 60 s deadline.

## What is unnecessarily distinguished?

The original unbounded keys are `(ops, ext, external)` in both `solve` and
`group_curve`. They carry all graph dimensions and all ancestor-held tensor
names into smaller subgraphs.

For example, a consumer accessing only X, C0 and U0 cannot observe whether a
sibling's U3 appears in `external`. Its local cost does not depend on a J
dimension absent from all of its accesses either. The caller has already
charged the capacity of ancestor reservations outside this subproblem.
Nevertheless the original cache distinguishes these calls.

The diagnostic `project_both` mode changes the *keys and arguments at cache
entry*, leaving the recurrence untouched:

- replace `external` by its intersection with the tensors accessed by `ops`;
- set dimension entries not used by any access in `ops` to a canonical 1.

Tensor identities used by the subproblem are preserved. This is not merging
different physical copies or removing the caller's reservation cost.

### Why this projection fits this recurrence

Fix the graph and the curve options. Let T(O) be tensors accessed by an operator
interval O and D(O) all their index dimensions. Every local tensor set, scalar
leaf check, size, loop-legality test, and traffic coefficient in either function
uses only these tensors and dimensions. New groups O' are subsets of O, so
T(O') is a subset of T(O), and D(O') is a subset of D(O). No descendant can
reintroduce a removed tensor or dimension.

For each partition or loop alternative, the original and projected calls
therefore have the same local choices and charges. Their recursive children
again agree after projection. Induction over the terminating recursion gives
the same numerical frontier. Crucially, indices of *held but accessed* tensors
are retained; only entirely unused dimensions are canonicalized. Implicit
scalar-leaf behavior is unchanged.

This argument is specific to the inspected recursive model. It does not
establish a safe state quotient for native FFM or a changed execution grammar.

## Why the memory still grows

Both decorators use `lru_cache(maxsize=None)`, so all these keys and their
frontiers remain live during a curve. Partition choices, retention subsets,
and tile extents multiply; Python tuples, frozensets, integers, and cache tables
make millions of small states expensive. Separately, `results.extend(...)`
accumulates candidates before sorting/Pareto pruning.

The `max_capacity` option removes result points, but does not itself bound the
number of cache entries. The implementation can still descend into a branch
before applying its capacity filter. Nor does a worker pool share these Python
memo tables across different curve processes.

## Practical conclusion

The small graph does not intrinsically require hundreds of MiB to describe
its tensors. A substantial part of the observed use comes from the chosen
search representation, including provably irrelevant cache context. Correcting
this is an engineering prerequisite for larger experiments, not evidence of a
new graph-search contribution.

Before replacing production runs, validate projected caching on mixed
directions, FFN rewrites, witnesses and the independent simulator. Keep the
frozen P19 criterion unchanged. Full P19/FFN completion and their memory needs
are not established by these small controls.

Reproduce a control on Linux with:

```sh
PYTHONHASHSEED=0 python -m research.index_coupling.probe_curve_memory kkkk original 4 4 4 4
PYTHONHASHSEED=0 python -m research.index_coupling.probe_curve_memory kkkk project_both 4 4 4 4
```

All 11 terminal records, including four deadline outcomes, are archived in
`results/memory_probe/final_records.jsonl`. The probe also emits periodic
progress records during execution. At the last status check, the existing
unmodified P19 pool still had zero completed records and five MemoryError
messages. Its running workers were left untouched.
