# Frozen first prediction protocol

Protocol v1, 2026-11-08. Written after a smoke-test curve for 2mm(M=4, KN=4)
and before inspecting the held-out curves below. No coefficients are fitted.
The smoke-test case is calibration, not held-out evidence.

Question: can full-tensor boundary information plus isolated-operator curves
predict a graph's buffer/traffic frontier without executing graph-level Join?
These are deliberately explicit hypotheses, **not asserted bounds/theorems**.

## Fixed semantics

Modern two-level Snowcat-style YAML, one serial compute unit, no spatial array,
no recomputation. Cold external inputs, final outputs written to MainMemory.
MainMemory read/write energy is 1 per bit; all other energy and all latency is
zero. Thus energy / 8 is backing-store traffic in bytes. INT8 workloads, one
instance. Both capacity and traffic are Pareto objectives. A finite buffer
envelope holds the sum of all full tensor footprints; this is explicit, not an
unbounded-capacity claim. Search all default native FFM templates in that
envelope, with GlobalBuffer kept variable through generation and Join.

Reference is the attained envelope in this declared FFM grammar and source
operator order, not a proof over all programs/schedules. Distinct topological
orders, recomputation and alternative operator semantics are outside v1.
Every retained point is reconstructed, replayed at its required capacity,
and checked against per-tensor backing-store action counts. Small smoke cases
also check fresh fixed-capacity searches immediately around breakpoints.

Materialized control: require MainMemory to keep every tensor and set zero
fused loops. Zero fused loops alone does not imply DRAM materialization.

## Predictions fixed before global curves

For operator i, s_i is the smallest full tensor footprint among its inputs and
outputs (including weights). b_i is the full footprint of tensors already
produced/fetched, needed by a later operation, and **not an input of i**, just
before i. External tensors enter at first use. Weights with only one consumer
never contribute to b_i. This is a prescribed full-tensor accounting rule,
not an assumption that tiling must retain full tensors.

- P0, operator-size only: plateau capacity = max_i s_i; candidate breakpoint
  set = distinct s_i. No graph mapper or isolated mapper is used.
- P1, structural addition: plateau = max_i(b_i+s_i); candidate set = b_i+s_i.
- P2, local-frontier addition: independently generate each isolated operator's
  capacity/traffic Pareto frontier. Let c_ij be its capacities and c_i* the
  first capacity attaining its minimum traffic. Predict plateau =
  max_i(b_i+c_i*); candidate breakpoints = union_i,j(b_i+c_ij).
  No graph-wide best mapping, compatibility class or graph frontier is used.

P2's local search time is part of prediction cost. The hypothesis intentionally
does not solve cross-operator tile compatibility; failures are evidence about
that omission, not permission to insert graph winners into the prediction.
Each case writes a prediction checkpoint and hash before graph search starts.

## Evaluation fixed in advance

Plateau = first capacity attaining the minimum traffic in the completed native
reference. Report signed and absolute relative capacity errors. Breakpoints
exclude the first feasible point; P0/P1/P2 candidate sets are assessed against
traffic decreases of at least 5% from the preceding attained plateau. Match
within 5% relative capacity, one-to-one; report precision, recall and matched
location errors. Do not discard false predicted breakpoints above the true
plateau. This prevents dense candidate lists from looking automatically good.
Also report all native frontier points, materialized-control frontier and the
first sampled capacity with strictly lower graph traffic. No curve regression
or fitted threshold is performed. We do not promise a complete Q(C) predictor
from a list of capacity candidates alone.

## Registered cases and limits

- Calibration: 2mm, M=4, KN=4.
- Held-out shapes/topologies: 2mm(2,8), 2mm(8,4), 3mm(4,4),
  GLU(M=2,G=4,C=4), attention proxy(tokens=4,heads=1,head_dim=4).
- Existing YAML coverage: GPT block(tokens=2, hidden=4, heads=1, head_dim=4,
  FFN=16), MobileNet-28 with P/Q ranks reduced to 4, N channels to 4 and T
  channels to 8. These are explicitly scaled workload programs, not full-size
  models or a full softmax/activation implementation.
- Also attempt the original MobileNet-28(batch=1) and original GPT-6.7B
  geometry at 2 tokens. A timeout/error remains a reported failure; it is not
  silently replaced by a scaled result.

Windows single-process workers, parent-enforced wall-clock and sampled working
set limits, 240 s and 2 GiB per case by default. A case exceeding either limit
is incomplete; its partial front is not a reference optimum. Original-size
cases may use 120 s to bound this initial feasibility attempt, recorded by
the runner. All cases are serial across workers. Failed predictions do not
automatically justify switching to multi-core or multi-level resource graphs.
