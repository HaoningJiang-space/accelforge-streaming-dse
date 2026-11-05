# Global hardware binding gate

This extends the existing barrier-2mm proof model. It does not change its
Mapping grammar, add streaming, or claim calibrated chip area/performance.
The graph DP still generates a complete resource-demand frontier with no
architecture points. Hardware binding is a separate exact step on that frontier.

## Hardware, prices and budget

One global architecture is `a=(Px,Py,C,B)`: integer array extents, SRAM bytes,
and DRAM bytes per cycle. Each axis has a declared positive integer grid
`lo, lo+step, ... <=hi`. There is no 64-point or equal-PE-count restriction.
All operators and conversions use this same architecture.

Use the explicitly **normalized** resource cost

\[
H(a)=w_P P_xP_y+w_C C+w_B B,\qquad w_P,w_C,w_B>0.
\]

All coefficients and budgets are integers. These are declared resource-price
units, not square millimetres, power or a calibrated NVDLA area model. A resource
budget ceiling restricts feasible hardware. Bandwidth remains a cost/performance
choice; no artificial minimum-bandwidth feasibility rule is introduced.

For a complete demand `d=(u,v,P,E,c,q)`, feasibility is
`Px>=u, Py>=v, C>=P`, energy is E and latency is `c+q/B`. No implicit retargeting
or extra compute speed is obtained from unused PEs. Larger SRAM does not alter
this already fixed schedule's traffic. Different tilings/bindings remain separate
plans in the demand frontier.

The binding rule is invalid if shape/capacity also changes clock, leakage,
interconnect, access energy or other cost coefficients. Those dependencies need
a new model/contract; they are not silently treated as invariant.

## Demand-driven hardware construction

For each demand, round u,v,P **up** to the first allowed point of the respective
axis. If any requirement exceeds its axis, that demand is infeasible in this
envelope. Otherwise let these minima be `(x_d,y_d,C_d)`.

For each allowed B under the ceiling, construct one candidate
`(x_d,y_d,C_d,B,d)`. The positive price bounds B directly by

\[
B\le\left\lfloor{H_{max}-w_Px_dy_d-w_CC_d\over w_B}\right\rfloor.
\]

Round this upper bound down to the bandwidth grid. No PE-shape/SRAM Cartesian
product is materialized, and no architecture invokes a complete Mapping search.

Proof of coverage: for any feasible `(a,d)`, its grid-rounded minima fit inside
a. Replacing a's PE/SRAM by those minima leaves E and T(B) unchanged and cannot
increase H. Therefore every numerical `(H,E,T)` Pareto vector has a representative
among the constructed candidates. Larger unused hardware and tied source
identities need not all be returned. Multiple B values remain necessary because
they trade hardware cost against latency.

This relies on the current grammar's demand sufficiency and fixed costs. It is
not a general co-design theorem for arbitrary accelerator models.

## One compiled hardware-cost frontier, many budget queries

Retain the exact `(H,E,T)` frontier with reconstruction witnesses. Filtering it
at any budget `h<=H_max`, then taking its E/T frontier, preserves every E/T vector
feasible under h. A discarded vector's dominator has **no greater H**, so it
cannot disappear merely because the budget decreased.

This argument applies to complete physical plans. It is unrelated to filtering
FFM's capacity-dependent fallback/Pareto membership from a maximum-capacity run.
Queries above the compiled ceiling are unsupported and must raise rather than
return a partial result. Empty results establish infeasibility only for the
supplied complete demand set, envelope and model.

## Independent validation

The hardware Oracle must enumerate all grid hardware points and all unique
observations from unpruned scalar execution of the complete grammar. It must not
use grid-rounding/minimal-hardware binding, production demand pruning, production
hardware pricing functions or the production frontier routine. Reuse of immutable
axis/price data and the independent physical interpreter is allowed.

Compare the complete `(H,E,T)` vector set, all budget-query E/T frontiers and
minimum EDP, including infeasible budgets and rounding boundaries. Every selected
source must round-trip its plan and replay through the physical interpreter on
the **same global hardware**, with exact energy/latency/peak checks. Count actual
hardware candidates constructed versus full-grid points and feasible plan–hardware
bindings. These are same-model proof/work counts, not FFM speedup measurements.

Current real FFM shape-switch cases and calibrated hardware costs remain later
model-alignment gates. A toy normalized-budget switch is not their replacement.
