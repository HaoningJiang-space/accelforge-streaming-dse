# Conditional elimination: six terminal Join probes

Base revision: `5e265f48c5dd065cbc93c1bda6fdf3e0a59bfb12`.
This is a restricted aggregation-law experiment for graph-structured
architecture–mapping co-optimization. It is not a new complete search engine or
an end-to-end performance benchmark. The original FFM implementation is unchanged.

## Actual pair materialization

All modes receive the same generated candidate store and saved prefix. Only the
last consumer is advanced. `coordinates` retains original tensor metadata and
uses coordinate dominance; `live_coordinates` drops metadata unused by this
no-adjust terminal program; `effect` compares native resource response functions.

| Workload | PE shape | GB bytes | Native | Coordinates | Live coordinates | Effect | Pair reduction |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2mm, M=4, KN=8 | 4×8 | 96 | 48 | 48 | 48 | 48 | 0% |
| 3mm, M=4, KN=8 | 4×8 | 128 | 130 | 130 | 130 | 91 | 30.00% |
| 2mm, M=4, KN=8 | 8×4 | 96 | 50 | 50 | 50 | 50 | 0% |
| 3mm, M=4, KN=8 | 8×4 | 128 | 180 | 180 | 180 | 132 | 26.67% |
| 2mm, M=16, KN=16 | 16×16 | 4,096 | 110 | 110 | 110 | 110 | 0% |
| 3mm, M=16, KN=16 | 16×16 | 4,096 | 394 | 394 | 394 | 302 | 23.35% |

These are actual matched rows materialized by the **final Join**, before its
capacity filtering and local Pareto. Earlier Join work and generation are not
included. The earlier decision-hypergraph audit's 697-pair 3mm total covered all
Join stages and is not a baseline for the 394-pair terminal count here.

The effect mode removes 19, 17 and 33 producer-row occurrences in the respective
3mm consumer buckets. These are not global Mapping deletions. The comparison
uses local E/T, required fields and symbolic resource effects. It reads neither
a target optimum nor an enumerated completion-response oracle.

## Correctness evidence

- All three reductions at all six points match the complete native numeric
  frontier and Mapping source identities, rather than only minimum EDP.
- All 45 final effect-result instances reconstruct and re-evaluate successfully
  using the existing FFM model. They are result instances, not a count of unique
  physical mappings or independent hardware-lifetime validations.
- A separate native-path check compares 816 capacity-checked composed rows and
  2,448 exact resource coordinates against compiled response functions, with no
  unknown transfer cases in these six probes. Those observations are not inputs
  to the elimination rule.
- A unit test additionally checks 156 synthetic producer/consumer bindings
  against native arithmetic with test-only Pareto disabled.
- Invalid units/ranges, uncompiled allocation/free/alias effects, unsupported
  search contracts and proof-budget overflows retain original candidates.
- The targeted run passes **8 tests**. The declared research regression passes
  **658 tests** in 205.63 seconds, including those eight; the counts overlap.

The [contract](../../CONDITIONAL_ELIMINATION.md) spells out the sufficient
max-plus comparison and floating-cost strictness guard. A universal inequality
over consumer resource coordinates is not a universal architecture-family
certificate: architecture, consumer program, units and upstream policy are fixed.

## Interpretation and limits

The coordinate controls eliminate nothing here. The positive difference comes
from comparing resource **effects**: incomparable historical/current resource
vectors can induce ordered terminal responses. This supplies one executable
local law beyond strict-state interning, not a proof of a general sufficient
Fusion boundary, a legal new variable order, or research novelty.

Candidate generation, ordered fallback, prefix Pareto and previous Joins remain
unchanged. Six independent architectures do not show shared cross-architecture
reasoning. Comparisons, copies and expression construction also cost time, so
pair reduction is not evidence of total-time speedup. No DSE/cache speedup or
global-optimality claim is made. Moving this law before candidate generation and
combining it across architecture domains remain open gates.

## Artifacts and reproduction

- [audit.json](audit.json): per-bucket witnesses, exact expressions, all mode
  counts, verification outcomes and implementation SHA-256 fingerprints.
- [summary.json](summary.json): compact counts and explicit scope flags.
- [reading_sources.json](reading_sources.json): pinned P0 reading sources and
  reviewed sections/methods; source bodies are not vendored.
- [regression.txt](regression.txt): declared research-suite output.

From the repository root:

```sh
python -m research.graph_coopt.audit_conditional_elimination --output research/graph_coopt/results/conditional_elimination/audit.json
python -m pytest -q research/graph_coopt/test_conditional_elimination.py --disable-warnings
python -m pytest -q research/tracking_audit research/streaming_join research/graph_coopt --disable-warnings --maxfail=1
```

The diagnostic audit includes observation, copies, native/reduced execution and
reconstruction; its elapsed values are not fair performance measurements. The
known legacy `compatibility_util` collection issue is outside the declared
research suite, which is not an all-repository regression.
