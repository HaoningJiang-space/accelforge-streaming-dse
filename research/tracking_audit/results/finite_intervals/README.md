# Finite interval membership and restricted policy-region audit

Base: `7b8fdde8`, with the finite interval changes in the containing commit.
Measurements use one local worker, Python 3.12.14, NumPy 2.3.5, Pandas 3.1.0,
Numba 0.68.1 and paretoset 1.2.5, with hash seed 0 and numerical thread counts 1.
The raw search records include platform, parent commit, dirty-tree indicator and
a source digest. Search timing excludes normalization, comparisons and Mapping
re-evaluation. Both methods use Event enumeration, selective GlobalBuffer tracking,
default late filtering and the same conservative Fusion space. There is no
template-count limit. No other experiment is run concurrently.

## What is implemented

[CAPACITY_REGIONS.md](../../CAPACITY_REGIONS.md) proves the single-interval result
for a fixed complete candidate universe and ordered fallback only. The integer-bit
reference is separate from FFM. The finite backend uses two uint32 **target-index**
endpoints, exact interval intersection and containment, with lossless Bitset
fallback for holes and mixed codecs. Unlisted capacity queries are rejected.

It still constructs Packed enumeration output and scans its bits to detect runs.
The schema contains all K declared labels. This is neither continuous-region
generation nor a proof that every FFM candidate has a single interval.

## Experiment protocol

For each case and K=16/64/256/1024, run one warmup per method and three measured
trials in alternating order. Compare the complete normalized Boolean frontier,
all per-target numerical frontiers, and their dtypes after **every run**. Rebuild
and re-evaluate each method's last selected Mapping at every target capacity.
These are repeated selections, not that many distinct Mappings or an exhaustive
search-space proof. The reference here is the existing Bitset shared search;
these times are not speedups over independently running FFM at every capacity.

Cases:

- GLU `(64,128,256)` / NVDLA, fixed 0.03125–0.25 MiB range.
- Historical MatMul `(2,4,8)` / NVDLA, fixed 64–128-byte range with non-nested
  fallback choices. The targets follow the current normalized floating model;
  this sweep is not integer-byte accuracy evidence.

Generated membership payload is measured without DataFrame index, schema strings,
Tensor objects, provenance or scratch. At K=1024 a Bitset row occupies 128 bytes;
an interval row occupies 8 bytes. This factor of 16 is **field payload**, not RSS.
All generated frames in these cases fit intervals; synthetic hole tests exercise
fallback. Event expansion counts must stay unchanged between representations.

The separate partial-program audit checks all ordered pairs of six usage
expressions with two costs and four threshold profiles in a three-symbol divisor
space bounded by 120, at 32 capacities each. It observes merged cohorts and final membership, compares
all targets to independent FFM enumeration, and checks union values and dtype.
It finds four programs with two-run final membership: a general single-interval
theorem for the existing FFM policy is therefore ruled out. The normalized
three-capacity witness and the prefix-Pareto ablation are saved in
[noncontiguous_witness.json](noncontiguous_witness.json). This synthetic symbolic
program is not a reconstructed real-workload Mapping. See the proof document
for its constraints and scope.

## Reproduction

From the repository root, in the stated dependency environment:

```bash
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
python research/tracking_audit/audit_interval_structure.py --output /tmp/partial_state_audit.json
python research/tracking_audit/repro_noncontiguous_membership.py --output /tmp/noncontiguous_witness.json
for case in counter glu; do
    for k in 16 64 256 1024; do
        python research/tracking_audit/benchmark_membership.py --case "$case" \
            --count "$k" --methods bitset interval --repeats 3 \
            --output "/tmp/${case}_k${k}.json"
    done
done
python research/tracking_audit/audit_membership_structure.py --count 1024 \
    --generation-only --output /tmp/glu_events_k1024.json
python -m pytest research/tracking_audit research/streaming_join -q --disable-warnings
```

## Results

All complete Boolean frontiers and all per-target cost frontiers match across
16 warmups and 48 measured searches. All 5,440 last-run selected Mappings
re-evaluate. This comparison preserves the existing conservative Fusion space;
it does not recover its excluded legal mappings. Raw results are `counter_k*.json`
and `glu_k*.json`; [summary.json](summary.json) gathers timing and work counters.

Warm medians in seconds (three trials per method):

| Case | K | Bitset search | Interval search | Bitset Join | Interval Join |
| --- | ---: | ---: | ---: | ---: | ---: |
| Counterexample | 16 | 0.840 | 0.790 | 0.018 | 0.019 |
| Counterexample | 64 | 0.842 | 0.815 | 0.018 | 0.019 |
| Counterexample | 256 | 0.880 | 0.847 | 0.020 | 0.019 |
| Counterexample | 1024 | 1.013 | 1.057 | 0.027 | 0.020 |
| GLU | 16 | 3.928 | 4.113 | 0.802 | 0.841 |
| GLU | 64 | 4.054 | 4.210 | 0.786 | 0.817 |
| GLU | 256 | 4.386 | 4.440 | 0.841 | 0.844 |
| GLU | 1024 | 5.278 | 5.044 | 1.099 | 0.865 |

Search medians are computed directly, not by adding component medians.
There is no consistent overall speed improvement. At K=1024 the generated
membership payload changes 376,704 -> 23,544 bytes for GLU, and 9,600 -> 600
bytes for the small counterexample. At K<=64 the payload is equal to Bitsets.
The interval mode remains opt-in. Peak RSS is only a whole-process observation
including both representations and validation, not a per-backend comparison.

The representation does **not** reduce enumeration work. These counters agree
between Bitset and Interval; separate `events_*.json` runs add event diagnostics:

| Case | K | State expansions | Expanded rows | Capacity masks executed | Unique generated membership patterns |
| --- | ---: | ---: | ---: | ---: | ---: |
| Counterexample | 16 | 174 | 735 | 279 | 12 |
| Counterexample | 64 | 180 | 753 | 285 | 13 |
| Counterexample | 256 | 180 | 753 | 285 | 13 |
| Counterexample | 1024 | 180 | 753 | 285 | 13 |
| GLU | 16 | 192 | 25,508 | 233 | 5 |
| GLU | 64 | 211 | 34,106 | 302 | 9 |
| GLU | 256 | 233 | 41,966 | 375 | 13 |
| GLU | 1024 | 252 | 55,511 | 438 | 15 |

Capacity masks are the number of masks actually materialized across cohort
checks, not globally distinct physical byte thresholds. All generated rows in
these **two workloads** have one sampled interval. The synthetic partial-program
counterexample shows why that observation cannot justify a universal assumption.

The actionable next step is an exact **union-of-regions** enumerator which derives
supported capacity events without a predeclared grid, retains pruning history,
and preserves holes when equal final Tiles are deduplicated. Replacing Bitsets
by a single enclosing interval would change the existing policy in the saved
counterexample. Neither this codec nor the restricted complete-candidate reference
is that next enumerator.

## Validation

[tests.txt](tests.txt): **344 research/Streaming tests passed**. These include the
5,832 fixed-universe exhaustive cases, integer-bit boundaries for the restricted
reference, multiword/empty interval conversion, exact Pareto and provenance,
domain/dtype/tolerance guards, mixed-codec concat/streaming Join, a capacity ×
bandwidth grid with Mapping re-evaluation, and the noncontiguous FFM reproduction.
The 288-program audit additionally checks 9,216 independent-enumerator projections.
The full proof is restricted to complete candidates; the general FFM single-interval
claim is contradicted by the saved witness. No continuous Mapping-space or
unrestricted Fusion completeness guarantee is claimed.

[source_manifest.json](source_manifest.json) identifies the implementation and
audit sources used with this base. The existing unrelated
`repro_capacity_fraction_history.py` file was not used or modified.
