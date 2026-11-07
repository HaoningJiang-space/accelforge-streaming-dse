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

All five pairs completed; see the [machine-readable summary](../joint_budget/results/formal_demand128/summary.json)
and the individual result/replay pairs next to it. The 96 physical points
are the 24 ordered factorizations of 6,144 PEs crossed with 4, 8, 16 and 32 KiB.

| Five-run median | Full relaxed Event | Demand with seed wave |
| --- | ---: | ---: |
| Complete search time (range), s | 129.78 (124.14–132.95) | 43.81 (43.56–44.23) |
| Time to all four common EDP targets (range), s | 21.60 (21.22–22.03) | 13.20 (13.15–13.23) |
| Native model rows | 218,509 | 4,533 |
| Native Join pair rows | 7,190,411 | 183,963 |
| Peak process GiB before independent audit | 0.492 | 0.351 |

The four physically re-evaluated EDPs were identical in every trial:
1.4112041153331202e-10, 9.708321706257069e-11, 7.658403161702401e-11 and
4.061826628539734e-11 J·s, in budget order. Every demand trial independently
replayed all 96 point witnesses and eight seed/final budget witnesses.
The native Event replay rechecks its four budget incumbents. The 2.96×
complete-search and 1.64× target-time ratios compare medians on this
instance; the complete Event and heuristic searches have different
completeness guarantees. The seed pass is charged again when the full
search revisits that hardware.

## Feedback ablation and scale holdout

In a separate one-run ablation, all three proposal policies used the same
physical domain, mapper, LP objective weights, numeric Join, and relaxed policy.
Removing producer/consumer feedback from proxy generation reduced work a little
but hurt all four budgets. An independent single-axis sweep recovered no EDP
despite materializing 76 more rows and solving 156 more LPs than feedback:

| Proposal policy | Native model rows | LP solves | Worst EDP / Event | Search, s |
| --- | ---: | ---: | ---: | ---: |
| Fusion property feedback | 4,131 | 5,244 | 1.000 | 39.17 |
| Independent | 4,057 | 5,016 | 2.754 | 32.01 |
| Independent single-axis sweep | 4,207 | 5,400 | 2.754 | 44.31 |

These controls do not prove that all graph-blind samplers lose. They show the
observed cost advantage cannot be attributed solely to more rows or LP solves.
The [replays](../joint_budget/results/ablation_attention128/) cover all 96
selected points and four budget incumbents for each method, with native
action counts and exact reservations checked at each point.

The [unretuned Attention256 holdout](../joint_budget/results/holdout_attention256/)
finished in 54.24 s vs 137.83 s for Event, but EDP was worse by 0.34%, 0%,
3.02%, and 6.06%. Feeding live properties from the actual numeric QK→proxy
prefix to AV did not repair those gaps and raised the time to 95.97 s. That
heuristic is retained as a diagnostic; it is not the default.

The [exact-anchor control and hybrid](../joint_budget/results/refine_attention256/)
first exhaustively solve the same geometry-ordered first shape as Event. The
hybrid then generates mappings conditioned on all other 92 physical points.
Both matched all four Event targets. The hybrid used 55.91 s, 17,625 native
model rows and 809,218 Join pairs, compared with 137.83 s, 274,408 rows and
9,291,036 pairs for Event. All improvements came from the anchor itself
(21.71 s on its own). This repairs the tested holdout's quality, but does not
show a time-to-target advantage over Event's first shape or certify any other
shape's optimal mapping.

On [Attention512](../joint_budget/results/holdout_attention512/), the same
hybrid matched all four Event targets without retuning (73.65 s vs 120.49 s
complete search). The anchor still supplied all winners. The timings are
diagnostic, with other validation work active; the trial does not establish
faster first attainment. The separate correlated-bound exact-policy search
used 14 native shape solves, cut 44 hardware points, and reproduced all four
costs in an independent replay of 3,823 dual functions and 49,209 reference
vectors. It took 106.12 s.

An observation-only [continuation audit](../joint_budget/results/continuation_attention256_targets.json)
measured the max-plus resource contract on the 12-point Attention256 slice.
Of 2,164 prefix/hardware instances, 1,233 already had no consumer at the same
native numeric equality key. Among the 931 that did, evaluating the compiled
terminal resource response at componentwise minima did not exclude any more.
This audit used the generated candidate subset and never deleted a native
row. It does not support deploying the capacity filter as a speed claim.

On [native 3mm](../joint_budget/results/fusion_3mm12/), both proposal variants
matched all three Event targets. The 12-point reference changes optimal
array shape from 64×96 at 128 KiB to 32×192 at 132 KiB. Event took 73.96 s;
feedback took 25.55 s, and independent proposals took 17.84 s. Both proposal
runs replayed all 12 physical point mappings and three budget incumbents.
This confirms that selecting both shape and mapping can matter, and that
cross-operator feedback is useful on Attention but unnecessary on this 3mm slice.

The [full 96-point 3mm run](../joint_budget/results/fusion_3mm96/) picked a
64×96 array at 128 KiB and a 48×128 array at the two larger budgets. Both
proposal variants matched the full Event reference's three perfect-tile
costs. The independent policy materialized 2,346 native rows and evaluated
48,306 Join pairs, compared with 441,603 and 125,484,813 for Event. Observed
complete-search times were 46.56 s and 389.62 s, respectively, in a diagnostic
with concurrent development. Event reached the three targets in 69.54 s.
These timings are not another repeated formal benchmark.

## Exact tails improve the 3mm energy-delay result

Power-of-two perfect tiles leave lanes unused on 96-wide and 48-wide
fanouts. A bounded refinement tries the available width at a nonshared
temporal site feeding the spatial loop. It keeps the native Join for
fusion/resource checks and rejects a candidate if an independent iteration
trace disagrees with its MAC count or cycles. It does not search every
possible tail or modify the repository's default native model.

The unmodified perfect-factor assumption could report fractional cycles for
a nondividing tile. The scoped tail evaluator explicitly checks integer
divisibility and combines full/tail children at the same reservation depth.
The initial symbolic timing still undercounted a shared memory port by
taking a maximum across full/tail branches. Use the
[corrected port ledger](../joint_budget/results/tail_3mm96_ports.json), which
sums the replayed bit actions at each physical port and applies the same
energy, bandwidth, and compute rates to both perfect and tail mappings.
It reproduces the perfect scores. The initial symbolic timing reports are
retained as diagnostics, not as the final EDP comparison.

| SRAM budget | Perfect Event array | Array / SRAM with tails | Perfect EDP (J·s) | Repriced tail EDP (J·s) | Reduction |
| --- | --- | --- | ---: | ---: | ---: |
| 128 KiB | 64×96 | 96×64 / 128 KiB | 4.28879e-10 | 3.70865e-10 | 13.53% |
| 132 KiB | 48×128 | 48×128 / 132 KiB | 3.47010e-10 | 3.02749e-10 | 12.75% |
| 256 KiB | 48×128 | 64×96 / 256 KiB | 3.47010e-10 | 2.68590e-10 | 22.60% |

This changes the selected hardware as well as the mapping at two budgets.
All 96 seed points came from the independent proposal search; 364 tail
witnesses replayed. The port calculation is independent of the native
latency expression and uses native bit action counts. The comparison is
against the complete *perfect-tile* search. It does not certify optimality
in the extended grammar or establish a speedup over a comparator allowed
to search that same extended grammar. The same one-site tail edits on
Attention256/512 were rejected by the native Fusion Join.

Separately, reallocating 64 or 128 of 6,144 compute sites to the Attention
proxy's pointwise path reduced modeled EDP by 6.34–17.57× at fixed SRAM and
per-action energy. All four mappings remained unchanged. This diagnoses
the simulated scalar bottleneck; it is not an additional mapping benefit
or a measured area/power result. Real NVDLA already includes a
[pointwise data processor](https://nvdla.org/hwarch).

External systems still require matching physical constraints and mapping scope
under the same evaluator. Published GPU runtime, Gemmini EDP and MAESTRO
estimates are not directly comparable to these native NVDLA scores.
