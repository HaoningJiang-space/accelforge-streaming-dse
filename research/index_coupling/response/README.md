# response: closed forms, bounds and substitution for chain states

This package holds the code of CONTRACTION_ORACLE.md §6-18 and
SANDWICH_RESULTS.md. It describes a chain state's grammar response
(capacity -> least extra traffic, grammar v2) without searching. It covers
FFN and attention stacks and any chain of dense contractions and elementwise
operators.

| Module | Contents | Status |
| --- | --- | --- |
| `forms.py` | Unit-M closed forms: `loop_nest`, group forms (`single`, `pair`, `ce`, `ec`, `cec`) and the boundary DP `predict` | exact; frozen and held out (§6-11) |
| `keep_level.py` | One contraction at any M: keep-level `predict`, cached frontier `curve_of` | exact; frozen and held out (§12) |
| `chains.py` | `recognise` / `archived`: structural chain-state recognition returning a `Chain` | shared by every module below |
| `bounds.py` | `lower` (operator projection, any M) and `upper` (singleton partition) | proved / constructive (§14, sandwich) |
| `dag.py` | Archived call DAGs: `load`, `reach`, `removed`, `terminal_work` | accounting of exclusive work |
| `substitution.py` | `make_exact_kernel` (in-memory hook, `graph/curve.py` unchanged), lazy native witnesses `expand` | 6.8× frontier search on FFN-4, none at M8 (§16) |
| `experiments.py` | Every experiment command, plus `verify` | entry point |

## Commands

Run from the repository root with `PYTHONPATH=.`:

```sh
python -m research.index_coupling.response.experiments verify          # all frozen predictions, seconds
python -m research.index_coupling.response.experiments grammar SET PRED OUT   # SET: nest chain2 chain elementwise weights matmul
python -m research.index_coupling.response.experiments archive|op-check|op-c2|op-work|closed-form-work|sandwich [CASE ...]
python -m research.index_coupling.response.experiments exact-check [CASE ...]
python -m research.index_coupling.response.experiments exact-bench OUT.jsonl REPEATS CASE ...
```

- Archive commands default to the eight archived cases in `dag.CASES`.
- Frozen prediction sets and every recorded output are in
  `../results/contraction_oracle/`.
- `contraction_oracle.py`, the schedule-level oracle, stays one level up.

## Where things stand (for the next experiment)

- **Exact at unit M.** Substitution there gives a measured 6.8× speed-up in
  frontier search on FFN-4.
- **Little at M8.** Work at M8 sits in M > 1 states. Edge pruning is capped at
  16-24% of DP work, or 35-42% with oracle knowledge (§18).
- **Sandwich certificate.** It is exact wherever it holds, but it stopped by
  its frozen rule. Its upper bound fails because the optimum fuses operators.
- **Factorized loop closure.** The bounded full-grammar pilot preserves all
  tested curves and directly replays 49 native root witnesses, but slows
  both M8 cases and stops under its frozen rule. See
  [LOOP_CLOSURE_RESULTS.md](../LOOP_CLOSURE_RESULTS.md).
- **Open problem.** An upper bound, or exact response, for fused M > 1 groups.
  Sharing across different residency contexts remains open; the tested
  `(start, suffix, Pareto(A, D))` closure does not yet provide an M8 speedup.

## Renamed modules

These modules were merged here on 2026-11-10. Their old commands in earlier
commits map as follows:

| Old module | New location |
| --- | --- |
| `chain2_closed_form` | `forms.two_chain`, `forms.contraction_chain`, `forms.single`, `forms.pair`; `experiments grammar chain2` and `grammar chain` |
| `elementwise_chain` | `forms.predict` and the group forms; `experiments archive`, `grammar elementwise` and `grammar weights` |
| `matmul_keep` | `keep_level.predict`; `experiments grammar matmul` |
| `op_projection` | `bounds.lower`; `experiments op-check`, `op-c2` and `op-work` |
| `closed_form_work` | `experiments closed-form-work` |
| `sandwich` | `bounds.upper`; `experiments sandwich` |
| `exact_search` | `substitution`; `experiments exact-check`, `exact-bench` and `exact-once` |
| `row_projection` | removed; superseded by the operator bound. Its results stay in §13; the code is at commit `fe0cf256` |
