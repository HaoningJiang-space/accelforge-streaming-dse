# Real FFM anchor and finite-capacity family: post-hoc diagnostic

This experiment addresses the fixed-PE, fixed-bandwidth first step. It does
**not** implement a lazy family search, prune any FFM groups, or prove a new
graph working-set bound. In particular, target membership is established only
**after the full shared Join**, so the reported candidate group exclusion did
not save that Join.

## Read-only terminal BranchSummary

[BranchSummary](../../../../accelforge/mapper/FFM/_join_pmappings/branch_summary.py)
is an immutable, conservative summary of two input frames for the final Join
of a two-Einsum search. It preserves the previous nonnegative additive Energy
and Latency lower bound with downward rounding, shared tensor names and input
row counts. If its limited matching-key helper can count compatible pairs it
records the count; otherwise it records `null`, never zero. Missing objectives,
empty/unsupported frames, negative values and nonfinite values yield an unknown
bound. The graph-dependent working-set field is **unknown**.

FFM's opt-in `_terminal_branch_observer` is called before the final compatible
pair is joined. It receives only an immutable summary and cannot alter the input
frames or skip a group. It is a diagnostic hook, not a supported general pruning
API; default searches do not invoke it. The captured shared Tensor names are
structural metadata, not a proof of simultaneous live data. The complete
`BranchSummary` does not yet identify equivalent groups across different target
searches or establish a working-set lower bound.

## One real anchor and independent sampled checks

The anchor is obtained by a normal FFM search for `matmuls(2,4,8)` on NVDLA,
PE `4x8`, 68 B GlobalBuffer. Its search time and subsequent reconstruction /
validation time are recorded, including cold-start effects. The resulting
Mapping ID is then re-evaluated against 68, 72, 80, 96 and 128 B without first
searching those targets; all five physical checks pass with the same re-evaluated
Energy and Latency. Each target is independently searched **afterward** solely
as a reference; the anchor appears in each sampled final FFM frontier. Those
separate full searches are not part of a claimed reuse algorithm, and absence
from a final frontier would mean policy membership is unknown, not necessarily
that the candidate was never generated.

At each sampled point one terminal group is *post hoc* above that anchor's
reported EDP according to the basic cost bound. The corresponding full FFM
search already ran, and no group was skipped. At larger capacities a different
Mapping has lower EDP; the anchor is an upper bound, not the target optimum.
Raw [anchor and reference results](audit.json) include per-stage timings,
physical re-evaluations, all group summaries and re-evaluated target winners.
These single-process observations are not a timed baseline comparison.

## One shared FFM run over 61 integer capacities

A separate diagnostic searches 68–128 B inclusive with FFM's finite-target
Event enumeration and membership bitset. This is one full shared generation and
Join, not 61 independent searches. The 68 B anchor appears in the shared output
for all **61** discrete target memberships. Its upper bound conservatively includes
both the anchor's reconstructed EDP and its FFM-reported costs.

Four terminal union-group summaries are observed. One `1 x 3` input group has
a basic E/T lower bound strictly above that upper bound. Conditional on the
existing shared-enumerator and membership semantics, that same union-group
inequality applies to each of the 61 target projections: a proof over one union
rather than 61 separate full FFM searches. However, its exact matched-pair
count is unavailable; `1 x 3` is an **upper bound** of three pair attempts, not
proof that three pairs were compatible or feasible. The run performs the entire
Join first to discover and verify anchor membership; **actual pruned groups and
avoided work are zero**.

The five independently searched sample points have the same selected reported
best EDP as their shared-search projections. The remaining 56 capacities are
not independently searched, and matching five minima is not a complete-frontier
or mapspace coverage proof. This result is finite-target only; it is neither a
continuous `[68,128]` byte-region theorem nor an architecture-family working-set
certificate. [Shared audit](shared_audit.json) records every capacity, immutable
group bounds, unknown match counts, post-hoc decisions and the reference
comparisons. `working_set_extra` remains `unknown` for every group.

## Validation and next gate

[regression.txt](regression.txt) records the full research/Streaming regression,
including tests that the new observer preserves FFM output and unsupported cost
schemas remain unknown. No new graph working-set certificate, adaptive box
splitting, live production pruning, or timing against the bounded cache is
implemented. In particular, the existing FFM `TensorReservation` and resource
operations may free, merge or de-duplicate storage across the Join; an input
reservation maximum cannot simply be added to another phase's peak.

The next necessary evidence is a stable **pre-Join** anchor-membership witness
and a branch invariant on simultaneous storage that is sound for every legal
completion, then a check whether it excludes any additional real matching pairs
beyond the E/T bound. If those cannot be proven, the correct outcome is unknown
and the original group must run.

## Reproduce

```sh
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
python -m research.tracking_audit.audit_anchor_family --output research/tracking_audit/results/anchor_family/audit.json
python -m research.tracking_audit.audit_shared_anchor_family --output /tmp/shared-anchor-family.json
python -m pytest -q --disable-warnings research/tracking_audit research/streaming_join
```
