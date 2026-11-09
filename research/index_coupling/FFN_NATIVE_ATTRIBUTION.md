# FFN: native reconstruction and the 80 B traffic difference

Completed 2026-11-09. This is an exploratory execution diagnostic following
[FFN_EXECUTION_AUDIT.md](FFN_EXECUTION_AUDIT.md), not a new frozen prediction.
Neither the graph recurrence nor native FFM/model code was modified.

**Result:** reordering independent input copies reconstructs the two selected
native source rows. Native detailed evaluation reproduces both 76 B / 576 B
and 147 B / 256 B. The 128 B traffic difference at the common 80 B budget can
now be decomposed: native extra input reads are 192 B, versus 64 B for the
independently executed graph witness. Both pay 128 B of extra partial-sum
traffic, but spill different outputs.

## Reconstruction failure is order-sensitive

A fresh search at upstream `04cf894e` returned the same 27-row archived
frontier in 337.543 s. Querying with the archive's three-decimal capacity
convention selects the intended 147 B plateau; its raw reservation is
147.00000656835132 B. The 80 B query selects 76.00000408733779 B / 576 B.

Both original source orders fail on the eighth merge, CopyX with CopyW1.
The merger requests one shared loop although this adjacent pair reports
zero. `_from_pmappings` obtains the requested depth from the left subplan's
maximum sharing with **any later** subplan, then merges its immediate neighbor.
In this case that neighbor is an independent weight copy:

| Source budget | CopyX outer loop | CopyW1 first loop | Iterations |
|---|---|---|---|
| 80 B | m, tile 4 | d, tile 1 | 2 versus 4 |
| 147 B | m, tile 1 | d, tile 1 | 8 versus 4 |

The fallback matcher removes the left loop before printing its error, so the
printed empty list does not mean CopyX originally lacked a loop. Nor does a
requested/adjacent depth difference alone prove an error: an earlier merge
with EdZ has depths 2/1 and succeeds. The recorded loop mismatch and successful
alternative orders establish the narrower failure mechanism here.

Only the four independent input copies were permuted; every copy remains
before every consumer. All eight computation einsums retain their order, and
the source per-einsum tiles, storage and reservations are unchanged. These
are legal **new schedules**, not a claim that original reconstruction silently
preserved execution. The native merger and evaluator remain unmodified.

For each of the two source rows, all 24 copy orders were checked:

| Outcome | 80 B source | 147 B source |
|---|---:|---:|
| Fails during reconstruction | 20 | 20 |
| Reconstructs and passes native detailed evaluation | 4 | 4 |
| Evaluated capacity / traffic, identical for all successes | 76 / 576 B | 147 / 256 B |

The successful orders place CopyW1/CopyW2 first in either order, followed by
CopyX/CopydY in either order. All four also agree on per-tensor DRAM traffic.
This closes the missing native-cost attribution for these two rows; it does
not provide an independent cell execution of native mappings or a general
fix to the reconstruction algorithm.

## Which input is reused, and which output is unfinished?

At the common 80 B capacity budget, the native plan uses 76 B and the graph
witness uses 80 B. Each input/output tensor below contains 32 unit-sized cells.
Native copy-input names X_in/dY_in are identified with logical X/dY only for
this traffic table; the underlying physical copies are not merged.

| Tensor | Native reads / writes | Graph witness reads / writes |
|---|---:|---:|
| W1 | 128 / 0 | 32 / 0 |
| W2 | 128 / 0 | 32 / 0 |
| X | 32 / 0 | 64 / 0 |
| dY | 32 / 0 | 64 / 0 |
| Y | 0 / 32 | 32 / 64 |
| dX | 0 / 32 | 32 / 64 |
| dW1 | 32 / 64 | 0 / 32 |
| dW2 | 32 / 64 | 0 / 32 |

H, Z, dZ and dH do not reach DRAM in either evaluated schedule.

The native plan retains X/dY row blocks, splits M=8 into blocks of 4, and
uses F=1 within those blocks. W1 is fetched separately by EH and EdX, 64 B
each; W2 by EY and EdZ, also 64 B each. Its unfinished outputs are dW1/dW2.
The graph witness instead retains F=4 weight/gradient blocks across M,
shares each weight fetch across consumers, and revisits X/dY in two F blocks.
Its unfinished outputs are Y/dX. The latter schedule already has an independent
cell-level execution, including input residency episodes and reduction checks.

| Accounting term | Native | Graph witness |
|---|---:|---:|
| Compulsory reads and final writes | 256 B | 256 B |
| Extra read-only input reads | 192 B | 64 B |
| Partial-sum reloads | 64 B | 64 B |
| Extra partial-sum writes | 64 B | 64 B |
| Total | **576 B** | **448 B** |

Thus 576−448 = (192−64)+(128−128) = 128 B, or 22.22% of native traffic.
This is a comparison at equal allowed capacity, not equal used capacity, and
not a measured hardware speedup. It explains the transaction difference of
these selected schedules; it does not show why the native search did not
return the graph schedule (mapspace restriction versus search pruning).

The earlier fixed-witness ablation disabling X/dY sharing also produced
576 B. That equality was coincidental as a native attribution: native already
shares X/dY and reads each just once. The ablation still correctly establishes
the benefit of X/dY sharing **within the graph schedule**.

## Consequence for the research question

The positive effect is now supported beyond a curve comparison. The useful
distinction is the identity and loop scope of retained inputs/accumulators,
not a scalar amount of shared memory or an aggregate partial-sum penalty.
Two plans pay the same total partial-sum overhead while exposing different
reuse obligations. This supports studying conditional interfaces that retain
those distinctions; it does not yet prove a small or minimal interface.

The native 147 B / 256 B plateau survives detailed evaluation, whereas the
graph grammar reaches 256 B at 148 B. Keep this difference: the graph model
is not an exact representation of the complete native execution space. The
remaining FFN breakpoints are not causally classified by these two examples.

## Reproduction and evidence

In an environment with the pinned upstream ahead of this checkout on PYTHONPATH:

```sh
python -m research.index_coupling.replay_native_ffn_gap \
  --trace-merge --save-sources selected_sources.pkl
python -m research.index_coupling.replay_native_ffn_orders selected_sources.pkl
python -m research.index_coupling.replay_native_ffn_orders selected_sources.pkl \
  --all-copy-orders
```

Only load the snapshot produced locally by the first command. The trusted
snapshot remains on the experiment machine; no pickle or host information is
published. Its SHA-256 links the search to both replay runs. Search used one
worker and an 8 GiB/900 s limit; snapshot replay used 8 GiB/180 s. All commands
finished with exit 0 and empty stderr. Caught reconstruction failures are
reported explicitly, not counted as successful evaluations.

Records in `results/ffn_shared_input_replay/`:

- `merge_trace.jsonl`: metadata, reproduced frontier, before-mutation node
  records, snapshot hash, raw-log and template hashes (`dc2b3669`).
- `copy_order_replay.jsonl`: original/canonical order control (`53c6a553`).
- `all_copy_orders.jsonl`: all 48 source/order trials using the same runner.
- `native_attribution.json`: checked order coverage, per-tensor accounting,
  frontier equality and hashes of the supporting records.

All heavy work ran remotely in an isolated worktree. P19 jobs were not changed.
