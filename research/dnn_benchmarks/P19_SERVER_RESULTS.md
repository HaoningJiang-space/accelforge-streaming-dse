# P19: three complete timing rounds

All 24 unprofiled attempts have completed. Baseline and empty-group precheck
finish in all 12 of their attempts; all 12 attempts involving remainder
canonicalization fail under the frozen 4 GiB limit. The precheck is slower on
these P19 shapes. The separately scheduled eight profiling attempts are still
being collected and are not mixed into these timing statistics.

This study is pinned to `4a91b6f4` / grammar v1, with `independent_ops=True`.
It is separate from the later DNN grammar-v2/C2 study. Cases are
`fork(8,4,8,2,'kkkkkk')` and `fork(8,4,8,2,'kkkiii')`. Each attempt is a fresh
Python 3.10.12 process, limited to 600 seconds and 4 GiB, on one fixed CPU of
an Intel i9-12900 host. Runs are serialized and arm order rotates. Other work
can share the host; no hardware-execution speedup is inferred.

| Shape | Baseline median (s) | Precheck median (s) | Precheck / baseline time | Remainder | Both |
| --- | ---: | ---: | ---: | --- | --- |
| Same role | 240.707 | 278.484 | 1.157 | 3/3 memory-related failures | 3/3 memory-related failures |
| Mixed role | 232.259 | 274.983 | 1.184 | 3/3 memory-related failures | 3/3 memory-related failures |

Within each case, every completed frontier agrees and all **192** saved timing
run witnesses replay exactly. This validates the completed baseline/precheck
comparison. It does not validate the full four-arm matrix: the remainder arms
did not return frontiers and no speedup is assigned to them.

Raw outcomes remain 12 `complete`, 9 `crashed`, and 3 `memory`. Every crash's
traceback contains `MemoryError`, including failure while writing a record
after memory exhaustion. The parent-side RSS samples are retained. The 4 GiB
address-space cap is distinct from the RSS samples; the samples need not equal
the cap exactly. No failed attempt was silently rerun with a larger budget.

The implication is specific: the current remainder implementation is not an
effective optimization on these P19 workloads under this budget. Its exact
equivalence theorem is not contradicted by memory overhead. Cache reduction
and proven empty-state rejection do not by themselves guarantee runtime or
memory reduction.

All timing attempts and the frozen manifest are in `results/p19_timing`;
`results/p19_timing_score.json` contains the checks and medians. Absolute
experiment-source prefixes in failure tracebacks are redacted. Original raw
file digests and the redaction description are recorded in the archive
provenance; the original server files remain intact.

```sh
python -m research.dnn_benchmarks.score_p19_timing \
  --results research/dnn_benchmarks/results/p19_timing --out NEW_P19_SCORE.json
```
