# Index coupling between consumers of a shared tensor

Same operator DAG, tensor shapes and MAC count; only the index that one consumer
contracts differs. `X = AB` feeds `U = XC` and either `V = XD` (same: both
consumers contract X's column index) or `V = DX` (cross: V contracts X's row
index). All matrices are n×n INT8. The graph outputs are U and V.

Frontiers use the Snowcat abstraction of `research/structure_prediction`
(unit DRAM bits, zero-cost buffer, serial, no recomputation) and its replay
checks. `materialized` keeps every tensor in MainMemory with no fused loops.
Reference means the native FFM frontier in this fork's mapspace, not a proof
over all executions.

## Results (capacity B → minimum DRAM bytes)

n=16, so each tensor is 256 B and the algorithmic minimum is 6n² = 1536 B.

| Capacity, B | Same | Cross | Materialized (both) |
| ---: | ---: | ---: | ---: |
| 19 | 8,192 | 8,448 | 8,448 |
| 37 | 5,120 | 5,376 | 5,376 |
| 69 | 3,840 | 4,608 | 4,608 |
| 73 | 3,584 | 3,584 | 3,840 |
| 137 | 2,304 | 2,560 | 3,072 |
| 265 | 2,304 | 2,304 | 3,072 |
| 273 | 1,536 | 1,536 | 2,304 |

- Below 73 B, the cross frontier equals the materialized one. Fusion gives no
  benefit there, while the same-index graph already gains at 19 B. Same holds
  at n=8 (equal up to 19 B).
- Capacity needed for traffic 9n²: same needs n²/2+n+1 B (37 at n=8, 137 at
  n=16); cross needs 69 and 265 B (n²+5, n²+9), about 1.9×.
- Both graphs reach the algorithmic minimum at the same capacity n²+n+1
  (21, 73, 273 B), by keeping X whole and streaming the other operands. So the
  coupling changes the middle of the curve, not its plateau.
- Mechanism (per-tensor actions in `results/n8_*.json`): at n=8 and 37 B, same fuses X
  away and rereads B, C and D twice. Cross also avoids X traffic but spills
  V's partial sums (V written/read 192 B instead of 64). With a shared tensor
  that does not fit in the buffer, one consumer of a cross pair pays either X
  materialization or its own partial-sum spill.

## Limitation found

Adding the join `Y = U ∘ V` (a diamond) makes this fork's FFM fail for **both**
variants at n=4: same raises `No mappings found for EX <--> EU`, cross raises a
missing rank-variable translation (`'k' not found`). This matches the Join
failures on the GPT block (Q/QK) and MobileNet in `research/structure_prediction`.
The research fork is 550 commits behind upstream AccelForge.

### Upstream AccelForge (04cf894e)

`upstream_probe.py` uses only the public upstream API in a separate venv with
one job ([results](results/upstream_probe.jsonl), n=4):

| Case | Upstream result |
| --- | --- |
| same, no join | Same frontier as the fork (96 B at 21 B) |
| cross, no join | Same frontier as the fork (96 B at 21 B) |
| same + `Y` (diamond) | Joins: reaches 80 B (A–D read once, Y written once) at 25 B |
| cross + `Y` (diamond) | Fails: `assert len(my_loop_group) == 1 or len(other_loop_group) == 1` |
| scaled GPT block (fork fails at Q/QK) | Joins: 10-point frontier, 416 B at 50 B, 53 s |

The cross diamond fails in `Nested._merge` (`accelforge/frontend/mapping/mapping.py`),
in a branch marked TODO that assumes rank-variable translation can match the
remaining loops. It is an unfinished merge path, not evidence that no fused
execution exists. Whether 416 B is the GPT block's algorithmic minimum was not
checked.

## Reproduce

```sh
python -m research.index_coupling.run --n 16 --no-join --output /tmp/n16_same.json
python -m research.index_coupling.run --n 16 --cross --no-join --output /tmp/n16_cross.json
```

Each case took about 15 s with one worker on the Linux server.
