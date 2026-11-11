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
| `substitution.py` | `make_exact_kernel` (in-memory hook, `graph/curve.py` unchanged), lazy native witnesses `expand` | FFN-4: 6.8× historical frontier search, 6.60× complete native generation; no M8 benefit (§16/16a) |
| `experiments.py` | Every experiment command, plus `verify` | entry point |

## Commands

Run from the repository root with `PYTHONPATH=.`:

```sh
python -m research.index_coupling.response.experiments verify          # all frozen predictions, seconds
python -m research.index_coupling.response.experiments grammar SET PRED OUT   # SET: nest chain2 chain elementwise weights matmul
python -m research.index_coupling.response.experiments archive|op-check|op-c2|op-work|closed-form-work|sandwich [CASE ...]
python -m research.index_coupling.response.experiments exact-check [CASE ...]
python -m research.index_coupling.response.experiments exact-bench OUT.jsonl REPEATS CASE ...
python -m research.index_coupling.response.experiments exact-mapping-bench NEW.jsonl REPEATS CASE ...
```

- Archive commands default to the eight archived cases in `dag.CASES`.
- Frozen prediction sets and every recorded output are in
  `../results/contraction_oracle/`.
- `contraction_oracle.py`, the schedule-level oracle, stays one level up.

## Where things stand

Current priorities are in the [repository overview](../../OVERVIEW.md).
The open questions below identify research boundaries; they are not the
current implementation plan.

- **Exact at unit M.** Substitution there gives a measured 6.8× speed-up in
  historical frontier search on FFN-4. The complete native-witness follow-up
  retains 6.60×/6.70× on FFN-4/attention-4, including recovery; M8 gives
  0.84×/0.97×. See CONTRACTION_ORACLE.md §16a for scope and timing exclusions.
- **Little at M8.** Much work remains in M > 1 states. Recorded-order exact-child
  pruning removes 16-24% of DP work; one hindsight witness-selection policy
  removes 35-42%. The latter is not a proved all-order or wall-time bound (§18).
- **Sandwich certificate.** It is exact wherever it holds, but it stopped by
  its frozen rule. Its upper bound fails because the optimum fuses operators.
- **Factorized loop closure.** The bounded full-grammar pilot preserves all
  tested curves and directly replays 49 native root witnesses, but slows
  both M8 cases and stops under its frozen rule. See
  [LOOP_CLOSURE_RESULTS.md](../LOOP_CLOSURE_RESULTS.md).
- **Residency sharing.** The [latest offline study](../RESIDENCY_SHARING.md)
  rejects context-invariant gaps, local-only interactions and simple curve
  shifts at M > 1. Its 84–88% hypothetical DP-work ceiling is not a speedup
  forecast. Different curve shapes do not prove computation cannot be shared.
- **Open problem.** A cheap exact response or shared computation for fused
  M > 1 groups remains unproved. Neither the tested closure nor the three
  simple context-sharing structures establish it. Consolidate the existing
  evidence before proposing another representation.

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
