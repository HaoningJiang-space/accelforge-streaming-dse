# Held-out validation: cheap construction, insufficient full-curve coverage

The frozen quality gate fails. Both two-axis families provide executable
candidates at every reference-feasible budget, but neither is an accurate
substitute for the recursive reference over its complete capacity range.
No constructor was modified in response to these results.

## Experiment and provenance

Protocol/runner frozen at `398af08a`, based on `ef165c9e`; score aggregation
added at `8d963b72`, post-observation miss inspection at `42c0f0a1`.
All evaluations and replays ran on the designated experiment server, at most
four workers. 78/78 cases completed, with no timeout or evaluation error.
Three scoring unit tests passed there before the experiment.

- 31 shapes held out from constructor design, both patterns: 62 instances.
  Their reference curves had already been observed; they are not new unseen
  observations of the gap law.
- Eight fresh J=2 shapes, both patterns: 16 instances. Reference generated
  from scratch three times; each constructor measured seven times in rotated
  order. All methods compile once for the entire query set.
- Same power-of-two tile choices; constructors are strict restricted families,
  compared with the broader recursive-nest model. This is not native FFM timing
  or a proof of a physical global optimum.
- Score all integer byte budgets from reference minimum through its plateau,
  using the union of breakpoints. Tail budgets above that plateau are excluded.
  Percentages below pool integer budgets, not uniformly sampled instances.
  Per-instance rows and all breakpoint comparisons are preserved.

[Protocol](HELDOUT_PROTOCOL.md) · [Raw cases](results/constructive_heldout/cases.jsonl)
· [Summary](results/constructive_heldout/summary.json)

## Quality

| Family | All 78: budgets within 5% traffic | Fresh 16: within 5% | Worst traffic excess, all 78 | Uncovered integer budgets |
| --- | ---: | ---: | ---: | ---: |
| Strips | 41.87% | 22.44% | 658.82% | 3642 |
| Reduced retention | 74.18% | 66.67% | 112.00% | 0 |
| Full scoped retention | 80.23% | 68.59% | 112.00% | 0 |

Only 3/78 reduced and 5/78 full-family instances have <=10% excess at every
budget. Both fail the frozen criteria of maximum excess <=10% and at least
90% of integer budgets within 5%. They pass the no-uncovered-budget criterion.
The previous 121/128 midpoint successes therefore do not generalize to the
full curve. The original half-row targets favored a particular schedule family.

At equal traffic targets, the largest recorded capacity inflation for either
two-axis family is 21 to 69 B (228.57%), at target 307200 B for cross
(64,16,64,64). Large traffic errors are not universally explained by tiny
capacity offsets; all inverse comparisons are included in the raw records.

## Cost, without an exact-search speedup claim

For the 16 fresh instances, sum of within-instance median construction times:

| Recursive reference | Strips | Reduced retention | Full scoped retention |
| ---: | ---: | ---: | ---: |
| 43.587 s | 13.879 ms | 24.386 ms | 83.619 ms |

These measurements include candidate construction and Pareto, exclude
independent replay, and allow every method to reuse its entire compiled curve.
All constructors pass the timing gate; their quality gate fails. Their much
smaller grammar is precisely why these ratios cannot be advertised as an
exact-search improvement. These measurements do not establish a native
Capacity Events + Cache speedup.

## Two executable counterexamples identify the missing scope

After scoring, the worst full-family loss in each test set was selected and
its reference witness regenerated and independently executed.

| Shape, cross | Budget | Reference traffic | Full-family traffic | Full-family capacity for that reference traffic |
| --- | ---: | ---: | ---: | ---: |
| (64,4,64,8) | 661 B | 4352 B | 7936 B | 673 B |
| (16,2,64,4) | 171 B | 800 B | 1696 B | 177 B |

The fresh reference retains A/U/D across the K loop (32+64+64 B), then
retains B/C/V at the inner I loop (2+4+4 B), while X occupies one cell.
Its peak is 171 B and every input/output is transferred only once. The
existing constructor can retain A/U/D, but completes an entire 16-cell X
strip before its consumers run: 160+16+1=177 B. At 171 B it falls back to a
smaller strip and repeats/spills data, producing 112% more traffic.

The archived miss likewise retains B/C/V at one scope and A/D/U inside it;
its independently observed peak is B128+C256+V256+A4+D8+U8+X1=661 B.

The missing freedom is retention at multiple nested scopes and producing X
at a finer granularity than the retained operand slices. Adding all masks at
one scope does not supply that freedom. These are post-observation explanations,
not a repaired or newly tuned success result. Nor do two witnesses prove this
mechanism explains every miss.

[Reference witnesses and executions](results/constructive_heldout/misses.jsonl)

## Independent execution

42 distinct selected constructor plans (minimum-capacity, plateau and worst-loss
witnesses from fresh cases) passed the unchanged simulator: peak, per-tensor
reads/writes, complete operation coverage and numerical outputs all agree.
They executed 661984 operations. Both diagnostic reference witnesses also
passed. These selected replays do not certify completeness of either grammar.

[Constructor executions](results/constructive_heldout/audit.jsonl)

## FFN: the transfer gate and previous runs

The existing constructor's contract requires a MatMul producer and two MatMul
consumers. None of the seven shared tensors in the current FFN graph passes
this necessary check: X/W1/W2/dY are external inputs, H has elementwise
consumers, Z has an elementwise producer, and dH has an elementwise producer.
Thus a direct application is unsupported. Absorbing identity operations would
also require accounting for H's later use and other external lifetimes; those
were not erased to manufacture a matching fork. No full-FFN construction time
or quality claim follows from the fork measurements.

The previously launched FFN part jobs were inspected, not restarted. Graph
and no-write-through completed (reported 1365/926 s); the other nine parts
have empty outputs and logs ending in MemoryError. The observed source checkout
was b733c03e with an unrelated _version.py modification. The original outputs
embed no commit, so this is associated-checkout provenance, not a fresh pinned
benchmark. Import records preserve original output hashes and complete curves.

P12 FAILS against the best FFM row at each of 21 distinct archived capacities:
14 no-write-through points are still lower, six equal, one higher. At 140 B,
no-write-through still uses 320 B traffic versus FFM's 384 B. Write-through
alone does not explain the FFN advantage. At 147 B the model is worse (320
versus 256 B); its plateau starts at 148 B. P14-FFN remains incomplete because
of the nine failed jobs. No direct native FFM rerun or new independent replay
of the whole no-write-through FFN curve was performed here.

[FFN contract records](results/constructive_heldout/ffn_contract.jsonl) ·
[Imported FFN results and failures](results/constructive_heldout/ffn_status.jsonl)

## Decision

Keep the cost-preserving residence identity and executable constructors as
validated restricted results. Reject the claim that the current small family
already approximates the complete curve well or transfers directly to FFN.
This experiment identifies a concrete physical scope mismatch, not a need to
optimize the Pareto implementation. Any extension should first declare how it
represents nested residency without returning to full recursive enumeration;
this report does not introduce that extension.

## Reproduce

Run from the repository root in an existing Python environment on the server:

```sh
python -B -m unittest research.index_coupling.test_validate_constructive
python -B -m research.index_coupling.validate_constructive run > cases.jsonl
python -B -m research.index_coupling.validate_constructive audit --input cases.jsonl > audit.jsonl
python -B -m research.index_coupling.summarize_heldout cases.jsonl > summary.json
python -B -m research.index_coupling.inspect_heldout_miss cases.jsonl > misses.jsonl
python -B -m research.index_coupling.validate_constructive ffn_contract
```
