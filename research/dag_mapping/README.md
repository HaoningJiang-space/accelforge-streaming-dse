# DAG mapping: code and experiment guide

The research target is exact mapping search for DAGs with shared data, finite
SRAM and cross-operator fusion. The current priorities and claim boundaries are
in [research/OVERVIEW.md](../OVERVIEW.md). M8 chains are microbenchmarks; no result
here establishes scalable exact search for arbitrary DNN DAGs.

The latest [conditional separation audit](CONDITIONAL_SEPARATION_RESULTS.md)
proves a restricted solve decomposition and checks 10,539 conditional frontiers.
Its optimistic work coverage is limited; it introduces no default optimization.

## Code map

| Layer | Entry | Responsibility |
| --- | --- | --- |
| Native grammar | [graph/curve.py](../index_coupling/graph/curve.py) | Fixed-order solve/group recurrence, Cut DP, loops and retention; unchanged by this cleanup |
| Conditional providers | [response/](../index_coupling/response/README.md) | Prefix sharing, guarded chain responses and witness recovery |
| Region semantics | [boundary.py](boundary.py), [hierarchy.py](hierarchy.py) | Restricted region composition; typed plan decode/encode and independent resource checking |
| Search prototypes | [reuse.py](reuse.py), [downset.py](downset.py) | Opt-in closed-response sessions and order-free recurrence; keep their experiment limits |
| Workloads | [workloads.py](workloads.py) | Shared graph fixtures and certified representative orders; does not import benchmark drivers |
| Audit support | [audit_support.py](audit_support.py) | Prefix-aware call recorder and native conditional response closures; no optimizer |
| Audit rule | [conditional_separation.py](conditional_separation.py) | Resident-separated interval condition, construction, work ceiling and audit CLI |
| Frozen artifacts | [artifacts.py](artifacts.py) | Conservative shared source manifest, freeze checks and Git-pinned source reads |
| Experiment drivers | `study.py`, `bench_*.py` | Case/arm protocols, subprocess limits, timing and archival |
| Read-only analysis | `score.py`, `summarize_*.py`, `work_census.py` | Validate and summarize evidence; work ceilings are not measured speedups |

Graph fixtures belong in `workloads.py`, not in a benchmark. General audit
infrastructure belongs in `audit_support.py`; the candidate rule stays in its
own study. New drivers declare their own files plus `artifacts.source_set(...)`.
The common manifest is deliberately conservative, not a claim that every listed
provider executes in every experiment.

Historical imports remain available: `study.CASES`, `bench_reuse.graph_for` /
`select_orders`, `bench_composition.graph_for`, `conditional_separation.Recorder`
/ `Oracle`, and `score.frozen_bytes`. New code should use the shared modules above.
Existing `python -m` command paths and archived result paths remain unchanged.

## Using existing methods

For the tested DAGs, the strong existing configuration is Prefix + independent
splitting. It is an observed choice on these cases, not an automatic selector:

```python
from research.dag_mapping.workloads import graph_for
from research.index_coupling.response.prefix import make_kernel

graph = graph_for('two_stage_join')
kernel, _ = make_kernel(frames=True, composition='numeric', reductions=True)
points = kernel(graph, partitions='dp', scalar_leaf='v2', witness=True,
                independent_ops=True)
```

For an experiment using guarded analytic responses and their witness recovery:

```python
from research.dag_mapping.reuse import RegionSession

session = RegionSession(graph, unit=True, certificate=True, reductions=True)
points = [(c, q, session.recover(notes)) for c, q, notes in session.query()]
```

Recovery belongs in complete mapping-generation time. Combining all reductions
is supported within the documented guards but is not generally faster. The
specialized Fork quotient and offline C2 analysis remain separate mechanisms.

## Completed studies

The source column identifies the frozen implementation used for the referenced
results. Reproduce historical timings from that commit, not from current main.

| Study / driver | Frozen source | Result and status |
| --- | --- | --- |
| D1: `study.py` | `d3bd0327` | [Protocol](PROTOCOL.md), [results](RESULTS.md): fixed regions, even with a whole-graph outer loop, lose native frontier points |
| Gate 1: `check_hierarchy.py` | `0efa03d7` | [Interface plan](INTERFACE_PLAN.md), [results](RESULTS.md): representation and witness certification; no speedup claim |
| Gate 2: `bench_reuse.py` | `25d77176` | [Results](RESULTS.md): exact closed-response reuse, frozen efficiency gate failed; stopped |
| Gate 3: `bench_downset.py` | `5f30c8f8` | [Results](DOWNSET_RESULTS.md): exact all-order union, efficiency gate failed; stopped |
| Existing reductions: `bench_composition.py` | `646e8f24` | [Results](RESULTS.md): combinations are correct, best configuration depends on structure |
| Analytic combinations: `bench_analytic_composition.py` | `ce7473b8` | [Results](RESULTS.md): transported witnesses correct; no new combination beats the declared strongest old configuration |
| Conditional separation: `conditional_separation.py` | `2047138b` | [Proof](CONDITIONAL_SEPARATION.md), [results](CONDITIONAL_SEPARATION_RESULTS.md): sufficient local decomposition, limited remaining work coverage |

[Related-work checks](RELATED_WORK_CHECK.md) distinguish primary-source evidence
from hypotheses. A historical document's "next step" is not a new active task;
use the overview and the completed-study status above.

## Validation and reproduction

Run from the repository root. The research tests use the standard library:

```sh
PYTHONHASHSEED=0 python3 -m unittest discover -s research/dag_mapping -t .
PYTHONHASHSEED=0 python3 -m unittest research.index_coupling.test_prefix_sharing research.index_coupling.test_prefix_reductions research.index_coupling.test_analytic_composition research.index_coupling.test_unified_search
```

Summaries read the archived commit's source bytes even after main is reorganized.
Write to a fresh output path; never overwrite frozen evidence:

```sh
python3 -m research.dag_mapping.summarize_reuse research/dag_mapping/results/reuse --out /tmp/reuse-summary.json
python3 -m research.dag_mapping.summarize_composition research/dag_mapping/results/composition --out /tmp/composition-summary.json
python3 -m research.dag_mapping.summarize_composition research/dag_mapping/results/analytic_composition --out /tmp/analytic-summary.json
python3 -m research.dag_mapping.summarize_separation research/dag_mapping/results/conditional_separation --out /tmp/separation-summary.json
```

A new run must use committed declared sources. For example, after freezing the
intended implementation, `bench_composition run --out FRESH_DIRECTORY --revision
SOURCE_COMMIT` runs that protocol; `conditional_separation --case two_stage_join
--out FRESH_DIRECTORY` verifies its source against HEAD. Use the existing module
names with `python3 -m research.dag_mapping.<driver>` and inspect `--help` where
provided. Large timing matrices are not part of routine cleanup verification.

Method work continues on `research/main`; no new branch is needed. The existing
hardware integration branch is `research/dnn-benchmarks`. Preserve result files,
Git-pinned manifests and running experiment sources. Changes to module layout
must update declared source dependencies without rewriting old hashes or verdicts.
