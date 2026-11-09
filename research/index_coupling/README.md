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
- Capacity needed for traffic 9n²: same needs n²/2+n/2+1 B (37 at n=8, 137 at
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

## Held-out test of frozen predictions

Predictions in [PROTOCOL.md](PROTOCOL.md) were committed before these runs
(P3′ was added mid-run, before any output was read). Scores from
`evaluate.py` are in [heldout_scores.json](results/heldout_scores.json).

| Prediction | T1 square 32 | T2 64·8·8·8 | T3 8·32·32·32 |
| --- | --- | --- | --- |
| P1 equal plateau | pass (1057 B both) | pass (201 B both) | pass (265 B both) |
| P2 plateau location | pass (exactly 1057) | pass (201 ∈ [192, 321]) | pass (265 ∈ [256, 321]) |
| P3 transfer law, as frozen | fail at 1 of 5 points | pass (7 points) | pass (1 point) |
| P3′ narrower law | pass (2 points) | pass (4 points) | no applicable point |
| P4 cross onset 273 B | pass | — | — |

- P3's T1 miss is the failure mode already seen in training: at 273 B the same
  graph itself spills U and V, so the cross graph matches it (14,336) instead of
  paying the predicted extra (15,360).
- The sign of the cross penalty depends on shape. In T2, cross is better than
  same at 3, 4 and 7 B (for example 25,664 vs 26,112 at 3 B); in T3, cross is better at
  137 B (4,864 vs 5,120). The plateau is identical in every case.
- P1, P2 and P4 need no mapping search. P3/P3′ transfer the same-index
  frontier to the cross graph, so they still need one graph search.
- All values are this fork's FFM mapspace on the abstract Snowcat, not an
  independent proof; each case took 15–17 s.

## FFN training step on upstream FFM

`ffn_train.yaml` is one FFN layer: forward, backward and both weight gradients.
X (H = X·W1 vs dW1 = Xᵀ·dH) and Z (Y = Z·W2 vs dW2 = Zᵀ·dY) are cross pairs.

Two upstream modeling issues had to be handled first:

- **Shared graph inputs under Snowcat.** Snowcat's MainMemory keeps
  `~Intermediates`, so a graph input is backed in DRAM, and the join sums each
  consumer's read energy. A graph input read by two einsums is therefore charged
  once per consumer. (Upstream FFM does treat multi-einsum inputs as fusable;
  this is the architecture spec's backing policy, corrected after review.) In
  the minimal case `U = X·C, V = X·D`, the unlimited-buffer minimum is 96 B
  instead of 80 B. Wrapping the input in a copy einsum (as upstream's GPT
  workload does for `I`) makes it an intermediate and gives 80 B.
  Without copies the FFN minimum is 384 B; with copies it reaches the algorithmic 256 B.
- **Detailed re-evaluation crash.** With copies, X and dY become cross-index
  shared intermediates. The join completes, but FFM's post-join detailed
  evaluation crashed with `ValueError: No matching loop found` in
  `Nested._merge` (FFN; reproduce with `upstream_probe.py ffn_full_copy`). Running with
  `eval_in_detail=False` returns the joined frontier. On `shared_input_copy`,
  joined and detailed values agree row for row; the FFN values are not replayed.
  The cross diamond `Y = U∘V` also joins this way and reaches the 80 B minimum at
  37 B, versus 25 B for the same-index diamond, so with a join the plateau differs.

Frozen predictions (PROTOCOL.md) for two held-out shapes, from the single-nest
resident sets R_m = 4·D·F (weights and gradients) and R_f = 4·M·D (activations
and their gradients):

| Case | M·D·F | R | Plateau | P5 reaches minimum | P6 plateau in [R, 1.25R] |
| --- | --- | ---: | ---: | --- | --- |
| F1 token-heavy | 16·4·8 | 128 (R_m) | 147 B | pass (384 B) | pass (≤ 160) |
| F2 hidden-heavy | 4·4·16 | 64 (R_f) | 81 B | pass (320 B) | **miss by 1 B** (> 80) |

P7 (which resident set) is only indirectly supported: each plateau is below
the other set's size (256 B in both cases). F1's plateau equals the M=8
calibration's 147 B, consistent with weight-resident streaming being
independent of token count. Each run took about 6 minutes with one worker.

## Nest model (no FFM search)

`nest_model.py` predicts the plateau (minimum buffer with zero extra DRAM
traffic) without running FFM. It exhaustively minimizes over a restricted
model of recursive loop nests: a tensor that lacks the current loop index, or
is used by several sibling groups, stays whole; a loop must be iterated by
every einsum in its group; a copy and its source share one reservation and the
copy's position in the einsum order is ignored. The minimum is over this model,
not over all legal mappings. Each prediction takes well under a second.

| Set | Points | Exact | Within 1 B | Worse |
| --- | ---: | ---: | ---: | --- |
| Calibration (seen before writing the model) | 9 | 7 | 9 | — |
| Held-out C1, C2 (coupling) | 4 | 4 | 4 | — |
| Held-out F3, F4 (FFN training step) | 2 | 0 | 1 | F4: FFM 153 vs model 149 |

Frozen P8 (exact) passes 4 of 6 held-out points; P8′ (within 2 B) passes 5 of
6. The 1 B gaps where FFM is below the model are unexplained; no buffer element
has been identified. F4 is the opposite: FFM's saved frontier needs 4 B more than
the model's best nest (printed by `plateau(ffn(16, 8, 4), witness=True)`). This
does not prove FFM cannot express 149 B. The review's hypothesis is copy order:
`CopydY` is first in the einsum order, so the dY row stays live from the start;
adding that lifetime to the model gives exactly 153 B and leaves F1–F3 unchanged.
P9 in PROTOCOL.md tested it by moving the copy just before EdW2: F4 dropped
only from 153 to 152 B, not to the predicted 149 B (P9 fails), while F1 stayed
at 147 B (P9′ passes). Copy order accounts for at most 1 B of the gap; the other
3 B remain unexplained. The probe's JSON omits mapping witnesses, although
no-detail FFM objects retain per-einsum mappings, so the next step is to extract
F4's per-einsum mappings. The uncopied shared-input run is now saved with its
DRAM breakdown (X read twice, 32 B, total 96 B; with the copy X_in is read once,
80 B): `results/late_copy_and_shared_input.jsonl`.

The first version of the model let an einsum sit inside a loop over an index
it does not iterate, i.e. recompute it. That gave the same F4 value of 149 and
was fixed; no other prediction changed. Full table: `results/nest_scores.txt`.

## Attention core and real-size application

Frozen attention-core predictions (PROTOCOL.md, P10/P10′) all match FFM
exactly, with FFM's detailed evaluation enabled: 74, 56 and 56 B for A1–A3
(`results/attention_heldout.jsonl`). The model's nests are the FlashAttention
dataflow when queries are many (query-outer, K and V resident) and a key-outer
dataflow with Q and O resident when keys dominate.

`real_scale.py` applies the model at GPT-3 6.7B sizes (bf16;
`results/real_scale.txt`). These numbers are model outputs only; FFM cannot
check them at this size.

| Workload | Plateau (zero extra DRAM traffic) | Resident set |
| --- | ---: | --- |
| FFN training step, 2,048 tokens | 64 MiB | X, Y, dY, dX (loop over FFN hidden) |
| FFN training step, 16,384 tokens | 512 MiB | same (tie with weights) |
| FFN training step, 32,768 tokens | 512 MiB | W1, W2, dW1, dW2 (loop over tokens) |
| Attention prefill, 2,048 tokens, one head | 1 MiB | K, V |
| Attention decode, 1 query, 32,768 keys | < 1 KiB | Q, O |

The resident set switches at tokens = FFN hidden size (min(4·M·D, 4·D·F)) for
the FFN step, and at queries = keys for attention. Limits: only the zero-extra-
traffic point is modeled, not the capacity-traffic curve below it; online
softmax statistics, heads, projections and GQA are omitted.

## Capacity-traffic curve model

`curve_model.py` extends the nest model from the zero-extra-traffic point to the
whole Pareto curve: a tensor may be refetched (inputs, (T−1)·size per loop) or
spilled (accumulated outputs, 2·(T−1)·size) instead of kept, sibling groups may
pass a tensor through DRAM, and loops split by powers of two. It enumerates this
restricted model; it is not a lower bound and does not run FFM.

Compared with every saved FFM frontier (`compare_curves.py`,
`results/curve_comparison.txt`): **216 points over 19 graphs, 206 equal, 10
where the model is lower, none where it is higher.** Only n=4 and n=8 coupling
were inspected while writing the model; the rest were not used to build it but
also were not frozen predictions.

Codex's independent element-level simulator (`simulate_nest.py`,
REVIEW_NOTES_2.md) executed the model witness at all 216 points, checking
every dependence, and reproduced the model's peak buffer and DRAM traffic
exactly at every point. No accounting bug was found. The 10 lower points:
- **Cross coupling, 6 points (n4, n8, n16, T1, C2 ×2): excluded by FFM's
  representation.** The witness fuses X into EU while also writing X to DRAM
  for EV (write-through). FFM shares a tensor between einsums only through its
  first (backing) reservation, so one tensor cannot be both a buffer tile for
  EX/EU and a DRAM channel for EV (source lines in REVIEW_NOTES_2.md, fork and
  upstream). The saving is 5.6% of traffic for the square cases and 0.9–1.5%
  for C2.
- **Attention core, 4 points (32 B each): executable but unresolved.** The
  most likely cause is FFM's default of one fused loop per rank variable, but
  no rejected template has been shown.

On the FFN training step (`results/curve_comparison_ffn.txt`), FFM's saved
frontier repeats some capacities with dominated values; against FFM's best at
each capacity the model is lower at 19 of 20 distinct capacities by 32–96 B and
higher only at 147 B (the plateau, model 148). The simulator executed the
model's witness at 7, 19, 57 and 140 B and reproduced its buffer and traffic
exactly (`results/ffn_simulated.txt`); e.g. at 140 B the model needs 320 B of
DRAM traffic versus FFM's 384 B. The mechanism behind these FFN gaps has not
been classified; write-through of FFN's many multi-consumer tensors is the
leading hypothesis, not a finding.
