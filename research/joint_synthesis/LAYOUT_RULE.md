# Restricted free-SRAM-layout dominance

In the present uniform SRAM-access model, change a producer's SRAM output to
the consumer's required SRAM layout, keeping its schedule and external input
unchanged. Its local six-coordinate demand is identical: output packing changes
neither arithmetic nor SRAM action cost, traffic, cycles or workspace. Identity
conversion then has peak N and zero actions. It componentwise dominates both
the original SRAM relayout (peak 2N) and spill/reload (peak N, extra traffic).
This proof uses nonnegative costs, exclusive ownership and one remaining consumer.
It is not a theorem for bank/layout-dependent access or shared-consumer cuts.

The implementation requires an **actually available retained producer** at the
target interface with no worse demand. Thus externally fixed producer properties
or an absent replacement cannot silently be relaxed. Local Pareto removal of the
same-schedule producer is safe only because its retained dominator supplies the
same full interface. `layout_pruning=False` retains the original full control;
the rule removes complete combinations before calling `compose()`.

For default-cost square/rectangular 2mm, complete alternatives fall respectively
from 1,682 to 1,426 and from 3,550 to 3,030, with the same 19/54 root vectors.
These are finite work counts, not a speedup or novelty claim. The spill-only
increase was 128/260; the rule also eliminates those pairs' direct SRAM relayout.

The independent execution test confirms the predicted third fixed-kernel plan:
Col→Col identity has `(u,v,P,E,c,q)=(1,1,104,3740,252,304)`. It dominates both
fixed Row→Col alternatives when the producer layout is free. Explicit
`PhysicalRequirements` retain both enforcers when that replacement is disallowed.

`test_layout_rule.py` validates every recorded replacement by scalar execution
under default, nondefault and zero energy/setup coefficients, as well as fixed
and empty property domains. Existing witness/differential/order tests remain the
search reference. This engineering rule explains the previous negative result;
it does not establish nonlocal graph co-optimization.
