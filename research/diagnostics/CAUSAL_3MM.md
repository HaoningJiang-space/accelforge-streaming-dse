# Native 3mm: capacity, residency and array-shape causality

This is a diagnosis of the **six already archived mappings**, not a new search
algorithm or a new cost model. It uses the native NVDLA/FFM model, 3mm with
M=KN=256, 8-bit values, fixed 6,144 configured PEs, fixed bandwidth/clock and an
8-bit Register. The source is
[known_shape_reversal.json](../graph_coopt/results/coupling/known_shape_reversal.json).
All six structures restore with identical canonical Mapping IDs and reproduce
their source energy/latency within relative 1e-6. This is native-model
re-evaluation, **not independent physical lifetime verification**.

## What was actually run

- 12 fixed-map evaluations: each archived Mapping on its own PE shape at both
  128 and 132 KiB. No retile, rebinding or search is used for these migrations.
- Three fixed-map residency controls at 132 KiB: move T1/T2 backing to DRAM and
  insert full per-phase GB copies, preserving every Temporal/Spatial decision.
- Six reoptimized native **EL** controls with `max_fused_loops=0`, one at each
  original hardware point. This limits the search space; it does not disable
  whole-intermediate GB retention, force all-DRAM execution, or establish global
  physical optimality. Reconstructed selected costs match the search rows.
- Four diagnostic regressions, including exact-capacity-minus-one-byte and the
  actual native Join transfer. Existing synthesis/FFM suites were not rerun.

Only the six zero-fused-loop controls invoke Mapping generation. This is not a
timing benchmark: control search timings are archived but have no matched cold/
warm cached baseline or repeated-trial interpretation.

## 1. The extra 4 KiB admits a specific resource requirement

All three 132-KiB winners fail unchanged at 128 KiB. All three 128-KiB winners
remain feasible at 132 KiB with unchanged E/T. Thus extra capacity does not make
an unchanged low-capacity Mapping faster; it admits different mappings.

Every high-capacity winner has this native Matmul1 GB Reservation:

| Tensor | Elements / tile | GB bytes |
| --- | --- | ---: |
| T1 | full 256×256 | 65,536 |
| T2 | full 256×256 | 65,536 |
| W1, shape 16×384 | 256×16 | 4,096 |
| W1, shape 32×192 | 128×32 | 4,096 |
| W1, shape 64×96 | 64×64 | 4,096 |

The selected W1 row is one alternative, not three simultaneous allocations:
`65,536 + 65,536 + 4,096 = 135,168 bytes = 132 KiB`. The 32×192 source is also
rejected at 135,167 bytes, by exactly eight bits. In the 16×384 winner, Matmul0
also reaches 132 KiB using full T0/T1 and a 4-KiB W0 tile.

These facts establish the exact native Reservation threshold for **these fixed
mappings**. They do not prove every legal completion needs two fully live
intermediates, nor that all physically legal implementations need 132 KiB.

## 2. A per-phase maximum misses a real cross-stage Reservation

The 64×96, 128-KiB winner keeps T2 at root GB and exchanges a partial T1 through
a shared m=128 loop between Matmul0 and Matmul1. Individual phase model peaks
are 52/100/84 KiB, but the joined Mapping needs **116 KiB**, not max=100 KiB.

The recorded first Join performs:

| Native input / operation | Bits | KiB |
| --- | ---: | ---: |
| Left depth-1 Reservation: T1 tile + T0 tile + W0 tile | 425,984 | 52 |
| Right outer depth-0 Reservation: full T2 backing | 524,288 | 64 |
| Add outer right Reservation to left depth-1 state | 950,272 | **116** |

The left terms are 32+16+4 KiB. The corresponding right phase has
T2 64 + T1 32 + W1 4 = 100 KiB. The native transfer operation is
`reservation<GB,1,left> += reservation<GB,0,right>` before scope collapse.
The final global reservation remains 950,272 bits.

This is concrete evidence that a subproblem's scalar peak is insufficient:
the future/outer T2 Reservation affects a producer phase that does not itself
access T2. It describes **reserved capacity over the declared fused scope**,
not a claim that every T2 element has already been produced during Matmul0.
The native FFM already handles this dependency. Reproducing it in a new state
representation is not, by itself, a new algorithmic contribution.

## 3. What the changed mappings save

Memory actions below are native bit actions converted to bytes. Totals include
reads and writes; a full intermediate round trip is 2×65,536 bytes. The identical
MAC energy in all six runs is 4.22785843 microjoules, with 50,331,648 MAC actions.
Each phase's compute component latency is 4.096 microseconds in every run.

| Shape | GB KiB | Total DRAM bytes | GB energy, microjoules | Total energy, microjoules | Latency, microseconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| 16×384 | 128 | 524,288 | 8.432124 | 42.145939 | 14.336 |
| 16×384 | 132 | 327,680 | 7.863796 | 30.520377 | 12.288 |
| 32×192 | 128 | 458,752 | 5.867307 | 35.895378 | 13.312 |
| 32×192 | 132 | 327,680 | 5.583143 | 28.239725 | 12.288 |
| 64×96 | 128 | 393,216 | 5.875171 | 32.217498 | 13.312 |
| 64×96 | 132 | 327,680 | 5.721555 | 28.378137 | 12.288 |

Relative to its high-capacity winner:

- 16×384 at 128 KiB pays one T2 round trip (131,072 bytes) and one additional
  W0 read (65,536 bytes).
- 32×192 pays one T2 round trip (131,072 bytes).
- 64×96 already avoids DRAM actions for both T1/T2 through its fused organization,
  but reads T0 twice, adding 65,536 bytes. Its T1 is a tile, not a full root tensor.

At 128 KiB, 16×384 has two DRAM-bound 5.12-us phases; 32×192 has one at Matmul2,
and 64×96 has one at Matmul0. The remaining phases are compute-bound. At 132 KiB,
all phases in all three shapes are compute-bound. **The switch is not explained
by doing fewer MACs or obtaining more compute throughput.**

At 132 KiB, DRAM traffic, MAC actions and total latency are equal across shapes.
The 32×192 versus 64×96 EDP difference therefore comes from GB action energy:
0.138412032 microjoules, about 0.49% of the latter's total energy. This is a
small **model-level** ranking, not a robust real-chip area/clock conclusion.

## 4. Two controls with different meanings

### Fixed-map removal of cross-stage GB backing

For each high-capacity source, T1/T2 are backed by MainMemory instead of root GB.
Full GB copies remain local to each phase, and all loop/spatial choices are
preserved. This is legal under the existing `may_keep: All` storage policy and
re-evaluates at 132 KiB. It is **not a reoptimized no-sharing search**.

Each control adds exactly **262,144 bytes**: one full write/read round trip for
each of T1 and T2. Every shape's latency rises from 12.288 to 15.360 microseconds;
each phase becomes DRAM-bound at 5.12 microseconds. Total energies become
45.831684 / 43.551031 / 43.689443 microjoules for the three shapes respectively.
GB peak remains 132 KiB because the full per-phase copies remain. This control
measures the cost of forcing materialization in those schedules; it cannot
attribute the entire unrestricted-search improvement to a single optimization.

### Reoptimized zero-fused-loop search

EDP units are 10^-10 joule seconds. Entries are best **returned** by the declared
native FFM contract, not certified optima over all physical mappings.

| Shape | 128 KiB original | 128 KiB zero fused loops | 132 KiB original | 132 KiB zero fused loops |
| --- | ---: | ---: | ---: | ---: |
| 16×384 | 6.042042 | 6.042042 | 3.750344 | 3.750344 |
| 32×192 | 4.778393 | 4.778393 | 3.470097 | 3.470097 |
| 64×96 | **4.288793** | 4.796818 | 3.487105 | 3.487105 |

Only the low-capacity 64×96 result worsens: **11.8454%** EDP. Source identities
and resource peaks can change even where E/T ties. With this restriction,
**32×192 wins at both capacities**. The original architecture-ranking reversal
therefore depends on the fused alternative available to the low-capacity 64×96
search. This is a controlled search-space/policy comparison, not an additive
causal decomposition, nor a claim that `max_fused_loops=0` removes all data reuse.

## Research decision

This case supplies a genuine mechanism to study: full versus tiled intermediate
residency, a Reservation carried across a fused scope, and array-dependent tile/
memory-action choices. No artificial SRAM layout penalty or new bank model is
needed to expose it. A faithful representation would have to retain the live
backing Reservation's scope and the exchange tile, not merely one local peak.

**It still does not establish the need for a new Graph Search.** The native FFM
already resolves these dependencies. We have not measured a matched strong-cache
baseline on this case, isolated its residual expensive operations, or proved that
another graph decomposition would eliminate them. The next decision gate is a
same-contract cost/profile comparison, not implementing a three-stage optimizer
because this dependency exists. No new search state, synthesis feature, hardware
cost model or speedup claim is introduced here.

## Evidence and reproduction

- [causal_3mm_controls.json](results/causal_3mm_controls.json): 12 fixed replays,
  3 residency controls, 6 zero-fused-loop searches and their replays, per-Einsum
  actions/component latencies/energies, reservation prefixes and Join transfers.
- [causal_3mm_tests.txt](results/causal_3mm_tests.txt): four passing native
  diagnostic tests. These are not additional independent workload experiments or
  a rerun of the production regression suite.
- [causal_3mm.py](causal_3mm.py): restores target/Einsum-specific derived component
  references omitted by structural archives. Canonical identities are checked
  before evaluation. Temporary single-process observation hooks restore on exit;
  no native implementation or search decision is patched to change its result.

The source archive and used native sources have recorded SHA-256 fingerprints.
The work uses the existing 8-bit workload and native per-bit action coefficients;
it does not apply the deferred 16-bit toy/native coefficient draft. Native
reservation consistency does not independently validate physical aliasing,
exact cycle-by-cycle live sets, or a real memory allocator.

```sh
python -m research.diagnostics.causal_3mm --zero-fusion-controls --output research/diagnostics/results/causal_3mm_controls.json
python -m pytest -q research/diagnostics/test_causal_3mm.py --disable-warnings
```
