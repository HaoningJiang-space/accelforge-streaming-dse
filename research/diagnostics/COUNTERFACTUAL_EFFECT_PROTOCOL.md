# Bounded G1 counterfactuals and resource effects

No optimizer, online pruning, new Enforcer or native FFM changes. Use the same
native 3mm, six targets and Event+Cache/RU contract as G1/G2.

## Counterfactual classification

Observe local compressed inputs, visited Join outputs, and **terminal outputs
after capacity checks but before group Pareto**. Relate them to G1's 54 Jobs with
local inputs and no returned frontier descendants using exact template and Tile
provenance. Classifications overlap; do not sum them into graph-specific savings.

- A local sufficient replacement requires the same concrete local group and
  equality of every non-cost/non-source transition column, plus non-worse E/T.
  This is deliberately conservative and numerical; absence of a witness is not
  proof that no universal local dominance theorem exists.
- For each visited feasible complete row, find equal/strictly dominating returned
  numerical points at each actual target. Equal coordinates establish a possible
  source-fold explanation, not that every alternative source was retained.
- Fix the final consumer's compressed candidate and recompute the Pareto set of
  the **recorded feasible complete rows**. A globally unused Job on this restricted
  frontier is a finite consumer-choice counterfactual. It is not a replay of all
  legal completions or FFM's fallback history under a changed search space.
- If a Job never reaches the recorded terminal capacity-feasible pool, leave its
  cause unresolved. Prefix Pareto, compatibility/lookahead, policy membership,
  and source folding may have prevented its observation.

Do not label all 54 Jobs context-dependent or report their time as proven
Graph-Specific Waste. Keep per-Job classifications, partial coverage and concrete
source/cost witnesses. Validate unchanged full reference fronts.

## Restricted resource-effect contract

After native Join preparation, support exact finite GB/Register resource columns,
nonnegative addition and closure at loop -1, with **no** allocation/free/alias
adjustment. Extract the operation list; the effect evaluator itself cannot call
native Join, preparation, Pareto or resource helpers. Unknown programs are counted.

Compile max-affine integer expressions in the prepared consumer's resource
coordinates. Addition uses distributivity and closure uses max. Within this
fixed program/schema, structural induction proves equality for every admissible
consumer resource vector (nonnegative, nested prefix reservations, exact range).
This is not a sufficient interface for arbitrary continuations or all FFM Fusion.

Validate the effect against actual native outputs and an independent concrete
integer program interpreter. Use the archived six fixed mappings to check the
52+64=116 KiB mechanism and both capacity queries. A frontier of that six-plan
library is not an exhaustive physical Mapping grammar or a new Graph DP result.

## Compression and costs

Count separately: prepared producer-row occurrences, distinct resource functions,
states after retaining complete fixed-context non-resource fields and correlated
E/T, and a conservative conditional Pareto front within equal such requirements.
Resource-only equality does not imply Mapping substitutability. Architecture
capacity queries may reuse an effect of an already grounded Mapping; equal
effects across PE shapes alone do not authorize Mapping/cost migration.

All summaries are constructed **after generation has happened**. Publish summary
construction/analysis time as diagnostic overhead, not an end-to-end speedup or
avoided generation. No requirement to repeat an expensive trace merely to obtain
timing medians: this round tests semantics and evidence coverage, not performance.
