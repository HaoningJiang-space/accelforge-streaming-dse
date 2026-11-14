# Scale-scan rejection was an audit-parser bug

The reported K=3072 failures do **not** show premature TOGSim termination. The
unchanged original logs contain complete execution, nonzero output writes, and
final cumulative DRAM counts equal to the compiled-DMA ledger. The error was in
our Python auditor, not in TOGSim's execution or its emitted counters.

## Root cause

Both auditors used `re.search(r'combined ... reads, ... writes', log)`. That
selects the first matching line. The pinned backend emits two distinct records:

- `DramRamulator2::cycle()`: `all 16 channels combined ... (interval 10000 cycles)`.
- `DramRamulator2::print_stat()`: `channels 0..15 combined ...`, the final totals.

Below 10,000 cycles only the final line exists. Above that threshold the first
interval appears before the final totals. The earlier small pilot exercised
only the first condition. Its passing results remain valid, but it did not
cover this log-parsing branch.

The apparent size boundary came from crossing a **logging interval**, not from
a demonstrated tensor capacity, K limit, event limit or output-write failure.
The differing first-interval read counts also follow from different mappings'
progress within their first 10,000 cycles; they are not capacity limits.

| Original run | Old first-match reads / writes | Actual final reads / writes | Expected | Final cycles |
| --- | ---: | ---: | ---: | ---: |
| 128×256×3072 heuristic | 145,768 / 0 | 147,456 / 4,096 | 147,456 / 4,096 | 13,906 |
| 128×768×3072 heuristic | 145,254 / 0 | 393,216 / 12,288 | 393,216 / 12,288 | 33,829 |
| 128×768×3072, tile 16×128×16 | 25,920 / 0 | 2,654,208 / 12,288 | 2,654,208 / 12,288 | 1,248,930 |

## Correction and evidence

`togsim_statistics.py` now requires exactly one final cumulative DRAM record
covering the configured channel range and exactly one completion marker. It
reads DMA instruction counts only from the final statistics block and checks
that final core cycles equal the completion total. Missing/truncated, duplicate,
reordered and internally inconsistent final records raise an error. Interval
snapshots cannot substitute for totals. Both the repaired and original-backend
auditors use this parser.

Tests use the actual three long logs (1, 3 and 124 interval records), a short
control, truncated logs, duplicated final/complete records, a wrong channel
range and malformed final counters. The existing incorrect-traffic and load-tag
collision tests continue to reject genuinely inconsistent audit inputs.

The original 15-run scan, including its three rejected `dma_audit.json` files,
is preserved under `results/pytorchsim/scale_scan_ba6728f3`. The archive retains
compiled TOGs, allocation headers, runtime attributes, hardware/mapping metadata
and original timing logs. Numerical-array hashes are recorded; those large
arrays remain in the original experiment directory. No old outcome is silently
rewritten. Re-audits and fresh executions are recorded separately.

Re-audit without rerunning hardware simulation:

```sh
python3 -m research.dnn_benchmarks.reaudit_pytorchsim_scan \
  --runs research/dnn_benchmarks/results/pytorchsim/scale_scan_ba6728f3 \
  --out "$FRESH_AUDIT_DIRECTORY"
```

The backend source, patches, binary, compiler and hardware configuration remain
unchanged. Only the auditor is corrected. On the experiment host, **15/15** original scan runs pass the corrected full
compiled-DMA audit, explicitly correcting **3 false rejections**. The three
large cases above were also recompiled and re-executed with the same backend:
**3/3** pass the automatic numerical/DMA gate, with exactly the same cycles as
the original logs. A fourth fresh short control returns **736 cycles** and
passes. All **13** regression tests pass locally and on the host. Re-auditing
the earlier two eight-run pilots preserves all **16** previous accepted counts
and cycle totals.

Results are in `results/pytorchsim/interval_stats_a8c2aa19`: `reaudit/summary.json`
contains the original-to-corrected classifications, `replay/summary.json` contains
the four fresh executions at source `a8c2aa19`, and `prior_pilots.json` verifies
the earlier pilot records. The fresh replay archive retains numerical arrays and
raw inputs/outputs as well as compiler and timing artifacts; all **78** files
match the recorded archive SHA-256 digests. Simulator SHA-256 remains
`633ea49487ae72170b8cbdd1f2ab754401d8d7ff4db44aa6a3ac04436a974a6a`.

## Experiment policy

Continue the main experiment with per-mapping admission: numerical output,
completed execution, final cumulative DMA counts, instruction counts and output
coverage must all pass. Preserve all attempts and report true failure rates;
exclude invalid cycles from performance comparisons. Record auditor/backend
versions, and reclassify parser-induced failures explicitly.

Remove the proposed K≤2048 restriction: this scan does not establish that
boundary. K=3072 mappings can participate when they pass the corrected checks.
Passing one shape or mapping does not certify all tiles or SRAM budgets. Keep
hardware resources, precision and evaluation budgets matched. Static generated
arrays alone still do not establish full peak SRAM feasibility, and these checks
do not establish calibrated hardware accuracy or energy.
