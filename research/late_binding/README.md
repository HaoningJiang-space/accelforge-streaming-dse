# Mapping-first hardware binding

The screen uses materialized, serial operators and AccelForge's NVDLA template.
It captures the native tile rows before cross-template Pareto, including the
enumerator's own earlier reductions. The envelope is 32 × 192 PEs, 2 MiB of
GlobalBuffer, and 8 bits per Register instance. The experiments vary PE
dimensions, GlobalBuffer capacity, and its read and write bandwidth together.
The budget is normalized as PE count / 6144 + GlobalBuffer bits / 16777216 +
bandwidth multiplier / 2 ≤ 1.5. Energy uses fixed native action prices and
zero leakage. Latency uses the native per-component costs and a maximum within
each operator, summed across operators. This scope covers the native
unfused latency column. The experiment models neither a physical area budget
nor separate graph-level fill, staging, or port calendars.

| Workload | Native tile rows | Exact signature frontier | 10% EDP boxes | Exact bound survivors | Boxes and bound survivors |
|---|---:|---:|---:|---:|---:|
| [GLU](results/kill_frontier_glu.json) | 4,442 | 3,277 | 3,257 | 4 | 4 |
| [Attention](results/kill_frontier_attention.json) | 2,466 | 1,703 | 1,697 | 3 | 3 |
| [ResNet bottleneck](results/kill_frontier_resnet.json) | 7,190 | 2,871 | 2,846 | 22 | 12 |

All 11 operators meet the 1,000-residual threshold with the exact bound alone.
The bound uses a common feasible incumbent. For each candidate, it uses the
fastest bandwidth compatible with that candidate's demand. The remaining
operators contribute separate minima of energy and latency over their own
relaxed architectures. The graph bound is the product of the energy sum and
the latency sum. The incumbent equals the relaxed bound for GLU and Attention
to reported precision. ResNet's incumbent is 0.092% above the relaxed bound.
These certificates apply to the captured candidate banks.

Exact dominance compares PE and SRAM requirements, aggregate action counts
per component and action, and the service time of each independently scaled
component. The boxes retain exact demand antichains. Costs in a box differ
by at most √1.1 per coordinate, including a separate bin for zeros. One
replacement per operator bounds serial EDP inflation by 1.1. The two-layer
oracle enumerates mapping pairs at 12 hardware points, regenerates native
tiles at each point, checks the exact and approximate fronts, and verifies the
bound against continuous bandwidth binding on the tiny bank.

The workload equations use the repository's GLU and Attention proxies. The
ResNet workload includes the residual Add and an implicit zero-padding halo.
Its convolution charges the full iteration space at the boundary. Runs used
a local Windows watchdog with per-workload limits of 240 seconds and 2 GiB
working set. The ResNet case took 108 seconds. On Linux, use the existing
watchdog from an AccelForge environment.

```sh
research/tracking_audit/run_capped.sh 2 240 /tmp/frontier.log -- \
  python -m research.late_binding.kill_frontier resnet /tmp/resnet.json
python -m pytest -q research/late_binding/tests/test_kill_frontier.py
```

[DOSA](https://people.eecs.berkeley.edu/~ysshao/assets/papers/dosa-micro2023.pdf)
already uses mapping-first multilayer co-search, and
[SENNA](https://doi.org/10.1145/3705731) already combines layer requirements
by a componentwise maximum. The remaining question is whether certified
search improves time to end-to-end EDP on a large shared space. This screen
measures candidate compression and does not compare optimizers.

## Discrete shared-budget comparison

The prototype gives the same exact signature bank, five hardware anchors, and
serial EDP evaluator to direct binding, random search, GA, and Optuna TPE.
Each architecture-first query minimizes whole-graph EDP over the fixed
hardware using an exact two-dimensional energy and time frontier. All methods
can take the fastest affordable bandwidth, since energy is fixed and latency
is monotone in bandwidth. The grid has 32 × 192 PE dimension choices, 64
GlobalBuffer sizes at 32 KiB spacing, and 15 bandwidth steps of 1/8.
The normalized resource budgets of 1.5 and 0.75 admit 3,810,792 and 629,028
hardware points respectively. After taking the fastest bandwidth, there are
371,585 and 145,551 hardware points. The complete architecture-first oracle
reduces those points further by checking only exact candidate demand
breakpoints. Between breakpoints, extra hardware has the same feasible
candidate set and leaves weakly less bandwidth.

Direct binding takes the maximum of PE and SRAM demands for each mapping
prefix and computes its fastest affordable bandwidth. Each remaining layer
contributes its lowest energy and its lowest latency at that rate.
Future demands can only reduce bandwidth, so their relaxation yields a
lower bound on the prefix's best graph EDP. A leaf binds its cheapest legal
PE geometry and SRAM capacity and uses the resulting fastest bandwidth.
The independent architecture sweep certifies the optimum over the same bank.
Across the six workload-budget pairs it checks 141–2,034 breakpoints.
It reaches the common optimum in 0.4–2.0 ms, faster than direct binding in
five pairs. Completing the sweep to prove optimality takes 19–414 ms,
compared with 1.2–2.9 ms for direct binding.

| Workload | Tight-budget direct search | 25 ms median regret, random / GA / TPE | 1 s median regret, random / GA / TPE |
|---|---:|---:|---:|
| [GLU](results/grid_glu.json) | 2.7 ms | 3.85% / 9.01% / 54.93% | 0 / 0 / 0 |
| [Attention](results/grid_attention.json) | 1.3 ms | 4.01% / 4.01% / 6.93% | 0 / 0 / 0 |
| [ResNet bottleneck](results/grid_resnet.json) | 2.9 ms | 12.18% / 12.18% / 16.68% | 2.92% / 0.39% / 3.43% |

Five seeds per stochastic method. At the wide budget, the shared anchors
already attain the bank optimum for GLU and Attention. At the tight budget
the GA reaches ResNet's bank optimum in two of five one-second runs.
The timing table excludes the shared native enumeration and the common
preprocessing and anchors. The JSON records preprocessing, anchor timing,
per-seed checkpoints, architecture sweep, and fresh native regeneration
at the optimum hardware witnesses. Capturing and screening the native
candidate bank takes 15–108 seconds in these cases.

Fresh native tiles reproduce the bank optimum at five of six witnesses.
At the tight ResNet hardware, 32 × 96 PEs and 128 KiB, fresh native
generation lowers EDP by 1.22% at the same bandwidth. The envelope bank
therefore misses a native choice, and both exact searches certify only
the captured bank. The result characterizes the serial, fixed-price model
and an integer budget proxy.
A physical-area and port-contention evaluator, full graphs, and a common
execution comparison with accelerator-specific systems are needed to test
the stronger research claim.

### Candidate coverage repair

Native tile enumeration treats the two PE dimensions as feasibility
constraints and optimizes total latency at its generation bandwidth.
The `--retain-hardware-objectives` experiment also passes each PE demand
and component service time to the native tile Pareto pass. It recovers
the tight-budget native ResNet EDP of 2.92805 × 10¹⁴ pJ·ns at the same
32 × 96 PE, 128 KiB, and 0.375× bandwidth witness. The wide-budget
witness also agrees. Candidate capture and screening grows from 7,190
to 177,426 rows and from 108 to 218 seconds. The 38,720 exact signatures
leave 18 layer candidates after the wide-budget conditional bound.
Both hardware witnesses match fresh native generation. General
coverage across every architecture remains an open verification task.
[Coverage repair data](results/resnet_coverage_repair.json)

```sh
python -m research.late_binding.kill_frontier resnet /tmp/resnet.json --bank /tmp/resnet.npz
python -m research.late_binding.late_binding_grid /tmp/resnet.npz /tmp/resnet_grid.json
python -m research.late_binding.late_binding_grid resnet /tmp/resnet_grid.json --replay-native
python -m pytest -q research/joint_synthesis/tests research/late_binding/tests
```

Use `--retain-hardware-objectives` on the first command to generate the
larger ResNet bank and rerun the comparison.

The grid benchmark uses Optuna 5.0.0. Pass `--optuna-path` for an existing
vendor directory if Optuna is outside the active Python environment.

[Spotlight](https://www.cs.utexas.edu/~lin/papers/hpca23.pdf),
[HASCO](https://arxiv.org/abs/2105.01585), and
[UNICO](https://doi.org/10.1145/3613424.3614282) use Bayesian or learned
search components. [FAST](https://doi.org/10.1145/3503222.3507767) already
covers hardware, scheduling, fusion, and padding. These are system-level
comparators beyond the random, GA, and TPE controls in this experiment.
