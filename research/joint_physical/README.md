# Demand-driven architecture and mapping generation

Chat GPT-6 Extra High supervised the paper exploration and review. Codex implemented
and ran this native experiment. It is a prototype joint generator, not an external
SOTA claim or a proof of optimality for all physical mappings.

The search uses one hardware variable `(Px, Py, SRAM)` shared by every operator in
the Attention graph. Under that hardware, LPs propose integer log2 tile factors
from the native symbolic costs and physical resource constraints. Neighboring
integer choices retain useful fusion properties instead of retaining only a local
weighted-cost winner. Heavy-operator proposals supply actual tile properties for
the intervening proxy. The optional second pass also supplies properties back to
the heavy operators. This is demand-guided generation, not an admissible deletion
test based on raw pairwise compatibility.

The native materializer receives only selected full assignments. Its original
symbolic actions, resource expressions, rank columns and mapping provenance are
used unchanged. An assertion forbids native Cartesian Tile expansion. Packed
hardware membership accompanies every materialized row and intersects during the
unmodified numeric Join. It prevents combining operator maps from different
physical hardware. The Join evaluates the actual composed prefix and all native
fusion/resource requirements. Every selected complete map is reevaluated on its
original physical hardware, including exact capacity and both array dimensions.

The algorithm borrows property-aware choice from
[parametric query optimization](https://www.vldb.org/pvldb/vol8/p221-trummer.pdf),
late materialization from [MonetDB/X100](https://www.cidrdb.org/cidr2005/papers/P19.pdf),
hardware-conditioned choices from [Sia](https://suhasjs.github.io/files/sia-sosp23.pdf),
and buffer-sensitive data movement from [Orojenesis](https://timeloop.csail.mit.edu/orojenesis).
These are inspirations, not reproduced cross-domain benchmarks. The workload is
the repository's QK → **elementwise proxy** → AV, not exact softmax or FlashAttention.

## Evidence and limits

The exhaustive relaxed-policy Event+Bitset+global-cache control and the proposed
generator have the same frozen native cost model, shape/SRAM domain, and zero
minimum spatial usage preference. The original-policy Event reference separately
quantifies the effect of broadening the policy. Cost comparisons use the native
physical reevaluation, not raw float32 Join score differences.

First 96-point diagnostic, all four canonical budget optima exactly reproduced:

| Method | Search seconds | Native model rows | Join pair rows | Peak process GiB |
| --- | ---: | ---: | ---: | ---: |
| Full relaxed Event + Bitset + cross-shape cache | 134.184 | 218,509 | 7,190,411 | 0.496 |
| Demand generation, one wave | 39.600 | 4,131 | 182,409 | 0.288 |

The demand run proposed 245,795 inexpensive integer assignments before validation
and selection, using 5,244 actual LP solves. The 4,131 count is materialized native
model rows, not total proposal work. All 96 selected per-hardware witnesses passed
physical re-evaluation. This was one diagnostic per method and the demand run
overlapped a symbolic audit. It is not a formal timing estimate.

The algorithm does **not** preserve complete per-hardware E/T/resource frontiers
or certify optimality. Even removing the usage preference is insufficient to make
shared full enumeration exactly reproduce all original enumeration histories:
the separate `direct` control matched four 12-point global optima but missed some
non-winning vectors at 32 KiB. It remains a diagnostic control. The failed
original-policy shared preparation is still disabled.

The heuristic also has a known small native counterexample: at one budget on
Attention(8,1,4), 1.53944064e-15 versus the control's 1.188798464e-15. The separate
bounded factor completion mode, used only for a small native test, enumerates the
complete factor lattice and passed all three small budget optima with the same
materializer and Join. It is explicitly counted and is disabled in the real
benchmark. This validates the materialization path, not heuristic completeness.

The 100-extraction independent audit covers every 6,144-PE ordered factor pair,
both policies, both SRAM endpoints, and the virtual preparation envelope. Raw
catalogs, normalized symbolic E/T, hard resource/factor constraints and serialized
LP matrices/objectives/upper bounds all match. Only physical RHS parameters vary.
Exact rational dual replay, this source-model audit, floating-model error analysis
and finite reference agreement are separate checks. No universal float error
theorem is claimed.

## Formal timing protocol

Five fresh single-worker processes per method, sequential, alternating order.
The proposed method first generates an incumbent on the same deterministic
geometry-first shape used by the control. That first wave and its validation are
charged; it then searches the full 96-point domain. Report complete runtime and
time to reach the common target EDP separately. The Event control often reaches
the optimum well before its exhaustive run ends. Reference costs are never used
for seeds, search ordering or stopping. Report files include independent replay
of serialized witnesses, with the native loop and storage metadata needed to
reconstruct fused scopes.

```
./research/joint_physical/benchmark_windows.ps1 -Repetitions 5 -PushEachTrial
```

External systems still require matching physical constraints and mapping scope
under the same evaluator. Published GPU runtime, Gemmini EDP and MAESTRO
estimates are not directly comparable to these native NVDLA scores.
