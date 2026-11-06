# Bounded pre-enumeration Fusion experiment

This is a finite feasibility study, not a general mapper or a speedup claim over
FFM. Original FFM, `joint_synthesis/graph_dp.py`, and all earlier diagnostics stay
unchanged. The primary family is fixed **before** exhaustive/native validation:

- Three dense, square 256x256 Matmuls, 8-bit operands/partial sums/outputs.
  There is no sparse compute optimization. Numerical examples must not overflow.
- One global 64x96 PE array; active spatial lanes are reduction k by output j.
  Temporal m is innermost. Each of the six k/j choices is in {32,64}.
- Shared **n1** stripe s in {64,128,256}; j0 and k1 must divide s. The low native
  archived mapping uses n1=128, not m=128 (the old causal report had a rank typo).
  Exactly 192 full plans are in this declared family.
- T1 is a column stripe, T2 is a full 256x256 backing allocation. For each stripe,
  produce T1, consume it into T2, then free T1. Allocate T2 at the first consumer
  and retain it. T0 uses an N*k0 GB tile. Each weight uses a k*j GB tile and one
  register per active MAC lane. After all stripes, consume T2; T3 uses an N*j2
  output GB tile and is written to DRAM. All tensors have distinct ownership.
- Weight tiles are explicitly staged after both tile loops. This lowers W1/W2
  storage compared with some archived syntax; it does not claim identical full
  Mapping identity. No layout choice, conversion, streaming partial T1 delivery,
  recomputation, arbitrary DAG, open scope, or target-specific fallback exists.
- The final T3 physical interface and identity are the same for every full plan.
  Within a fixed s, T1 geometry, stage order, access order, alignment, ownership,
  and lifetime obligations are fixed. Only the internal k/j variables disappear.

## Resource effect before Tile evaluation

Let N=256 and one element be one byte. Before enumerating k/j, construct

```
a = N*s + N*k0 + k0*j0
b = N*s + N*N + k1*j1
c = N*N + N*j2 + k2*j2
P = max(a + (N*N if s<N else 0), b, c)
```

The producer's scoped external response is `Phi(x,y,z)=max(a+x,y,z)` for s<N;
for s=N it is `max(a,y,z)`. Here x is the retained outer T2 obligation, y/z are
other scope peaks. This is a closed, fixed-scope function, not a claim about
arbitrary continuations or allocation/alias programs. Instantiating x=N*N,
y=b,z=c gives P. A later producer stripe coexists with partially produced T2;
there is no later stripe at s=N. Thus k=j=64 gives 116 KiB at s=128 and 132 KiB
at s=256. These equations follow allocation scopes, not sampled native peaks.
The independent interpreter must reproduce them by allocating and freeing.

## Correlated cost and declared hardware model

Reuse the native NVDLA primitive coefficients, not its search or evaluation:
1 GHz; DRAM read/write share 38.4 bytes/ns; GB independent read/write ports have
512/128 bytes/ns. DRAM bit-action energy is 7.03 pJ; GB read/write bit-action
energies are .249/.293 pJ; MAC .084 pJ; register actions have zero energy/latency.
These are analytical model coefficients, not calibrated chip measurements.

For each phase, latency is the maximum of compute and aggregate port-service
bounds. Whole-chain latency is the sum of phase service times (including the
repeated stripes). This is **not** a cycle-accurate overlapping-DMA simulation.
Numerical data movement is legal independently of this ideal service estimate.
The exact frontier objectives are `(GB bytes, energy fJ, latency ns)` at fixed
array/bandwidth. Register capacity is fixed at one byte per lane, not an extra
optimization objective. We do not compare an unrestricted FFM RU frontier with
this restricted three-dimensional frontier.

All action formulas are built symbolically from loop multiplicities before
numeric tile evaluation. Intermediate partial sums skip the first zero read;
final T3 also requires one GB read for its DRAM drain. Fixed power-of-two domains
and N<=1024 keep all generated binary arithmetic counts exact and below 2^53;
subsequent energy and service-time calculations use integers and Fractions.

## Elimination and its limited sufficiency proof

Within one s, each phase contributes a correlated `(P_i,E_i,T_i)` vector. The
producer's P_i already includes its retained outer T2 obligation if s<N. The
composition is `(max(P_i), sum(E_i), sum(T_i))`. All three operations are monotone.
An alternative weakly dominated in all three dimensions can therefore be
replaced under every continuation **in this grammar at the same s**. This does
not assert that arbitrary physical interfaces with equal peaks are equivalent.
No local EDP pruning or independently minimized E/T/resource bound is used.
Equal vectors preserve one reconstructible plan, not all Mapping identities.

Stage-local symbolic factors are evaluated once per distinct structural input;
free-symbol analysis proves the third phase independent of s. Incremental
Pareto elimination avoids materializing every complete plan. Budget pushdown can
reject an entire s domain if `N*s+N*N+min(k1*j1)>capacity`, a simultaneous-live
allocation bound. It is valid only for this grammar; it cannot reject an FFM Job.

## Validation and decision gates

1. Independent event interpreter enumerates all 192 full-size plans. It imports
   no symbolic/effect/composition module and counts tile events and actual live
   allocations, rather than evaluating P or action polynomials. Its own quadratic
   frontier is compared with flat symbolic and eliminated full frontiers.
2. Scalar MAC execution of all plans in small N=4 and N=8 domains checks values
   with dense identity weights and a bounded nonzero input pattern, including
   each intermediate accumulator. Large-size event enumeration is **not** scalar
   arithmetic validation of 192*3*256^3 operations.
3. Verify local dominance against every finite continuation, reversed enumeration,
   exact-capacity boundaries, no-native-call construction/search, and oracle
   reconstruction of all returned witnesses.
4. A separate adapter re-evaluates deterministic representatives and returned
   witnesses with native FFM fixed-map evaluation. It is outside search and never
   calls the Mapping generator. Compare actions/phase service costs/GB peaks.
   A mismatch invalidates a native-equivalence claim; do not fit coefficients.
5. Time symbolic construction + flat/eliminated/budget search, report candidate
   materializations and factor evaluations separately. Native validation and
   exhaustive verification costs are separately reported. Include an equally
   cached flat baseline: factor reuse alone is not decision elimination.

**Continue locally** only if symbolic construction is pre-enumeration, exhaustive
frontiers match and internal decisions actually disappear. **Cautious** if this
works only because the fixed grammar makes costs separable, or native model calls
have not been avoided in the original full search. **Stop generalization** if
sufficient states approach exhaustive tuples or model preparation costs dominate.
No result here by itself licenses a new general Graph DP, a native 3mm end-to-end
speedup claim, or cross-architecture full-space equivalence.

### Native adapter boundary

For a fused s<N mapping, the native W1 `Storage` node must remain at the shared
scope: placing it below the inner loops changes FFM's inferred T1 Compatibility
and the native Join rejects the mapping. The adapter uses the archived scope
convention and validates the **effective** k1*j1 Reservation, actions, and costs.
The event interpreter stages that same effective weight tile explicitly. This
is a numeric/lifetime cross-check, not a proof that every frontend node has an
identical literal allocation trace. No symbolic resource or cost formula was
changed to accommodate this adapter issue.
