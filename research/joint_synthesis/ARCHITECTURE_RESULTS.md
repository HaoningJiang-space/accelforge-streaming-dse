# Normalized-budget global hardware synthesis gate

This is the next restricted step after `51b53d82`'s independent 2mm composition
gate. The [hardware contract](ARCHITECTURE_CONTRACT.md) precedes the implementation.
No native FFM, `joint_search`, Reservation or legacy pruner code is changed.
After the Oracle invariant fixes, the same four configurations and all 452 budget
queries were rerun in [architecture_gate_hardened.json](results/architecture_gate_hardened.json).
See [ORACLE_REVIEW_RESULTS.md](ORACLE_REVIEW_RESULTS.md) for new shape/precision
coverage; the original receipt below remains historical.
The later expanded converter grammar is reported in
[ENFORCER_RESULTS.md](ENFORCER_RESULTS.md); the unpruned work counts below refer
to this earlier direct-only grammar.

## Actual algorithm

`solve_joint(graph, model, envelope, prices, budget_ceiling)` runs the independent
graph DP once, then binds its complete demands to **one global hardware**. Local
Mapping generation and DP receive no hardware point/list. For a fixed plan,
PE/SRAM are rounded up from required extents/peak; only legal bandwidth choices
under the positive normalized budget are expanded. The result is the exact
`(hardware resource cost, energy, latency)` frontier, with plan/hardware witnesses.

`query_budget(h)` returns the complete E/T frontier and `best_edp(h)` returns an
optimal EDP witness for any integer `0<=h<=budget_ceiling`. These calls perform
no new graph DP or Mapping search. Out-of-range budgets raise; tied numerical
vectors need not return every physical architecture or plan identity.

The cost is `H=4·Px·Py+C+3·B` in the primary configuration. C is bytes, B is
bytes/cycle, and H is **normalized resource-price units**, not calibrated area.
The secondary configuration changes the weights and uses offset/nonunit grids.
The grammar retains complete-X materialization, ideal byte-capacity SRAM,
fixed access/MAC energy and latency `c+q/B`; no streaming, fragmentation, bank
placement, clock/leakage or interconnect effect is introduced.

## Complete independent checks

Two graphs are tested: `(M,K,N,P)=(2,2,2,2)` and `(2,2,4,2)`. For each, the
physical Oracle enumerates all complete plans and executes scalar MACs, packed
copies, allocations and frees. Hardware binding's Oracle then enumerates every
grid hardware point against **all** unique measured demand vectors, without the
production minimum-hardware substitution, price helper or Pareto routine.

| Hardware configuration | Px | Py | SRAM bytes | Bandwidth | Prices `(PE,C,B)` | Ceiling |
| --- | --- | --- | --- | --- | --- | ---: |
| unit axes | 1..3 | 1..5 | 4..48 step 4 | 1..9 | (4,1,3) | 128 |
| offset grids | 1,3 | 2,4 | 3..45 step 3 | 3,5,7,9 | (2,2,1) | 96 |

The four graph/configuration runs have identical complete `(H,E,T)` frontiers
between synthesis and the unpruned full-grid Oracle. Every integer budget below
the respective ceiling is queried **after** compilation: all **452** E/T fronts
and minimum EDPs match, including infeasible budgets.

All **177** returned joint-design witnesses are checked against the same global
hardware, grid membership, exact hardware cost, physical SRAM peak, executed
energy and bandwidth latency. Their sources are JSON-restored and re-executed
with another input seed; 57 source replay instances across configurations may
refer to the same physical plan and are not 57 globally unique mappings.

## Controlled work counts

The same-root grid baseline uses exactly the production root demand vectors,
but scans all hardware points. The unpruned grid baseline uses every unique
observation from complete scalar execution. This separates inverse hardware
binding from earlier graph-frontier pruning.

| Graph | Configuration | Root demands | Full grid points | Same-root feasible bindings | Constructed bindings | Joint frontier |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2×2×2×2 | unit axes | 19 | 1,620 | 17,744 | 171 | 28 |
| 2×2×2×2 | offset grids | 19 | 240 | 1,912 | 76 | 34 |
| 2×2×4×2 | unit axes | 54 | 1,620 | 34,866 | 486 | 58 |
| 2×2×4×2 | offset grids | 54 | 240 | 3,224 | 198 | 57 |

The controlled baseline has 57,746 feasible demand–hardware bindings; synthesis
constructs 931. Both produce the same numerical frontier. The full-grammar grid
checks 2,701,168 feasible **unique-observation** bindings. These are measured work
counts, not full Mapping-search calls, distinct chip counts or speedup ratios.
The physical execution Oracle is intentionally expensive and is not a timing
baseline for a search-performance claim. Diagnostic timings are archived only.

## Hardware actually changes with budget

For the square 2mm in the primary normalized configuration, representative best
EDP witnesses include:

| Budget | Global PE shape | SRAM bytes | Bandwidth | Used resource cost |
| ---: | --- | ---: | ---: | ---: |
| 16 | 1×1 | 8 | 1 | 15 |
| 36 | 1×2 | 20 | 2 | 34 |
| 64 | 2×2 | 24 | 8 | 64 |
| 96 | 2×2 | 24 | 9 | 67 |

Both operators fit each **single** selected array; they do not choose separate
hardware. A test forces producer 2×1 and consumer 1×2 demands and verifies that
the common architecture must provide 2×2, rather than max(total PE)=2.
This toy normalized-budget behavior does not reproduce or replace the known
real NVDLA SRAM/shape-switch experiment. That remains a model-alignment gate.

## Artifacts and scope

- [results/architecture_gate.json](results/architecture_gate.json): all exact
  fronts, budget transitions, source witnesses, counters and source fingerprints.
- [results/architecture_tests.txt](results/architecture_tests.txt): 19 targeted
  tests, including the prior composition tests. Counts overlap with the previous
  11-test receipt and must not be added.

```sh
python -S -m research.joint_synthesis.validate_architecture --output research/joint_synthesis/results/architecture_gate.json
python -m pytest -q research/joint_synthesis/tests --disable-warnings
```

The independent Oracle also runs in a fresh `python -S` subprocess with production
cost/composition/search/synthesis modules and FFM imports blocked. Neither old
FFM's 661-test suite nor a same-model FFM/SENNA/Cache comparison was rerun or
claimed here. General Fusion, 3mm/GLU decomposition, calibrated area/clock models
and end-to-end advantage over realistic co-design baselines remain open.
Hardware budgets are not yet propagated back into local candidate generation
or graph DP. This step reduces hardware-binding work after the graph frontier;
it does not further reduce the existing 1,554/3,290 graph-composition counts.
