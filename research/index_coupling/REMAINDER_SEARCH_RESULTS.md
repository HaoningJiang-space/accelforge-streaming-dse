# Exact remainder reuse and infeasible-group pruning

Implementation: `da52c801`. The two rules from
[REMAINDER_LEMMAS.md](REMAINDER_LEMMAS.md) are now independent, default-off
options in `graph/curve.py`:

```python
curve(graph, partitions='dp', witness=True,
      canonical_remainders=True, prune_infeasible_groups=True)
```

The complete local four-arm comparison passes, but **remainder reuse is not a
stack speedup in this implementation**. The cheaper infeasibility rule improves
the tested stack timings. Exact remainder reuse strongly compresses the
rank-symmetric ancestor control, while its representation and lookup overhead
outweigh the savings on these FFN/attention stacks.

## Contract and implementation

Both options require exact, unlimited-capacity, unconstrained, single-writer
queries with consistent tensor projections and positive integer extents.
Unsupported settings raise an error. `solve`/`group` entry, tile domain, full
operator iteration domains, live-tensor incidence and roles, write ownership,
current extents and full rank sizes are preserved. Operator order is preserved.
Parent-paid capacity and compulsory transfers are not part of the internal
response being shared. `canonical_spans` and `canonical_remainders` cannot be
enabled together; the former still works independently.

`graph/remainder.py` builds invariant buckets from the ordered remainder.
WL colors only filter candidates: an explicit rank and tensor bijection must
pass an exact incidence check before reuse. This is invocation-local
representative lookup, not a globally canonical serialization. A matching
budget may decline reuse safely; it never permits an approximate merge. There
are no matching cutoffs in this local benchmark. A bounded 4,096-entry alias
LRU avoids storing an unbounded second copy of all raw cache keys. The
representative descriptors and witness rename nodes still consume memory.
Witness restoration now maps loop ranks as well as operators and tensors.

The infeasibility predicate first checks **all live nonscalar tensors**, then
the common legal ranks and unretained internal producer/consumer tensors.
It rejects empty groups before caching. Partition enumeration and Cut DP also
skip a whole retention batch if its optimistic all-possible-kept version is
still empty. This monotonicity test includes the scalar leaf; merely checking
the internal-made resident subset is insufficient.

The proof notes now make entry phase explicit in the induction and separate
WL diagnostic evidence from exact graph isomorphism. The archived diagnostic
also retained domain-edge multiplicities; this implementation uses the stated
domain sets. The 47 historical census files and frozen prediction records are
not regenerated. The current `curve.py` source hash has intentionally changed.
The separate order-complete `unified_search.py` study is not re-scored here;
combining its AST-inserted certificate/provenance markers with these new flags
is not part of this experiment.

## Correctness evidence

[tests.json](results/remainder_search/tests.json) records **79/79 passing
tests** across all 16 existing/new test modules. The new tests cover all four
option combinations under both partition solvers, full root witness replay,
all 64 private residency masks of a mixed two-consumer Fork at both entries,
non-power-of-two shapes, divisor tiles, ownership/options, and rejected scopes.
They also include two controls that a label-only implementation would miss:

- a real WL collision, a 12-cycle versus two disjoint 6-cycles, is rejected by
  the exact matcher;
- resident identity/multiplicity can disappear, but resident-only operator
  domain ranks and the solve/group distinction cannot disappear.

The benchmark completes **64/64 fresh-process runs**. All four arms and all
repetitions return identical complete frontiers in each case. **496/496 saved
witness executions** match capacity and traffic exactly. These finite checks
support the scoped implementation; they are not a physical-optimality claim.

## Local measurements

Source and configuration: [manifest](results/remainder_search/local/manifest.json).
Results, counters and equality checks: [summary](results/remainder_search/local/summary.json).
Each individual JSON retains its frontier, witnesses and replay reports.

Apple M3, macOS arm64, Python 3.12.7. Runs are serial, in fresh processes with
`PYTHONHASHSEED=0`, 40-second search-plus-replay and 1-GiB memory budgets per
attempt. The table uses three **unprofiled search-time medians**, excluding
replay; arm order rotates. A fourth, separately profiled round provides work
counters. All arms use Cut DP, ownership projection, halving tiles and
`independent_ops=False`. No result timed out or exceeded memory.

| Case | Baseline seconds | Precheck only | Remainder only | Both |
| --- | ---: | ---: | ---: | ---: |
| FFN, four forward layers / 12 ops | 2.833 | 2.155 | 4.894 | 2.920 |
| Attention, four layers / 12 ops | 2.763 | 2.246 | 4.869 | 2.942 |
| FFN, one training layer / 8 ops | 3.119 | 2.818 | 5.669 | 4.220 |
| Ancestor control, eight ranks / 1 op | 0.216 | 0.225 | 0.053 | 0.053 |

Forward-stack extents and training extents are all two. Attention uses the
existing elementwise softmax abstraction; these are not full Transformer
workloads. At these shapes the forward FFN and attention remainders are
isomorphic, so their identical work counters are not independent structural
evidence. The training case has a different dependency structure.

The precheck gives baseline/precheck median ratios **1.31x, 1.23x and 1.11x**
on the three stack cases. Remainder reuse gives **4.08x** on the ancestor
control; this subsecond measurement should not be extrapolated to P19.

Response-cache entries are solve plus group entries, not total memory objects:

| Case | Baseline | Precheck only | Remainder only | Both |
| --- | ---: | ---: | ---: | ---: |
| FFN forward / attention | 10,834 | 6,201 | 8,517 | 4,502 |
| FFN training | 17,095 | 12,155 | 15,290 | 10,611 |
| Ancestor control | 12,866 | 12,866 | 81 | 81 |

The ancestor control has 45 solve and 36 group representatives, totaling
`(8+1)^2 = 81`, versus `3^8 + (3^8-2^8)` raw entries. This is an implemented
state count, not a lower bound on every exact algorithm.

| Case | DP transitions, baseline | Precheck only | Remainder only | Both |
| --- | ---: | ---: | ---: | ---: |
| FFN forward / attention | 592,789 | 276,544 | 568,808 | 259,603 |
| FFN training | 572,300 | 380,155 | 558,637 | 370,160 |
| Ancestor control | 6,305 | 6,305 | 36 | 36 |

Fewer entries do **not** imply lower memory here. Median unprofiled peak RSS,
in MiB:

| Case | Baseline | Precheck only | Remainder only | Both |
| --- | ---: | ---: | ---: | ---: |
| FFN forward | 40.42 | 38.33 | 156.05 | 95.20 |
| Attention | 41.62 | 38.33 | 156.98 | 96.73 |
| FFN training | 49.31 | 43.78 | 162.80 | 124.17 |
| Ancestor control | 40.92 | 41.52 | 22.34 | 22.03 |

In the profiled forward FFN run, remainder-only lookup takes 1.861 seconds;
with prechecking it takes 0.543 seconds. These are lookup-section timings,
not a complete attribution of all descriptor/witness/allocator costs.
The combined stack arm remains slower than precheck alone. Both options
remain opt-in; this evidence favors precheck alone for these stack shapes.

## Interpretation and outstanding P19 run

The remainder lemma supplies a sufficient structural response invariant. It
does not say that the invariant is minimal, cheap to compute, or yields a
small number of classes for every graph. Infeasibility is a distinct cheap
classification that can be tested before doing any graph matching. These
measurements make that ordering useful in practice without changing the
mathematical response.

This advances the conditional-response line: some context can be erased,
isomorphic surviving problems can share a response, and empty problems can be
discarded. It does not close the dynamic **order-complete** quotient problem,
nor explain the traffic differences among non-isomorphic remaining graphs.
The next implementation work should be cost-guided: share compact structural
metadata and measure matching/restore overhead before extending the quotient.
The next physical theorem still concerns the coupled live tensors that remain
after these exact reductions.

The formal P19 shapes `(8,4,8,2,'kkkkkk')` and `(8,4,8,2,'kkkiii')` are supported
by the runner but **have not been run in this study**. Server SSH/repository/
Python-environment information was requested and is still pending. No P19
performance, server synchronization, or three-copy equality is claimed.
Reproduction commands (run from the repository root; `psutil` is required):

```sh
python -m research.index_coupling.bench_remainder_search \
  --out research/index_coupling/results/remainder_search/local_reproduction

# Larger server study; all four arms use the same independent-split option.
python -m research.index_coupling.bench_remainder_search \
  --cases p19_same p19_mixed --independent-ops --seconds 600 --mem-gib 4 \
  --out research/index_coupling/results/remainder_search/p19_server
```

The runner preserves every attempt, including failures, and refuses to reuse
an output directory with a different source/configuration. Timeouts remain
incomplete; equality among completed arms is not a full-matrix pass.
