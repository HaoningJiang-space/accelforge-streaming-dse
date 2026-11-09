# Review request: index coupling and the nest model

Please check the claims below independently. Report disagreements with file,
line and a reproducing command. Do not change `PROTOCOL.md` predictions; add
findings in a separate `REVIEW_NOTES.md`.

## Claims to check

1. **Nest model correctness** (`nest_model.py`).
   - Brute-force check: for tiny graphs (e.g. coupling with all sizes 2, and a
     two-einsum chain), enumerate loop nests directly and confirm `plateau()`
     returns the true minimum of the model as defined in its docstring.
   - Check the memoization key `(ops, sliced, external)`: can two calls with
     the same key need different answers?
   - Check the cross-group rule: a tensor touched by two groups is kept whole
     from first to last group. Is "whole at the current slice granularity" the
     right size when an outer loop already slices it?
2. **Model vs FFM mapspace.** The model is constructive, not a lower bound.
   Find a case where FFM's plateau is more than 2 B below the model, or where
   the model's best nest is not expressible as an FFM mapping. The calibration
   FFN cases (M8/M16, D4, F8) differ by 1 B (model 148, FFM 147): identify
   which buffer element FFM saves.
3. **Copy-as-alias assumption.** Confirm in AccelForge source that
   `is_copy_operation` einsums reserve no buffer and only make a tensor
   shareable, in both the research fork and upstream `04cf894e`.
4. **Shared graph inputs.** Confirm that FFM treats only intermediates as
   shared between einsums (`make_pmappings.py`, `intermediate_tensors =
   input_tensors & output_tensors`), so `shared_input` reads X twice (96 B)
   while `shared_input_copy` reads it once (80 B).
5. **No-detail values.** FFN and cross-diamond frontiers come from FFM joins
   with `eval_in_detail=False` because detailed evaluation crashes in
   `Nested._merge`. Validate at least one FFN plateau point another way, e.g.
   construct its mapping and evaluate it, or patch the merge and replay.
6. **Held-out scoring.** Recompute `heldout_scores.json` and the FFN/C1/C2
   plateaus from the raw result files without using `evaluate.py`.

## Commands

```sh
python -m research.index_coupling.nest_model
python -m research.index_coupling.evaluate research/index_coupling/results/T1_same.json research/index_coupling/results/T1_cross.json --square-n 32
python research/index_coupling/upstream_probe.py shared_input shared_input_copy --n 4 --actions   # upstream venv
python research/index_coupling/upstream_probe.py ffn_full_copy --no-detail --dims M=8,D=4,F=8     # upstream venv
```
