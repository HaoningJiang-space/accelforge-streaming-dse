# Graph-cut branch bound: restricted exhaustive prototype

This is a **synthetic, explicitly restricted model** of two connected operations,
not the FFM cost model, not a search over FFM templates, and not a benchmark
against FFM or its cache. It is an initial executable check of the single-cut
certificate only. The default FFM search is unchanged.

## Contract

For one fixed cut, all `live_bytes` represent distinct, dirty producer values
that must be consumed later. They cannot be recomputed, compressed, aliased,
communicated directly to the consumer before the cut, or kept in another storage
level. No transfer is already in flight at the cut. The stated reservation is
simultaneously resident and its space cannot also hold these live values. The
only spill destination is DRAM. Under these conditions each byte that does not
fit needs one DRAM write and one later read. With capacity `C` and concurrent
reservation `r`, the traffic is at least `2 max(0, S - (C-r))` bytes.

The toy model fixes `S` and `r` in each branch; it does **not** yet derive them
from an AccelForge graph, Fusion schedule or Reservation. It also does not add
bounds from multiple cuts. If a certificate's preconditions cannot be established,
this prototype gives no valid pruning argument for that branch.

The model's disjoint mandatory input/output traffic and spill traffic are added;
energy is MAC cost plus per-byte DRAM cost, and latency is the maximum of compute
time and DRAM time. All bounds, EDP comparisons and optional epsilon comparisons
use exact rational arithmetic. The lower bound deliberately omits repeated input
traffic and completion-specific overhead. An incumbent must name a feasible
concrete completion and is independently evaluated before it can close a branch.

`U <= (1 + epsilon) L` permits pruning for a single best-EDP query only. It does
not establish an exact Mapping identity, a complete Energy–Latency Pareto frontier,
or preserve FFM's ordered fallback semantics if inserted inside its enumerator.
Infeasible branches are counted separately from objective-bound prunes.

## Exhaustive finite-grid audit

The 64 synthetic configurations vary capacity, bandwidth and PE dimensions.
The catalog has three streaming windows and three barrier schedules with varying
concurrent reservations; four completion overhead values are enumerated per branch.
Every configuration starts with the same feasible streaming completion. Winners
change among `stream4`, `stream8`, `stream16`, and `barrier-small-reservation`.

| Architecture points | Unpruned completion attempts | Bounded completion attempts | Bound-pruned architecture/branch pairs | Infeasible architecture/branch pairs | Best EDP mismatches |
|---:|---:|---:|---:|---:|---:|
| 16 | 384 | 96 | 16 | 56 | 0 |
| 32 | 768 | 288 | 48 | 72 | 0 |
| 64 | 1,536 | 736 | 128 | 72 | 0 |

The baseline attempt count includes infeasible attempts. A pruned pair avoids
four completion attempts in this toy catalog. Bound evaluation is still done
individually per architecture; `covered_per_branch` records several independently
verified points, not a symbolic region proof. The archived timings are single,
sub-millisecond or millisecond observations, include Python instrumentation,
and must not be interpreted as a speedup or an FFM break-even result.

Every prune is saved with its architecture, branch, feasible incumbent and lower
bound. A separate audit checks all catalog completions, checks each bound and
incumbent independently, and verifies the pruned branch cannot improve the
incumbent. Raw data: [audit.json](audit.json). Tests also compare a separate
byte-by-byte producer/consumer trace and enumerate randomized toy instances;
[regression.txt](regression.txt) includes the existing Attention permutation/Action
regression. These checks are not exhaustive over real hardware or FFM mappings.

## Reproduction

```sh
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
python -m research.tracking_audit.audit_graph_cut_bound --output /tmp/graph-cut-audit.json
python -m pytest -q --disable-warnings research/tracking_audit/test_graph_cut_bound.py research/tracking_audit/test_permuted_join.py
```

Next is to extract and independently verify live byte sets, simultaneity,
reservations and allowed spill/recompute behavior from real FFM Fusion mappings.
Only after proving that connection can a branch certificate be compared with the
normal FFM and cache baselines. In particular, this prototype does not perform
that requested real two-MatMul comparison, measure FFM skipped prefix rows, or
establish a query-count break-even.
