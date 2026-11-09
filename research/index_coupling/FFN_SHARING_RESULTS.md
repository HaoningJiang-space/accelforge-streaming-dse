# Complete P14-FFN: the restriction is not FFM-equivalent

**Frozen verdict: P14-FFN fails.** All eight materialization subsets are now
available. Their Pareto union is equal to the archived FFM at 15 union
breakpoints, higher at 15, and lower at none. The differences extend well
beyond the allowed 147/148 B plateau offset.

The newly finished Z and H+Z parts contain 31 and 19 frontier points and took
457 s and 418 s in their recorded runs. Their output JSON is complete and
their error logs are empty. These are completion observations, not matched
speedup measurements against the earlier failed runs. Both new frontiers are
dominated by the previously available six-part union: completing the eight
subsets leaves its 23-point frontier unchanged.

## 1. Correct union-breakpoint accounting

Each row below compares the union of that model curve's and FFM's capacity
breakpoints. Different rows therefore have different evaluation sets; the
counts should not be subtracted to isolate the contribution of one mechanism.

| Model | Lower than FFM | Equal | Higher |
|---|---:|---:|---:|
| Full graph | 34 | 2 | 1 |
| Write-through disabled | 30 | 7 | 1 |
| Completed restricted union, 8/8 subsets | 0 | 15 | 15 |

The previous claim of 56 better breakpoints combined sub-curve breakpoint
sets. **34** is the full graph curve's count under the scorer's own rule.
At capacity 80 B, for example, the full graph curve transfers 448 B versus
576 B in the FFM archive, a 22.22% reduction. This is the largest relative
reduction on its 37-point comparison set, not an average or a device speedup.
The graph is higher at 147 B (320 versus 256 B), reaching 256 B at 148 B.

The restricted curve, in contrast, is already worse at 49 B (864 versus
800 B) and 57 B (800 versus 704 B). Its plateau is **384 B at capacity 165 B**.
A one-byte capacity-offset allowance cannot repair a different traffic plateau.

## 2. A structural reason the restricted curve cannot match the plateau

This check requires no mapping enumeration. In the FFN M8 D4 F8 proxy, the
original input/output boundary is:

| Boundary objects | Sizes | Compulsory traffic |
|---|---|---:|
| Inputs X, W1, W2, dY | 32 B each | 128 B reads |
| Outputs Y, dW1, dW2, dX | 32 B each | 128 B writes |
| Total | | **256 B** |

Each of the four inputs has two consumers. The current restricted view calls
`separate(graph, inputs | chosen_intermediates)` and assigns a separate tensor
name to **every consumer of every shared graph input**. Consequently, even
with no intermediate materialized, the rewritten boundary requires:

```
8 input copies * 32 B + 4 final outputs * 32 B = 384 B.
```

The three optionally materialized intermediates H, Z and dH each have size
64 B and two consumers. Materializing one adds one compulsory write and two
reads, another 192 B. Every subset therefore has boundary traffic

```
384 B + 192 B * number_of_materialized_intermediates.
```

Thus **every** plan in this restricted union has traffic at least 384 B;
the union attains that floor. No missing subset, extra buffer, or more thorough
search of this rewritten space can reproduce FFM's 256 B plateau.

The distinction is physical: forbidding several consumers from sharing a
newly fetched DRAM tile is not the same as forbidding them from sharing an
input that remains resident across their uses. The rewrite does not preserve
the latter possibility. The observed FFM plateau alone refutes this rewrite
as an equivalent description of FFM's whole FFN mapping space. This does not
identify the exact native reservation/schedule responsible; that needs a
specific native mapping witness.

## 3. What the ablation establishes

The full graph model's 34 lower points remain recorded results. Imposing the
combined restrictions removes those improvements, which demonstrates their
importance **within this model**. It does not prove that one particular shared
reload mechanism uniquely explains the difference from native FFM: the
restricted space also excludes plans needed to reproduce known FFM results.

Keep the name "FFM-like" only as the historical hypothesis label. Do not
describe this eight-subset union as an FFM-equivalent oracle, or relax the
frozen equality criterion into "never below FFM" and call it a pass.
The original FFN proxy's alias/lifetime assumptions remain unchanged; this
audit does not establish a real neural-network performance gain.

Before defining another sharing ablation, require it to preserve at least
the known 256 B traffic solution, then use a native reservation witness to
distinguish whole-input retention from shared DRAM refetch. This is a check
on the control's physical contract, not a proposal for another optimizer.

## 4. Evidence and reproduction

The two completed runs were launched with the projected-cache code before
the module reorganization. Their runner identified 7b891c7c and imposed a
12,000,000 KiB address-space limit and six-hour timeout, without a capacity
cap. The six earlier successful parts are reused, justified by the projection
proof and archive-equivalence checks. No new FFN search was launched by this
completion audit.

The complete union was first scored using the pre-reorganization scorer in
the isolated 1d170433 checkout. The reorganized scorer at 6abe55bd produces
the same lower/higher capacity rows. An independent manifest check verifies
all eight distinct expected H/Z/dH subsets and monotone part frontiers.
Input-result file hashes, comparisons, and the rewritten boundary objects are
recorded in the machine-readable audit. This is static analysis of completed
outputs, not another mapping evaluation.

- [Two newly completed parts](results/ffn_parts/ffm_like_projected_completion.jsonl)
- [Six earlier parts](results/ffn_parts/ffm_like_partial.jsonl)
- [Full graph / no-write-through curves](results/ffn_parts/graph_nowt.jsonl)
- [Complete scoring output](results/ffn_parts/complete_scores.txt)
- [Manifest, comparisons and compulsory-traffic derivation](results/ffn_parts/complete_comparison.json)

```sh
python -m research.index_coupling.graph.scoring ffn \
  research/index_coupling/results/ffn_parts/graph_nowt.jsonl \
  research/index_coupling/results/ffn_parts/ffm_like_partial.jsonl \
  research/index_coupling/results/ffn_parts/ffm_like_projected_completion.jsonl
```
