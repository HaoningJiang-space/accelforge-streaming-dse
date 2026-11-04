# Conditional cross-phase copy witnesses

This records the previous cross-phase investigation as an audit aid. It is not
a physical execution trace, an FFM branch invariant or a pruning certificate.
The current research focus is the [architecture-family certificate](../architecture_family/README.md).

The witness state machine explicitly identifies each final logical `T1[m,n]`
value, its version and one **hypothetical** Copy ID. It requires all values to
be produced before a sequential barrier, each value to exist in that chosen
copy at the boundary, and each to be consumed afterwards. A small concrete input
with identity weights checks values through two mathematical matrix multiplies.
These events are constructed independently; they are not the actual FFM loop or
transfer schedule. A `Storage` declaration is not treated as proof that the
physical copy exists or survives. Actual copy identity, concurrent capacity,
in-flight transfers and branch-wide must-properties remain unproved.

The audit reads the previous real FFM [mapping/action](../fusion_cut/README.md)
and [lifetime](../fusion_lifetime/README.md) records, verifies their source
hashes and Mapping-ID multisets, then constructs a conditional element witness
for each supported instance. It does not rerun FFM in this audit.

| Item | Count |
|---|---:|
| Supported Mapping instances | 27 |
| Distinct Mapping IDs among them | 18 |
| Outer-loop/other structures left unsupported | 7 |

At 96 B the two requested 32-byte intermediate examples are represented in
[audit.json](audit.json) with complete per-element event lists. The MainMemory
witness has a conditional minimum of 256 bit writes and 256 bit reads; the
recorded FFM Action counts are 256 and 256 bit respectively. The GlobalBuffer
witness requires no MainMemory traffic under its chosen assumptions, matching
the observed zero MainMemory `T1` actions. Across all 27 instances the chosen
conditional requirements are consistent with the aggregate FFM counts.

The same recorded actions may already account for the witness's traffic: **no
additional spill lower bound has been proved** and the numbers must not be
added again. Agreement with aggregate counts cannot prove an element-level
match or establish actual physical copy lifetimes. All witnesses retain
`safe_to_prune = false`.

Reproduce with:

```sh
python -m research.tracking_audit.audit_cross_phase_copy --output /tmp/cross-phase.json
python -m pytest -q --disable-warnings research/tracking_audit/test_cross_phase_copy_oracle.py
```
