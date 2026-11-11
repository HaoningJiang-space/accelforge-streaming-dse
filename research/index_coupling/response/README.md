# response: closed forms, bounds and substitution for chain states

This package holds the code of CONTRACTION_ORACLE.md §6-21 and
SANDWICH_RESULTS.md. It describes a chain state's grammar response
(capacity -> least extra traffic, grammar v2) without searching. It covers
FFN and attention stacks and any chain of dense contractions and elementwise
operators.

| Module | Contents | Status |
| --- | --- | --- |
| `forms.py` | Unit-M forms: `loop_nest`, segment macros (`single`, `pair`, `ce`, `ec`, `cec`) and the boundary DP `predict` | chain envelope verified (§6-11); individual macros are not full native group frontiers (§21) |
| `keep_level.py` | One contraction at any M: keep-level `predict`, cached frontier `curve_of` | exact; frozen and held out (§12) |
| `chains.py` | `recognise` / `archived`: structural chain-state recognition returning a `Chain` | shared by every module below |
| `bounds.py` | `lower` (operator projection, any M) and `upper` (singleton partition) | proved / constructive (§14, sandwich) |
| `dag.py` | Archived call DAGs: `load`, `reach`, `removed`, `terminal_work` | accounting of exclusive work |
| `substitution.py` | `make_exact_kernel` (in-memory hook, `graph/curve.py` unchanged), lazy native witnesses `expand` | FFN-4: 6.8× historical frontier search, 6.60× complete native generation; no M8 benefit (§16/16a) |
| `experiments.py` | Every experiment command, plus `verify` | entry point |
| `fusion_width.py` | Bounded offline top-level group-span reconstruction from archived group interfaces | diagnostic only; high aggregate equality is mostly automatic n<=k coverage (§19) |
| `root_work.py` | Root-wide state families, parent provenance, free-terminal attribution and existing singleton-provider cost | read-only diagnostic; see WORK_ATTRIBUTION.md §4, no new replacement |

## Commands

Run from the repository root with `PYTHONPATH=.`:

```sh
python -m research.index_coupling.response.experiments verify          # all frozen predictions, seconds
python -m research.index_coupling.response.experiments grammar SET PRED OUT   # SET: nest chain2 chain elementwise weights matmul
python -m research.index_coupling.response.experiments archive|op-check|op-c2|op-work|closed-form-work|sandwich [CASE ...]
python -m research.index_coupling.response.experiments exact-check [CASE ...]
python -m research.index_coupling.response.experiments exact-bench OUT.jsonl REPEATS CASE ...
python -m research.index_coupling.response.experiments exact-mapping-bench NEW.jsonl REPEATS CASE ...
python -m research.index_coupling.response.fusion_width NEW.jsonl
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
- **Bounded group span.** The §19 diagnostic is complete: U_3 matches only
  20/193 M8-2 states whose spans actually exceed three operators (7.11% of
  that stratum's exclusive DP work). A shared row loop can span a long chain
  while using two activation cells, so group span is not physical live width.
  No online implementation follows this diagnostic.
- **Fixed M-to-one joint elimination.** The [proof and bounded plan](../LOOP_CONDITIONED_FACTORS.md)
  lead to an exact allocation/boundary DP in `../hypergraph_audit.py`. All
  36 branch frontier points match, with 324 exact replays. Complete branch
  generation is 0.52×/0.34× native on M8 and slower than existing forms;
  tiny FFN-4 only ties those forms. Section 20 records the factor-construction
  overhead. The pilot stops; no general hypergraph solver or root integration.
  Section 21's bounded continuation sweeps local breakpoints and retains the
  selected partition: search is faster, but complete M8 branch generation is
  still 0.47×/0.87× native after recovery. Tiny's fixed branch is 36.05× native;
  this is not a root speedup. All 720 repeated replays pass. The independent
  local audit finds 176/672 differences from native group frontiers: the
  forms are segment-plan macros, not individually exact group responses.
  Local solve partitions are inlined during recovery. The experiment stops.

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
