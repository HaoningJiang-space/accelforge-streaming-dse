# Two-level SRAM and mixed-phase hardware gate

The gate tests one prefill projection and one single-query decode score
contraction. It uses 8-bit tensors and 2,048 MACs at 1 GHz. The two SRAM levels
hold shared data and stripe-private weights, respectively. The experiment
varies the PE geometry, global bank count, global capacity per bank, and
private capacity per stripe.

The [pinned CACTI run](https://github.com/HaoningJiang-space/accelforge-streaming-dse/actions/runs/42453899987)
characterizes 45 nm scratchpads with one dedicated read port and one dedicated
write port. The [macro table](results/sram_45nm.json) records area, dynamic
read and write energy, standby leakage, and access and cycle time. A stripe
has one private macro. The shared SRAM is built from separate global macros.
The budget covers these SRAMs. MAC and register counts are fixed, and
interconnect layout area is outside the model.

Native bit counts are prorated against 64-bit private and 512-bit global
transactions. The initial service model assumes evenly distributed global
bank traffic and rounds each bank's access and cycle times up to whole
1 GHz cycles. The one-bank sensitivity keeps all SRAM area and leakage
and limits the global service rate to one bank. Both modes use aggregate
service rates. Address-level bank calendars are outside this model.

The mapper generates native tile rows independently at each hardware point.
The EDP calculation adds the energy and time of both phases before
multiplying. The independent-hardware relaxation combines the full energy and
time fronts of both phases across the same area-capped hardware points.
Both architecture-first controls retain all ties and remap both phases
with the physical costs. One uses a fixed-price, zero-leakage proxy to choose
hardware. The other chooses hardware using only the prefill phase.

## Cold decode

The 512-token cold scan covered 15 hardware points across three area caps.
At 16, 64, and 256 decode steps, the shared-hardware penalties were 1.37%,
1.83%, and 2.00% at each cap. Prefill-first followed by full remapping tied
the shared optimum in all nine cases. The nine shared EDP values reproduced
exactly on Windows with the same CACTI table.
[Linux report](results/cold_512_linux.json.gz) ·
[Windows replay](results/cold_512_windows.json.gz)

## Resident decode

The 1,024-token variant allows the 64 KiB KV input to stay in GlobalBuffer
between decode steps. Each native tile reserves the whole tensor plus its
other live storage. The audit checks the bit-exact capacity and verifies
zero native DRAM reads of resident KV. An explicit DMA fill loads the full
input once after prefill. The fill occupies both endpoints and pays
DRAM read energy, SRAM write energy, and leakage during the transfer.

At the 1.3465 mm² SRAM cap, 13 hardware points are admitted and four
can keep KV resident. The 16-step shared winner uses a 32 × 64 array,
two 64 KiB global banks, and a 1 KiB private macro per stripe. It uses
1.0954 mm² of SRAM. In the all-bank model, prefill alone chooses a
16 × 128 array and four 16 KiB global banks. That hardware needs cold
decode because its GlobalBuffer has no room for both full KV and staging.

| Global service | Shared penalty at 16 steps | 64 steps | 256 steps | Prefill-first EDP ratio at 16 steps | Fixed-price remap ratio at 16 steps |
|---|---:|---:|---:|---:|---:|
| All banks | 7.39% | 4.73% | 1.94% | 5.86× | 1.00× |
| One bank | 8.12% | 4.85% | 2.68% | 3.46× | 1.00× |

The hardware-conflict threshold of 5% is met at 16 steps in both service
models. The fixed-price architecture selector also models residency and
ties the physical shared optimum in every resident case. The result
identifies a capacity threshold and shared-hardware cost. The matching
control leaves a search advantage open. The optimality scope is the
sampled native mappings.
[All-bank report](results/resident_1024_all_windows.json.gz) ·
[One-bank report](results/resident_1024_single_windows.json.gz)

The [Linux replay](https://github.com/HaoningJiang-space/accelforge-streaming-dse/actions/runs/42454657897)
regenerated the CACTI table byte for byte and reproduced all 27 shared and
independent EDP pairs and their shared winners exactly. The Linux native
scans took 39–45 seconds per service configuration.
[All-bank Linux report](results/resident_1024_all_linux.json.gz) ·
[One-bank Linux report](results/resident_1024_single_linux.json.gz)

## Run

Run these commands from the repository root in the AccelForge environment.

```sh
python -m research.physical_cost.cacti_sram /path/to/pinned/cacti /tmp/physical-cost
python -m research.physical_cost.mixed_gate /tmp/physical-cost/sram.json /tmp/cold.json
python -m research.physical_cost.mixed_gate /tmp/physical-cost/sram.json /tmp/resident.json --context 1024 --resident-kv
python -m research.physical_cost.mixed_gate /tmp/physical-cost/sram.json /tmp/single-bank.json --context 1024 --resident-kv --single-bank-service
```

On Windows, supply the corresponding Python arguments to
`research/runtime/run_windows.ps1` and use the checked-in macro table.
Raw run logs and CACTI inputs are available as a compressed workflow artifact.

## Addressed SRAM with two concurrent requests

The addressed experiment admits prefill after the first decode step of
another request and opens the next decode step after prefill staging
starts. It tracks 64-byte physical words in every global SRAM bank, charges
whole transactions, and schedules the separate read and write ports, a
single DDR port and a single MAC array. Prefill and decode have separate
fixed slots in the private weight SRAM of each stripe. Global slots are
reserved from the first fill until their final use. The decode request
can retain a full KV image or stream its weight slices from DDR.

The evaluator schedules commands and the independent replay enumerates
word addresses and their versions. The latter checks conflicts,
producer completion, peak occupancy and EDP. Both search families use
the same physical area, tile choices, schedules, and calibrated costs.
Each wall-clock trace starts with candidate generation and charges
architecture selection, event compilation, dispatch and verification of
each new incumbent. The common CACTI table is loaded before timing.

On the initial three cases, the shared winners held KV concurrently with
prefill staging for 8.762–16.246 µs. The bank-aware architecture selector
retained all exact ties and the wider control included all architectures
within 2% of its bound. Both matched the complete search in all three
cases. The initial grammar refetches the prefill weight tile per row tile.
[Initial Windows report](results/banked_v1_windows.json.gz)

```sh
python -m research.physical_cost.banked_search research/physical_cost/results/sram_45nm.json /tmp/banked.json.gz
python -m pytest -q research/physical_cost/tests/test_banked_serving.py
```

### Weight residency and capacity binding

The expanded grammar can keep each prefill weight stripe in private SRAM
across row tiles and reserve the full source strip in global SRAM until the
last local fill. All searches can use this mapping. At context 768, adding
this option reduces the best EDP by 47.0% relative to the initial grammar.

Mapping-first capacity binding groups hardware by PE shape, bank count
and per-bank service cycles. For each addressed layout it computes the
global and private capacity requirements once. Within a group it discards
a feasible macro configuration only when another feasible configuration
has no greater read, write or leakage cost at each level. Their addressed
transactions and dispatch times are identical. The grouped architecture
sweep has the same rule. It removes 112 feasible pairs per workload and
cuts median generation time by 18–28% relative to joint search without
binding. Both complete sweeps and both joint searches agree on EDP.

Seven cases were run locally on Windows, serially in rotating method
order, with three repetitions, 13 hardware points and a common SRAM area
limit of 1.346496 mm². The table reports final EDP normalized to capacity
binding and median cold time (including candidate generation). The
bank-aware architecture selector includes all ties; the near variant
also includes all points within 2% of its optimistic score. Both fully
remap the selected points using the addressed evaluator.

| Workload | Near selector EDP ratio | Separate phase selector EDP ratio | Binding time (s) | Near selector time (s) | Grouped complete sweep time (s) |
|---|---:|---:|---:|---:|---:|
| Context 512 | 1.1110 | 1.0000 | 0.350 | 0.282 | 0.403 |
| Context 768 | 1.0000 | 1.5934 | 0.311 | 0.333 | 0.311 |
| Context 1024 | 1.0000 | 1.0000 | 0.320 | 0.340 | 0.352 |
| Context 1536 | 1.0000 | 1.0000 | 0.597 | 0.586 | 0.598 |
| Asymmetric | 1.0000 | 1.0000 | 0.619 | 0.639 | 0.663 |
| Decode heavy | 1.0000 | 1.0000 | 0.311 | 0.329 | 0.310 |
| Prefill heavy | 1.0000 | 1.3014 | 0.338 | 0.309 | 0.302 |

At 0.5 s in each repetition on context 512, joint binding, joint search
and the complete sweeps returned the same best EDP. That EDP is 10.0%
below either bank-aware architecture selector. The separate-phase selector
also reaches the optimum after a median 3.365 s. The winning 64 × 32 array
uses four 16 KiB banks and 6.613 µs, while the bank-aware selector chooses
two 64 KiB banks on the same array and takes 7.726 µs. At 2 s the bank-aware
selectors still differ only on that case. End-to-end time gains from
binding vary by workload.

The independent replay finds 3.114–9.788 µs of KV and prefill staging
co-residence and 0.479–2.825 µs of cross-request read/write overlap summed
over banks. For a fixed context-768 tile and hardware, the striped,
separated and shared layouts have identical word counts, dynamic energy
and peak aggregate occupancy. Their scheduler bank-wait totals are
3.965, 5.013 and 10.357 µs, and their independently replayed makespans are
13.022, 13.519 and 17.832 µs. Bank placement alone changes executable
latency in this ablation.

The area cap covers CACTI SRAM macros with fixed total MAC count and DDR
bandwidth. The experiment covers one prefill GEMM and one decoder score
operator, uses fixed physical slots and two declared dispatch priorities,
and does not generate AccelForge native FFM address traces. Exactness is
within that finite grammar.

[Expanded Windows report](results/banked_v2_windows.json.gz)

### Wider shortlists and complete cache reservation

The shortlisted architecture-first remapper now also supports all points
within 10% of the best score and the top two points including all ties at
the cutoff. At the original cap and 512-token context, the joint EDP is
9.99% below the 10% shortlist and 7.90% below the top two at 0.5 s across
all three repetitions. The grouped complete sweep reaches the same EDP
under that budget. For three held-out contexts (448, 576 and 704) crossed
with two SRAM area caps (1.211846 and 1.481146 mm²), the top two reaches
the exact EDP in all six cells by 0.5 s. The 10% selector misses it only
at the higher cap and 576 tokens, where joint EDP is 18.89% lower.
[Shortlist result](results/banked_shortlist_512_windows.json.gz) ·
[Smaller cap holdout](results/banked_holdout_1.35_windows.json.gz) ·
[Larger cap holdout](results/banked_holdout_1.65_windows.json.gz)

The complete cache variant requires both K and V to be loaded into
different physical words of the same banked SRAM. V stays allocated
through the last measured decode step; an independent check verifies
all V word fills, completion before the first decode compute, and the
absence of an early release. Every search uses mandatory residency in
this variant. The timed decoder still executes QK scores; a subsequent
value contraction and KV updates are outside the experiment. V is
charged for its initial fill and leakage, and its storage competes with
prefill staging throughout the trace.

| Context | Allocated V | Total global SRAM peak | Full KV and prefill co-residence | Cross-request bank R/W overlap |
|---|---:|---:|---:|---:|
| 256 | 16 KiB | 90,432 B | 4.276 µs | 0.535 µs |
| 384 | 24 KiB | 106,816 B | 4.920 µs | 0.470 µs |
| 512 | 32 KiB | 123,200 B | 4.979 µs | 0.535 µs |

At the original cap the capacity binder and the grouped full sweep tie
all three complete-cache optima. All bank-aware shortlists also match
them by 0.5 s. The isolated-phase selector is worse on two of the three,
by 12.91% and 47.43% when measured as the reduction in EDP from the
selector to the joint optimum. These are differences against the
isolated selector; the complete-cache experiment does not establish a
search advantage over the bank-aware selectors.
[Complete-cache result](results/banked_complete_kv_windows.json.gz)

```sh
python -m research.physical_cost.banked_search research/physical_cost/results/sram_45nm.json /tmp/holdout.json.gz --area-factor 1.65 --cases holdout448 holdout576 holdout704 --methods binding near wide top_two grouped_sweep standalone
python -m research.physical_cost.banked_search research/physical_cost/results/sram_45nm.json /tmp/full-kv.json.gz --cases kv256 kv384 kv512 --methods binding optimistic near wide top_two grouped_sweep standalone
```

### Dependency and bank-port ranking control

The critical-path variants compile the four cheapest distinct mappings
per hardware point. Each probe uses the command DAG's longest path and
the busiest physical port to refine its mapping lower bound. Probe cost
is included in cold runtime and its compilation is reused for dispatch.
The architecture-first controls rank each point by the smallest refined
probe bound, keep either all first-place ties or the first two points
including cutoff ties, then fully remap. Joint search has access to the
same probes. The probe score only ranks architectures; any pruning uses
the certified bound of each individual mapping.

At context 768, the aggregate word counts of the fixed layout ablation
are identical. The inexpensive per-bank bound orders the three layouts
correctly, with shared placement only 13% above striping in predicted EDP.
The command bound raises that separation to 18%, but assigns shared and
separate placement the same bound. Addressed execution puts shared
placement 46% above striping. The command bound is a stronger
relaxation for these mappings, and it still misses contention.

The critical-path top two matches final joint EDP in all ten cells.
At context 512 it matches by 0.5 s in all three repetitions; using only
the cheaper top two still leaves a 7.90% gap. At the higher-cap
576-token holdout, the critical-path top two has 23.29% higher EDP than
critical-path joint search at 0.5 s and matches when allowed to finish.
The cheaper top two already matches by 0.5 s. The grouped full sweep
also matches final EDP throughout. With mandatory K and V residency,
the architecture-first controls and joint search match by 0.5 s in
all three cases. These comparisons establish bank placement and cache
lifetime effects without establishing a general optimizer advantage.

[Critical-path original and complete-cache results](results/banked_critical_1.5_windows.json.gz) ·
[Smaller cap results](results/banked_critical_1.35_windows.json.gz) ·
[Larger cap results](results/banked_critical_1.65_windows.json.gz)

```sh
python -m research.physical_cost.banked_search research/physical_cost/results/sram_45nm.json /tmp/critical.json.gz --cases context512 kv256 kv384 kv512 --methods binding critical_joint critical_first critical_two grouped_sweep top_two
```

## Architecture shortlist scaling

The scale experiment keeps one 2,048-MAC array and the same DDR service
model. It varies the array shape, the number of independent global SRAM
banks (2–24), and the macro type and depth in global and private SRAM.
Multiple identical macros behind the same logical port add capacity,
area and standby leakage. An access uses one macro and the model uses
its calibrated word energy and service period. Selection mux and
routing overhead are outside the area and timing model. The common
4.5 mm² SRAM cap admits 3,302 configurations, of which 2,391–2,715 are
feasible across the five workloads. They form 149 distinct timing
classes. Each class groups equal PE shape, bank count and rounded
global and private port cycles.

The compiler builds an addressed layout and optimistic profile once
per mapping and timing class. Within a class, a design can be removed
when another feasible design admits every mapping it does and has no
larger cost for any action or for standby leakage. Both designs run
each shared mapping with identical command times. This leaves 552–760
architecture points in the five full-grid cells. The experiment reports
fixed shortlist results on the entire feasible grid as well as after
this safe reduction. All fixed shortlists retain ties at the cutoff
and remap over the whole declared grammar.

For a shortlist with exact remapped EDP U and minimum omitted
architecture lower bound B, the global optimum lies in
[min(U, B), U]. The relative optimality gap is at most
U / min(U, B) - 1. In particular, B >= U certifies that the shortlist
contains an optimum. The architecture lower bound is the minimum of
the admissible bounds over all feasible mappings. Ranking by a handful
of command probes is heuristic and is used only to order the shortlist.
An adaptive baseline orders the remaining architectures by admissible
bound, remaps each until the remaining bounds cannot improve the
incumbent, and independently replays every reported winner.

The original 13-point pool is included in every subset. Five fixed
seeds generate nested 64-, 256- and 1,024-point subsets. The full grid
and the anchor each run once per workload. Each cell below is a
workload and subset pair. Entries show misses over cells, followed by
the maximum observed relative EDP regret. The table uses all feasible
points and the exact same evaluator throughout.

| SRAM grid size | Cells | Top 1 | Top 2 | Within 10% | Critical-path top 2 |
|---|---:|---:|---:|---:|---:|
| 13 | 5 | 2/5 (23.29%) | 1/5 (8.58%) | 2/5 (23.29%) | 0/5 (0.00%) |
| 64 | 25 | 21/25 (33.47%) | 14/25 (32.53%) | 6/25 (15.91%) | 10/25 (23.29%) |
| 256 | 25 | 16/25 (42.68%) | 12/25 (28.79%) | 1/25 (4.43%) | 3/25 (4.43%) |
| 1,024 | 25 | 16/25 (28.09%) | 13/25 (16.03%) | 0/25 (0.00%) | 7/25 (5.35%) |
| 3,302 | 5 | 5/5 (16.21%) | 3/5 (9.08%) | 0/5 (0.00%) | 2/5 (6.18%) |

The miss fraction is nonmonotonic. At 3,302 points the 10% window
includes 24–80 feasible designs per workload (22–54 after the safe
reduction) and finds every optimum in this sample. Its omitted lower
bounds do not certify any of those five choices. The exact adaptive
solver certifies the full grids by remapping 54–148 architectures
after reduction. The two largest-grid critical-path misses are 3.95%
regret on context 576 and 6.18% on the 32-step complete-cache case.
Their winners agree with the word-address replay. All values refer
to the banked prefill-GEMM/QK grammar. The diagnostic shares work
across nested subsets, so its aggregate runtime is not a cold
comparison of search methods.

[Scale report](results/banked_scale_450_windows.json.gz)

```sh
python -m research.physical_cost.banked_scale research/physical_cost/results/sram_45nm.json /tmp/scale.json.gz
```

The plot summarizes the same nested cells. Each size labels its number
of workload/subset pairs. Shared anchor points and nested seeds make
these descriptive frequencies.

![Shortlist misses and maximum EDP regret](results/banked_scale_450.svg)

```sh
python -m research.physical_cost.plot_banked_scale research/physical_cost/results/banked_scale_450_windows.json.gz /tmp/scale.svg
```

### Cold search at 3,302 architecture points

The cold comparison regenerates the grid, mapping profiles and safe
dominance reduction for every run. Each method begins with the same
verified feasible seed. The adaptive method opens complete remaps in
order of architecture lower bound. The joint method interleaves
mappings across architectures and lazily refines their bounds with the
command DAG. The two fixed shortlists fully remap their selected
architectures. Every improvement is checked by the independent word
replay before its timestamp is recorded. Five repeats rotate the method
order. Timing starts before grid construction and includes selection,
compilation and verification. The precomputed CACTI characterization
table is shared.

| Workload | Method | Median time to exact EDP | Median total time (range) | Schedule checks | Final regret | Certified |
|---|---|---:|---:|---:|---:|---|
| Context 576 | Adaptive | 4.536 s | 6.429 s (6.329–6.933) | 166 | 0% | Yes |
| Context 576 | Joint | 5.637 s | 6.222 s (5.748–7.055) | 150 | 0% | Yes |
| Context 576 | Within 10% | 4.492 s | 5.260 s (5.205–6.688) | 128 | 0% | No |
| Context 576 | Critical-path top 2 | — | 12.458 s (12.275–13.769) | 12 | 3.95% | No |
| 32-step K+V | Adaptive | 3.128 s | 8.401 s (8.101–8.986) | 544 | 0% | Yes |
| 32-step K+V | Joint | 4.466 s | 9.251 s (9.005–9.357) | 544 | 0% | Yes |
| 32-step K+V | Within 10% | 3.136 s | 6.209 s (6.131–6.321) | 230 | 0% | No |
| 32-step K+V | Critical-path top 2 | — | 18.255 s (18.164–18.939) | 32 | 6.18% | No |

In context 576, the adaptive baseline reaches the exact EDP at the
5-second checkpoint in 5/5 runs, the 10% window in 4/5, and joint
search in 0/5. The first three methods reach it in all five long-cache
runs at 5 seconds. The critical-path selector spends most of its time
compiling candidates for architecture ranking. Those compilations
are included in total time and separately reported. The joint search
reduces schedule checks in one case and reaches the optimal EDP later
in both. The 10% policy attains that EDP with no global certificate.

[Cold comparison](results/banked_scale_cold_450_windows.json.gz)

```sh
python -m research.physical_cost.banked_scale research/physical_cost/results/sram_45nm.json /tmp/scale-cold.json.gz --cases holdout576 kv_long --cold-repeats 5
```

### Certifying the omitted architectures

Both certifiers start with the exact remapped 10% shortlist, its
verified incumbent, and copies of the same command and schedule
caches. They must exclude every remaining architecture. The
architecture certifier remaps by lower bound. The family certifier
groups feasible mappings with identical addresses, dependencies and
service periods. At a fixed mapping and duration it takes the minimum
EDP across the actual feasible members, using each member's dynamic
energy and leakage. A family can be rejected when this minimum at the
command latency bound reaches the incumbent. Otherwise it uses the
faster of the two addressed schedules and checks the member costs
at that duration. Identical timing allows one dispatch to cover
all members with the same priority, while capacities and prices
are evaluated per member.

All five incumbents were certified by both methods in all repeats.
These times start after shortlist remapping. The new work columns
are identical for both methods because the architecture baseline
already caches equivalent command timings.

| Workload | Omitted designs after dominance | New compilations | New schedules | Architecture median (s) | Family median (s) |
|---|---:|---:|---:|---:|---:|
| Context 512 | 713 | 164 | 6 | 1.152 | 1.164 |
| Context 576 | 712 | 164 | 20 | 1.296 | 1.322 |
| Complete K+V | 536 | 134 | 0 | 0.917 | 0.997 |
| 32-step K+V | 563 | 172 | 272 | 2.658 | 2.834 |
| Asymmetric K+V | 498 | 106 | 6 | 1.496 | 1.491 |

The long-cache case has 314 vs 288 logical schedule checks with
identical physical dispatch counts. This comparison establishes a
practical certificate for the 10% window. Batching the proof by
timing family adds no measured reduction in new addressed evaluations.

[Certificate comparison](results/banked_scale_proof_450_windows.json.gz)

```sh
python -m research.physical_cost.banked_scale research/physical_cost/results/sram_45nm.json /tmp/scale-proof.json.gz --proof-repeats 5
```

## Scaling timing classes with DDR and PE count

The addressed evaluator now gives the DDR port a configurable integer
service time per 64-byte word. The four settings are 1, 2, 4 and 8 ns,
or effective rates of 64, 32, 16 and 8 GB/s. The DMA and global bank
occupy the slower of their two service periods. The analytic bound,
command evaluator and independent word replay use the same setting.
The PE counts are 1,024, 2,048 and 4,096. Each panel enforces a separate
MAC ceiling and a CACTI SRAM area cap. MAC area and DDR interface area
are outside that SRAM budget, and per-word DDR energy is held fixed.

The timing key includes the PE X axis, the two actual Y-axis fold
counts for the prefill and decoder reductions, the bank count and
the global, private and DDR service periods. This merges nominal
PE geometries when both reductions are saturated. Capacity and
action prices remain design-specific. Safe dominance is applied
separately at each area cap before architecture best-first remapping.
The tests compare cross-DDR and cross-PE schedule reuse with an
unpruned enumeration and the independent word replay.

For fixed 32 GB/s, the following cells show effective classes,
opened classes and classes where the search actually dispatches at
least one addressed schedule. A class is opened when the architecture
bound is too low to dismiss its remap before considering its mappings.

| Workload | 1.35 mm² effective / opened / dispatched | 2.70 mm² effective / opened / dispatched | 4.50 mm² effective / opened / dispatched |
|---|---:|---:|---:|
| Context 576 | 63 / 8 / 3 | 198 / 64 / 32 | 378 / 96 / 44 |
| 32-step K+V | 45 / 6 / 4 | 189 / 28 / 23 | 378 / 65 / 40 |
| Asymmetric K+V | 33 / 6 / 4 | 189 / 56 / 33 | 378 / 79 / 44 |

At 4.5 mm², each of the four fixed-DDR panels has 378 effective
classes and the adaptive proof opens 21–96 of them (5.6–25.4%).
The combined envelope at that cap admits 39,624 SRAM designs, with
1,788 nominal and 1,512 effective timing classes in each workload.
It opens 46–86 classes. All three combined winners use the fastest
DDR setting. The fixed-DDR panels keep that bandwidth effect out of
their denominators. The proportion of opened classes varies with
workload, area and DDR speed. The report records both the architecture
and timing-class counts, including how many bounds remain strictly
below the verified final incumbent. These are search-work counts.
The diagnostic shares profile construction across panels.

[DDR and PE scaling report](results/banked_axes_windows.json.gz)

```sh
python -m research.physical_cost.banked_axes research/physical_cost/results/sram_45nm.json /tmp/axes.json.gz
```

## Native FFM check with AV and FFN

The native probe loads the AccelForge GPT-3 block example with eight
tokens, width 64, four 16-wide heads and FFN width 256. It includes
the input copy, Q/K/V projections, QK, the example's elementwise
softmax proxy, AV, output projection and both FFN GEMMs. FFM generates
and joins mappings independently at each of five SRAM-admitted
architectures. Fusion is capped at one loop. The best joined
energy/latency row is replayed through AccelForge evaluate_mapping
and the two values must agree before reporting the leakage-adjusted
EDP. This uses the native aggregate memory model. KV append and
address-level overlap are outside this probe.

The compute-only lower bound uses compulsory contraction MACs,
ideal utilization of the chosen array and nonnegative SRAM leakage.
The five architectures all required remapping. The best EDP is
6.762e-12 J s on the 32 × 128 array with four 16 KiB global banks
and 64 GB/s DDR. The bound agreed with the exhaustive architecture
result. Every FFM frontier contained one row and replay matched
energy and latency at all five points. The timings are smoke-run
diagnostics for the declared block and fusion limit.

[Native compute-bound report](results/native_block_compute_windows.json.gz)

The cold DDR cut also charges the six compulsory external projection
and FFN weight reads. MainMemory is their backing store in this
specification. The bound adds their bit energy to mandatory MAC
energy and uses the maximum of ideal array service and required
single-DDR read service. SRAM standby leakage is charged over
that latency bound. Intermediate activations, output writeback,
and startup costs are relaxed. The replay explicitly checks each
of the six weights and finds 393,216 read bits (48 KiB) on every
architecture.

The cold cut opens four of the five architectures. It eliminates
the 16 GB/s point with a lower bound of 9.283e-12 J s after finding
an incumbent of 6.762e-12 J s. The independent full remap of the
excluded point gives 1.814e-11 J s. The three architectures with
fixed 32 GB/s all still require remapping. The elimination is
specific to the mixed DDR pool. This probe uses FFM's native
bit-granular aggregate memory model and the same graph and
fusion limit as the compute-only check.

[Native cold DDR report](results/native_block_cold_cut_windows.json.gz) ·
[Original FFM paper](https://arxiv.org/abs/2602.15166)

```sh
python -m research.physical_cost.native_block research/physical_cost/results/sram_45nm.json /tmp/native-block.json.gz --cold-ddr-bound
```

## Joint area budget with paid DDR and MAC choices

This sweep charges one common budget for the two SRAM levels, the
MACs, and the DDR I/O and digital PHY area estimate. The SRAM
entries are the existing 45 nm CACTI table. For the INT8 PE, Yosys
0.61 synthesizes the registered multiply and signed 32-bit accumulator.
Generic gates and mapped flops are priced using the pinned Nangate45
X1 cell areas. The sum is 1,180.508 µm² per PE. This is standard cell
area before routing and clock implementation.

DDR I/O area and read, write and idle power come from the pinned
CACTI external I/O routines with one loaded rank per channel.
The additional digital PHY area is the modeled I/O area times
0.551 / 3.820, the digital-to-I/O ratio of the published DDR3
controller. This ratio is a proxy for the digital part of the DDR4
design. DDR4-2000 channel replication represents 8, 16 and 32 GB/s.
The 64 GB/s point uses five 32-bit DDR4-3200 channels. The scheduler
still represents their aggregate bandwidth as one shared port.

| DDR (GB/s) | I/O + digital PHY (mm²) | Read (pJ/bit) | Write (pJ/bit) | Idle (mW) |
|---|---:|---:|---:|---:|
| 8 | 1.810 | 14.792 | 16.152 | 57.361 |
| 16 | 2.907 | 12.874 | 14.233 | 63.121 |
| 32 | 5.815 | 12.874 | 14.233 | 126.242 |
| 64 | 10.535 | 10.712 | 11.744 | 325.686 |

Transfer energy is active minus idle power divided by aggregate bit
rate. Idle interface power is charged once over elapsed execution
time. Replicating identical channels preserves incremental pJ/bit
and increases area and idle power. The nominal energy estimate uses
the modeled interface. At 32 GB/s its active price already exceeds
the old fixed 7.03 pJ/bit, so the residual DRAM core energy is zero
in the nominal ledger. The optional device term permits sensitivity
analysis. Controller logic, package, array routing and PE idle power
are outside this model.

Each total-area cap adds 1.35, 2.70 or 4.50 mm² to the area of
the 2,048-MAC and 32-GB/s reference without SRAM. Those same
9.582, 10.932 and 12.732 mm² limits apply to every hardware choice.
The three workloads all choose 32 GB/s at each limit. The winning
MAC count varies between 1,024 and 4,096. The 64 GB/s tier is
infeasible at the first two limits. At the last it admits only
1,024-MAC designs and still loses wherever a mapping fits.

The fixed 32 GB/s panel gives the following numbers of opened
versus effective timing classes.

| Workload | 9.582 mm² | 10.932 mm² | 12.732 mm² |
|---|---:|---:|---:|
| Context 576 | 40 / 94 | 64 / 195 | 80 / 318 |
| 32-step K+V | 15 / 86 | 41 / 192 | 67 / 317 |
| Asymmetric K+V | 40 / 81 | 28 / 192 | 67 / 315 |

At the largest cap, the fixed 32 GB/s proof opens 21.1–25.2% of
classes. At smaller caps it can open up to 49.4%. The report records
actual dispatch separately. The counts describe this model and these
sizes. The mixed-DDR denominator includes service classes with very
different bandwidth, and no asymptotic claim follows from the sweep.

[Raw calibration ledger](results/paid_ledger.json) ·
[Paid-area scan](results/paid_area_windows.json.gz) ·
[CACTI-IO](https://users.cs.utah.edu/~rajeev/cacti7/) ·
[Controller area table](https://kluedo.ub.rptu.de/files/8310/Diss_Chirag_Sudarshan_wo_DOB.pdf)

```sh
# Use the revisions and Liberty hash in results/paid_ledger.json.
yosys -p 'read_verilog mac_int8.v; synth -top mac_int8 -noabc; dfflibmap -liberty nangate.lib; write_json mac.json; stat'
g++ -std=c++11 -O2 -I "$cacti" ddr4_probe.cc "$cacti/extio.cc" "$cacti/extio_technology.cc" -o ddr4_probe
# Run from the repository root after producing the local probe and netlist.
python -m research.physical_cost.calibrate_ledger /tmp/mac.json /tmp/nangate.lib /tmp/ddr4_probe /tmp/ledger.json
python -m research.physical_cost.paid_area research/physical_cost/results/sram_45nm.json research/physical_cost/results/paid_ledger.json /tmp/paid-area.json.gz
```

At fixed 12.732 mm² and context 576, scaling only the interface area
by 0.8 selects 64 GB/s and 2,048 MACs, with 17 of 1,324 mixed
effective classes opened. Scaling it by 1.2 selects 32 GB/s and
2,048 MACs, with 84 of 1,058 opened. The nominal winner is 32 GB/s
and 4,096 MACs. A 4 pJ/bit incremental device term at nominal
area keeps that winner and changes fixed 32 GB/s openings from
80 to 83 of 318. The bandwidth conclusion depends on the PHY
estimate. Each sensitivity holds the absolute area limit fixed.

[PHY ×0.8](results/paid_phy080_windows.json.gz) ·
[PHY ×1.2](results/paid_phy120_windows.json.gz) ·
[DRAM device sensitivity](results/paid_device4_windows.json.gz)

## Historical native prefill and decode with PHY area charged

All three candidates run at 32 GB/s and fit the same 12.732 mm²
budget. They have 1,024, 2,048 and 4,096 MACs and respectively 768,
576 and 256 KiB of global SRAM. The candidates use the largest
number of 64 KiB banks within this cap for each shape, with
32 private 1 KiB SRAMs. Total areas are 12.378, 12.309 and
12.597 mm².

Native FFM remaps a 256 × 256 × 256 prefill projection and a
single-query attention graph with QK, the elementwise normalization
proxy and AV. The decode graph operates on a fixed four-head group
with 16 values per head. The episode runs prefill and decode in
series on the same hardware. The decode reuses the fixed K/V
inputs across autoregressively ordered queries. The model allows
either cold DDR reads each time or a complete cache reservation
with one charged fill. The resident case removes the full K/V
size from staging and retains the native mapper's active tile
reservations in the remaining space. Every joined frontier row
is replayed, including the per-tensor DDR action counts. Resident
K/V has zero off-chip reads after the initial fill. Fusion is
limited to one loop. This is a native aggregate model of a
fixed-context episode. It excludes concurrent requests, cache
append and partial residency from the mapped candidates.

The 4,096-MAC prefill takes 6.144 µs, compared with 16.384 µs
on 1,024 MACs. At context 5,120 only the latter can reserve
the 640 KiB cache. Its resident decode takes 24.320 µs per step.
Cold decode takes 42.244 µs per step. The shared optimum switches
at longer decode phases. The independent-hardware comparator
minimizes the product of summed energy and latency over both
complete phase frontiers.

| Context | Decode winner at 8 steps (MACs) | Shared hardware EDP penalty at 8 steps | At 32 steps | At 128 steps |
|---|---:|---:|---:|---:|
| 4,096 | 2,048 | 2.85% | 0.87% | 0.23% |
| 5,120 | 1,024 | 9.04% | 2.61% | 0.68% |
| 6,144 | 4,096 | 0% | 0% | 0% |

The last case has no room for both a complete cache and staging
on any candidate. At one decode step the prefill and decode
winners agree in all three contexts.

The boundary lower bound charges native compulsory input and
output activation traffic, including the prefill X read and P
write (64 KiB each). It also charges required weight reads and
uses the maximum of ideal compute and compulsory DDR service.
The capacity relaxation gives K/V all modeled on-chip storage
at a step boundary, including private SRAM and registers. If the
cache exceeds that capacity, the excess must be fetched before
each subsequent complete scan. The initial cache fill is charged
once. Intermediate scores and other internal activations can
stay on chip for free in the bound.

We compare both bounds against full native remapping of the
three architectures. The lower bound that assumes cold or fully
resident modes opens one of three at context 5,120 and 32 or
128 steps, and two at eight steps. The relaxed capacity bound
allows arbitrary partial residency and opens all three. These
are proof-work counts reconstructed from the verified frontiers.
The restricted-mode result does not establish pruning for
native partial caching or for arbitrary attention graphs.

[4,096 context](results/paid_native_4096_windows.json.gz) ·
[5,120 context](results/paid_native_5120_windows.json.gz) ·
[6,144 context](results/paid_native_6144_windows.json.gz)

The timings and shared penalties above describe the legacy mapping and
area/energy ledger at revision `e563bc4b`. The rerun below supersedes
that decode timing when interpreting the KV-capacity tradeoff.

```sh
python -m research.physical_cost.paid_area research/physical_cost/results/sram_45nm.json research/physical_cost/results/paid_ledger.json /tmp/paid-sensitivity.json.gz --cases holdout576 --caps 12.732443088031802 --phy-scale 0.8
```

## Native decode timing audit and fixed-bandwidth rerun

At context 5,120 on the 32 × 32 HP architecture at 32 GB/s,
QK and AV already each use 512 spatial instances in the legacy
plan. The pointwise normalization proxy has no spatial loop.
It processes 20,480 elements at one per ns. In the legacy cold
plan, QK and AV each take 10.882 µs at MainMemory and the
normalization takes 20.480 µs at MAC. This accounts for all
42.244 µs. The action counts show one full scan of K and V,
320 KiB each. Scores and Prob each make a 20 KiB write and
read, totaling another 80 KiB. That traffic explains the
23.044 µs summed DDR service. The normalization's legacy
1.280 µs DDR service fits inside its 20.480 µs MAC time.

The `spatial` ablation permits partitioning the normalization
input and output on the existing two fanouts. The `gemv` variant
also lets FFM choose whether to spill Scores and Prob. The
contractions retain their broadcast axes and existing reduction
paths. All joined plans are replayed with their action counts and
per-operator service times. An independent calculation from the
replay records reconciled exact DDR traffic and summed stage
maxima for all 32 decode plans.

| Mapping at 5,120 | Cold (µs/step) | Resident (µs/step) | Scores and Prob DDR traffic |
|---|---:|---:|---:|
| Legacy | 42.244 | 24.320 | 80 KiB |
| Spatial only | 23.044 | 5.120 | 80 KiB |
| Spatial and optional spills | 20.511 | 3.867 | 0 |

In the corrected cold plan, the two DDR stages take 10.242 µs
each and on-chip normalization takes 0.027 µs. Cold is within
0.15% of the raw 20.480 µs K/V transfer time. In the resident
plan, QK and AV are limited by WeightBuffer service at 1.280
and 2.560 µs. This raises effective useful QK+AV throughput
over the whole decode step from 26.9 to 169.5 MAC/ns. These
resident timings exclude the one-time fill. Its cost is included
in episode EDP using balanced stripes and aggregate streaming service.

Bandwidth is a fixed system condition in each panel. The native
area cap is 6.918 mm² for SRAM and MACs. The three HP shapes
use 12, 9 and 4 global banks. PHY transfer and idle energy remain
in the ledger. The incremental DRAM core charges are 6.852
pJ/bit for reads and 5.554 pJ/bit for writes, derived from x8
DDR4 burst currents and full-row amortization of ACT/PRE.
Total active prices at 32 GB/s are about 19.73 and 19.79 pJ/bit.
The core model assumes the row amortization in the fixture
and excludes device refresh, additional device background
energy and controller queuing. MAC area retains the earlier
`synth -noabc` calibration. [DRAMPower DDR4 VDD fixture](https://raw.githubusercontent.com/tukl-msd/DRAMPower/master/tests/tests_drampower/resources/ddr4.json)

| Context, HP at 32 GB/s | Cold, 1,024 MACs (µs) | Resident, 1,024 MACs (µs) | Shared EDP penalty at 8 / 32 / 128 steps |
|---|---:|---:|---:|
| 4,096 | 16.409 | 3.093 | 7.63% / 3.72% / 1.31% |
| 5,120 | 20.511 | 3.867 | 28.16% / 12.39% / 3.99% |
| 6,144 | 24.612 | Infeasible | 0% / 0% / 0% |

The shared penalty compares one architecture with an idealized
pair of independently chosen architectures, each under the same
area cap. At 5,120 and 8 steps the 4,096-MAC prefill preference
and the 1,024-MAC resident decode preference persist at 16,
32 and 64 GB/s. The respective penalties are 11.60%, 28.16%
and 41.77%. The same ledger and architecture give an 8.40%
penalty with the legacy mapping at 32 GB/s. At 6,144 the largest
global SRAM has no staging after reserving all K/V.

The [45 nm LSTP table](results/sram_45nm_lstp.json) was generated
from the same CACTI revision with cell and peripheral device
types changed. A 64 KiB macro has 0.0194 mW leakage, versus
93.42 mW for HP. The area is 0.4827 versus 0.4259 mm² and
the modeled service takes three versus one ns. Remapping under
the same 6.918 mm² cap gives 11, 8 and 3 banks on LSTP. At 5,120
and 32 GB/s, the 1,024-MAC resident step changes from 3.867 µs
and 6.259 µJ to 4.087 µs and 2.425 µJ. The preferred prefill
shape becomes 2,048 MACs. At 8 / 32 / 128 steps the corresponding
shared penalties are 14.85% / 6.16% / 1.97%. This sensitivity
recharacterizes the entire SRAM, including its timing and area.

At context 5,120 and 32 GB/s the partial-cache relaxation opens
two of three HP architectures at 8, 32 and 128 steps. The
declared cold/full-resident bound opens one. The work counts
are reconstructed from full remaps. The episode uses a
pointwise normalization proxy, three shapes and serial phases.
The shared penalty measures hardware conflict for those phases.
Partial-resident mappings, true softmax, KV append, concurrent
requests and optimizer comparisons require a different experiment.

[HP 4,096](results/decode_hp4096_windows.json.gz) ·
[HP 5,120](results/decode_hp5120_windows.json.gz) ·
[HP 6,144](results/decode_hp6144_windows.json.gz) ·
[Legacy](results/decode_legacy5120_windows.json.gz) ·
[Spatial-only](results/decode_spatial5120_windows.json.gz) ·
[16 GB/s](results/decode_bw16_windows.json.gz) ·
[64 GB/s](results/decode_bw64_windows.json.gz) ·
[LSTP](results/decode_lstp5120_windows.json.gz)

The separate banked sweep uses the same per-bandwidth ledger.
At the 6.918 mm² cap the certificate opens the following timing
classes. Dispatch counts are recorded separately in the raw data.

| Workload | 16 GB/s | 32 GB/s | 64 GB/s |
|---|---:|---:|---:|
| Context 576 | 116 / 318 | 84 / 318 | 55 / 318 |
| 32-step K+V | 113 / 317 | 66 / 317 | 62 / 317 |
| Asymmetric K+V | 63 / 315 | 73 / 315 | 29 / 315 |

[Fixed-bandwidth banked sweep](results/fixed_ddr_windows.json.gz)

```sh
python -m research.physical_cost.cacti_sram "$cacti" /tmp/lstp --device itrs-lstp
python -m research.physical_cost.native_serving research/physical_cost/results/sram_45nm.json research/physical_cost/results/paid_ledger.json /tmp/decode.json.gz --context 5120 --bandwidth 32 --mapping gemv
python -m research.physical_cost.external_ddr research/physical_cost/results/sram_45nm.json research/physical_cost/results/paid_ledger.json /tmp/fixed-ddr.json.gz
```
