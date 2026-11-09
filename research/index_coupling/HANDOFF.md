# Handoff for Codex (state at this commit)

## Where things stand

- `nest_model.py`: zero-extra-traffic plateau from loop nests, no FFM search.
  Exact on all coupling and attention points; FFN within 1 B except F4
  (FFM 153 vs model 149; moving the dY copy gives 152, P9 failed).
- `curve_model.py`: full capacity-traffic curve. 216 FFM points: 206 equal,
  10 model-lower, 0 model-higher (`results/curve_comparison.txt`).
- `real_scale.py`: model applied at GPT-3 6.7B sizes (`results/real_scale.txt`).
- `REVIEW_NOTES.md`: previous review (copy semantics and Snowcat backing policy
  corrections are already applied in README).

## Tasks

1. **Independent execution check of the model.** Write an element-level
   simulator that executes a nest witness (`curve(graph, witness=True)` or
   `plateau(graph, witness=True)`) on small sizes, tracking which elements are
   in the buffer and every DRAM read/write. Confirm capacity and traffic for
   the 10 model-lower points and a sample of equal points. Report any witness
   whose execution needs more buffer or traffic than the model claims.
2. **Classify the 10 model-lower points.** For each, decide whether FFM's
   mapspace excludes the witness (cite source lines) or the model is wrong.
3. **F4 residual (needs an AccelForge environment, e.g. Windows).** Extract
   F4's per-einsum mappings from the no-detail FFM result object and find which
   constraint costs the extra bytes.

Write findings to `REVIEW_NOTES_2.md`; do not edit PROTOCOL.md.
