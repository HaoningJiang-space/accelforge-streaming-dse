# FFN: executable sharing benefit, native attribution still open

Completed 2026-11-09 on the designated experiment server. This follows the
failed P14-FFN' equality prediction. It changes no frozen prediction, production
curve recurrence, independent executor, or native FFM implementation.

**Positive result:** one FFN M8 D4 F8 schedule executes at 80 B peak and 448 B
DRAM traffic. Keeping exactly that schedule and its reservations, but requiring
separate consumer reads of X and dY, raises traffic to 576 B with the same
80 B peak. All outputs, reduction completion, and no-recomputation checks pass.

**Limit:** 576 B also matches a freshly reproduced native FFM frontier point,
but the native selected source has different storage templates and fails
whole-mapping reconstruction. Numerical equality does not identify its
per-tensor traffic or prove this is the unique reason FFM misses 448 B.

## Execution evidence

The empty-materialization member of `ffm_like_si` is the union's winner at
80 B. It already forbids shared intermediate tensors from being split through
DRAM; all its original shared inputs remain governed by the graph model.
Regenerating this member with witnesses took 159.359 s, under an 8 GiB/600 s
limit. Its three selected traffic values match the archived member exactly.

| Budget B | Executed peak B | Compulsory traffic | Extra input reads | Partial-sum stores + reloads | Total traffic |
|---|---:|---:|---:|---:|---:|
| 80 | 80 | 256 | 64 | 128 | 448 |
| 147 | 140 | 256 | 64 | 0 | 320 |
| 148 | 148 | 256 | 0 | 0 | 256 |

Each execution completes 1,664 arithmetic steps, 3,264 consumer-read checks
and 128 graph-output cell checks. Cells are unit-sized, arithmetic uses exact
Python integers, and elementwise functions retain the existing copy/product
abstraction. These are not calibrated mixed-precision FFN hardware results.

At 80 B, the actual per-tensor transfers are:

| Tensor | Reads | Writes | Partial reads | Partial writes |
|---|---:|---:|---:|---:|
| W1 | 32 | 0 | 0 | 0 |
| W2 | 32 | 0 | 0 | 0 |
| X | 64 | 0 | 0 | 0 |
| dY | 64 | 0 | 0 | 0 |
| Y | 32 | 64 | 32 | 32 |
| dX | 32 | 64 | 32 | 32 |
| dW1 | 0 | 32 | 0 | 0 |
| dW2 | 0 | 32 | 0 | 0 |

H, Z, dZ and dH have no DRAM transfers. The schedule splits F=8 into two
blocks of 4, retains W1/W2/dW1/dW2 tiles over M, and processes M rows. The
first peak contains four 16 B weight/gradient tiles plus four 4 B objects
(H, X, Y and Z): 64+16=80 B. The caller releases and allocates other objects
according to the actual witness; they are not all charged at that first peak.

The outer F split revisits X and dY as inputs and Y and dX as accumulators:
each input is read twice, whereas each output is written twice and reloaded
once. Thus 256+64+128=448 follows from counted transactions, not just the
symbolic recurrence. This is a concrete FFN example of the input-retention
versus unfinished-accumulation tradeoff.

## Fixed-witness sharing ablation

The audit tracks every graph-input cell from first load until its reservation
is released. At 80 B it observes:

| Input | Cell residency episodes | Consumers served by every episode |
|---|---:|---|
| W1 | 32 | EH, EdX |
| W2 | 32 | EY, EdZ |
| X | 64 | EH, EdW1 |
| dY | 64 | EdW2, EdZ |

All four tensors contain 32 cells. X and dY each have two episodes per cell;
each episode serves both consumers. Counting episodes equals the independently
counted input reads.

For the post-hoc ablation, a selected read-only input value is discarded on a
new consumer's first access during that reservation. It is reloaded from DRAM;
the reservation, arithmetic schedule and all other behavior remain unchanged.

| Inputs whose consumers read separately | Peak B | Traffic B | Extra over original |
|---|---:|---:|---:|
| None | 80 | 448 | 0 |
| X | 80 | 512 | 64 |
| dY | 80 | 512 | 64 |
| X and dY | 80 | 576 | 128 |
| W1, W2, X and dY | 80 | 640 | 192 |

All five executions pass the original cell executor's finish checks. This
isolates a 128 B (22.22% of 576 B) traffic saving in this schedule. It is not a
search-speed result, a frozen held-out prediction, or a faithful implementation
of all FFM allocation/copy rules. In particular, this ablation adds no separate
physical buffers for consumers.

## Fresh native comparison and its failure boundary

The upstream environment is pinned to `04cf894e3f33aae6ea9814104a852c160f4d9e25`.
The workload is `ffn_full_copy`, search objectives remain ENERGY|RESOURCE_USAGE,
and one worker searches without detailed post-join evaluation. In 331.651 s it
returns 27 rows and reproduces the entire archived frontier exactly.

At budget 80 B it selects 576 B traffic, with nominal capacity 76 B
(raw float-derived reservation 76.00000408733779). Attempting to build its
whole mapping using the native `_for_model=True` path fails before evaluation:

    ValueError: No matching loop found for [] and
    [Temporal(... rank_variable='d', tile_shape=1, ...)]

The captured template reservations also prevent a misleading interpretation:
CopyX and CopydY place their outputs in GlobalBuffer, while CopyW1 and CopyW2
place theirs in MainMemory. These are stored template annotations, not a
successfully instantiated execution. The native choice is not established to
be the model schedule with X/dY sharing switched off. No native per-tensor
traffic decomposition or physical capacity validation was obtained.

The initial secondary 147 B query used an excessively strict raw-float
comparison and selected a 140 B/384 B row instead of the archive-rounded
147 B plateau. That raw record is preserved but **excluded from plateau
conclusions**. The runner is corrected to use the archive's three-decimal
capacity convention and retain raw capacity. This correction was not rerun;
the primary 80 B result and full archived-frontier reproduction are unaffected.
The model's 147/148 B replay above is independently valid for its own grammar.

## Research consequence

There is now direct execution evidence that a shared DRAM fetch can serve two
FFN consumers and save traffic without changing this schedule's capacity.
The same witness also exposes the competing cost of two partial-sum spills.
This is stronger than a curve-only comparison, but does not finish the causal
classification of all 26 remaining P14-FFN' gaps.

Use these executed policies as concrete interface requirements: residency
summaries must distinguish which consumers can reuse the same physical copy
and at which tile scope. Do not claim a universally minimal interface or an
FFM mapspace exclusion from this one successful plan. P21's fixed-boundary
composition result is complementary; neither result proves state compression.

## Reproduction and records

- Model replay: `80d21c41`, `replay_ffn_shared_inputs.py`; raw results in
  `results/ffn_shared_input_replay/model.jsonl`.
- Fixed-witness ablation: `e8251dbc`, same runner with `--counterfactual`;
  results in `counterfactual.jsonl`. A prior JSON-loading attempt failed before
  any execution because lists needed conversion back to witness tuples; it
  contributes no scientific result.
- Native search/reconstruction: `833ddf80`, `replay_native_ffn_gap.py`;
  `native.jsonl` retains metadata, frontier, errors and compact per-template
  reservations/loops, plus hashes of the original log and template strings.
- `verification.json` records saved-data consistency checks. All expensive
  work ran on the designated server, in isolated pinned checkouts. Active P19
  jobs were not changed.

```sh
python -m research.index_coupling.replay_ffn_shared_inputs
python -m research.index_coupling.replay_ffn_shared_inputs --counterfactual \
  research/index_coupling/results/ffn_shared_input_replay/model.jsonl
# Upstream AccelForge must precede this checkout on PYTHONPATH for:
python -m research.index_coupling.replay_native_ffn_gap
```
