# Explicit physical-enforcer alternatives

This gate extends the complete-materialization 2mm grammar at `1a52d578`.
Source/alias defenses were first pushed as `3204ba0d`. Neither FFM nor the old
research backends change. This is a coverage/composition gate, **not evidence
that adding enforcers accelerates free whole-graph co-optimization**.

## Plan choices and proof scope

`CompletePlan.enforcer` explicitly records `direct` or `spill_reload` and is
retained by JSON source reconstruction. Old direct-only source payloads still
restore using the default `direct`. Unknown or inapplicable paths are rejected.

All endpoint pairs retain their previous direct/identity/staging converter.
Distinct SRAM layouts additionally admit a full **row-major DRAM temporary**:
write the source, release its SRAM owner, allocate the target SRAM owner, reload,
then free the DRAM temporary. This depends on exclusive ownership and exactly
one remaining consumer; it cannot release a shared live source. DRAM capacity,
overlap, partial production, tiled/in-place copies and streaming remain outside
the model. No general converter-path optimizer is claimed.

For an N-byte tensor, standalone demands are:

| Enforcer | SRAM peak | SRAM byte actions | DRAM traffic | DRAM runs |
| --- | ---: | ---: | ---: | ---: |
| direct SRAM relayout | 2N | 2N | 0 | 0 |
| spill/reload | N | 2N | 2N | 2 |

Both pay the declared fixed access energy; spill/reload also pays two setup
costs. Its Oracle executes actual reads/writes, allocation and release rather
than using this formula. The 100-byte example checks both directions and keeps
only the new owner at exit: at C=150 only spill/reload fits. Degenerate equal
row/column packing still follows the declared, conservative layout-tag grammar.

The local replacement argument remains sufficient at the same complete property:
for any fixed endpoint enforcer, the continuation cost is unchanged and max/add
composition is monotone. Apply that argument to each route, then their union.
Lower peak and higher movement cannot be collapsed into a single local EDP.
This does not establish a separator for multi-live or shared-consumer graphs.

## Full-grammar independent validation

Production DP enumerates enforcers after local interface-conditioned frontiers.
The Oracle independently enumerates the extra route and executes every complete
`(producer, enforcer, consumer)` alternative. The validator checks every composed
summary, the complete six-coordinate root frontier, JSON source replay and
post-DP hardware E/T queries at all observed C−1/C/C+1 and B=1,2,3,5,8. It also
checks a direct-only DP against the **independently executed** direct-only subset.
The Oracle still runs with production demand/composition/search imports blocked.

| Graph `(M,K,N,P)` | Cost `(MAC,SRAM,DRAM,setup)` | Direct executions | Spill executions | DP kernel pairs | DP complete alternatives | Root vectors |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| (2,2,2,2) | (1,1,8,1) | 9,216 | 1,152 | 1,554 | 1,682 | 19 |
| (2,2,4,2) | (1,1,8,1) | 20,736 | 2,592 | 3,290 | 3,550 | 54 |
| (1,2,4,3) | (3,11,3,10) | 5,184 | 648 | 660 | 708 | 17 |
| (3,2,1,2) | (11,1,2,3) | 2,304 | 288 | 448 | 484 | 10 |
| (2,3,4,5) | (10,11,7,8) | 20,736 | 2,592 | 3,744 | 4,004 | 82 |

All **1,008 local summaries**, **65,448 complete executions** (including 7,272
spill/reload alternatives), and **5,840 hardware-query E/T fronts** agree.
Kernel-pair counts exclude the route dimension; complete alternatives include it.
The older receipts describe direct-only grammars and are not overwritten or
added as independent coverage. Timing fields remain diagnostics, not speedups.

## Capacity-dependent choice with fixed interfaces

A separate, explicitly constrained case fixes the producer and consumer kernels
for `(M,K,N,P)=(2,1,25,1)`, each with `(ti,tj,tk)=(1,1,1)` and order ijk. The
producer delivers X as SRAM row-major; the consumer requires SRAM column-major.
Their complete demands are independently executed:

| Enforcer | `(u,v,P,E,c,q)` |
| --- | --- |
| direct | (1,1,200,3940,252,304) |
| spill/reload | (1,1,104,5540,254,504) |

The whole-plan peak for spill/reload is **104**, since kernel scratch coexists
with X; its standalone converter peak of 100 cannot replace that full demand.
Both alternatives are Pareto-necessary for this fixed request.

Global binding uses Px=Py=1, C=1..220, B=1..16 and normalized
`H=4·Px·Py+C+3·B`. Independent enumeration of all 3,520 hardware points produces
the same complete H/E/T frontier, **all 401 budgets** and minimum EDPs. The
selected sources are JSON-restored and re-executed on the common hardware.

| Budget | Chosen enforcer | SRAM | B | Used H | E | T |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 150 | spill/reload | 104 | 14 | 150 | 5,540 | 290 |
| 400 | direct | 200 | 16 | 252 | 3,940 | 271 |

This proves a resource-conditioned physical choice in the declared fixed request.
It does **not** show these imposed interfaces are optimal for a freely mapped
whole graph, nor does it turn the normalized price into calibrated chip area.

## Negative result for unconstrained graph search

In **all five** free whole-graph cases, the expanded six-dimensional root vector
set is identical to the direct-only set. No retained root witness uses
spill/reload; **0 of 5,840 queries** has a changed E/T frontier or improved EDP.
The extra route increases intermediate work rather than eliminating it.

This is consistent with the current grammar: SRAM accesses have no layout-specific
cost, and consumer layouts are freely chosen. Matching the producer's SRAM
layout can avoid both relayout paths. No unvalidated layout penalty was added
to manufacture a winner. The finite results do not prove that spill/reload is
useless in a richer model, but they **do not justify expanding the converter
library as a performance research direction by itself**.

Multi-live/shared-consumer interfaces and model-backed layout/architecture cost
dependencies remain separate research gates. Current enforcers preserve only
the one-owner/one-consumer separator; streaming is not the next automatic step.
Hardware budgets still do not constrain local candidate generation.

## Defensive boundaries, receipts and reproduction

`convert()` now validates a live actual source's shape, precision, location and
layout even on identity. `compute()` rejects output/input owner aliasing before
any MAC actions, including disjoint subviews of the same owner. These explicit
rejections do not claim support for in-place computation or general aliases.

- [enforcer_gate.json](results/enforcer_gate.json): all five exhaustive cases,
  direct-only control, unchanged-front results, fixed-interface sources and budgets.
- [enforcer_architecture_gate.json](results/enforcer_architecture_gate.json):
  the expanded grammar also passes the four previous hardware configurations and
  all 452 integer-budget queries. These are separate from the 401 fixed-request
  queries above.
- [enforcer_tests.txt](results/enforcer_tests.txt): **83 passing tests**. This
  includes the previous 62-test set, new source/alias defenses and enforcer tests;
  counts overlap and must not be added. Production FFM regressions were not rerun.

```sh
python -S -m research.joint_synthesis.validate_enforcers --output research/joint_synthesis/results/enforcer_gate.json
python -S -m research.joint_synthesis.validate_architecture --output research/joint_synthesis/results/enforcer_architecture_gate.json
python -m pytest -q research/joint_synthesis/tests --disable-warnings
```

Both JSON receipts record top-level source fingerprints and explicit no-speedup
scope. They establish this finite grammar's correctness, not general graph
co-optimization, FFM mapspace equivalence or an advantage over strong baselines.
