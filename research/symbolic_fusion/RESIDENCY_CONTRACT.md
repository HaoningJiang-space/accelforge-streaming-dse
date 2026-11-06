# B: two real T2 backing contexts, two global array shapes

This bounded study follows the negative grounded-DP attribution result in A.
Freeze this grammar before native cross-checks; do not fit costs to observations.
The goal is to compare shared conditional summaries with equally cached ordinary
DP, not to produce a general mapper. A negative result is a stopping result.

## Common decisions and hardware

N=256, 8-bit values, three Matmuls, the same n1 stripes {64,128,256} and
weight-stationary loop order as the original study. Each stage reduction Tile
k and output Tile j both remain in {32,64}; no Tile choice is added. One global array is selected
from (reuse_input,reuse_output) fanouts {(32,192),(64,96)}, each 6,144 PEs.
**j<=reuse_input and k<=reuse_output** at every stage. j0 and k1 divide the shared
stripe. These legality constraints participate before stage expansion/combining,
not after building one fixed mapping list. Configured GB budgets are 128/132 KiB;
bandwidth, clock, Register and primitive coefficients stay unchanged. Additional
one-byte feasibility queries may check all attained peaks. No area-optimal-chip
claim is supported by this model.

## GB-backed context

Exactly the original grammar: T2 is allocated once at the first consumer and
retained across later stripes and the final Matmul. The producer may coexist
with future T2. T1 is produced and consumed one stripe at a time. Existing
resource effect and action formulas apply.

## DRAM-backed context (not x=0)

T2's logical backing is DRAM, owned for the whole program. In Matmul1, after
choosing the current reduction block and output block, allocate an M*j1 GB
partial-output tile. Load its previous DRAM version unless this is the first
reduction block, update it using the resident T1 stripe and the staged weight,
write it back to DRAM, and free the GB copy. This happens on every reduction
block, including at stripe boundaries. Versions must be read before overwrite.
There is no full T2 GB allocation in later producer stripes.

In Matmul2, the n3 output loop encloses the n2 reduction loop. Stage M*k2 T2
input values from DRAM for each output tile/reduction tile; stage W2; update
resident M*j2 T3; free the input tile. Finally drain T3 to DRAM. Thus T2 reads
are repeated across output tiles; a free bypass or zero-cost relabel is illegal.

Derived GB phase peaks (bytes) are:

```
P0 = N*s + N*k0 + k0*j0
P1 = N*s + N*j1 + k1*j1
P2 = N*k2 + N*j2 + k2*j2
```

Let V=N^3. Relative to GB-backed execution, Matmul1 gains DRAM reads
N^2*(N/k1-1), DRAM writes V/k1, GB reads V/k1 (one drain per reduction block), and GB writes
N^2*(N/k1-1) (fills). Matmul2 gains DRAM reads V/j2 and GB writes V/j2.
All other action counts stay the same. Weight traffic and dense MACs remain.
Each phase keeps the same aggregate port-service model; there is no new overlap
or banking penalty. A separate event interpreter executes actual partial-copy
lifetimes and optionally scalar values. A native adapter emits the backing and
per-tile storage nodes, then checks effective reservations, actions, and costs.

## Algorithms and fair attribution

All paths build the same pair of symbolic cost/resource branches once and share
the same pre-enumeration structural factor cache across shapes and contexts.
Each can precompile a frontier once for every legal (shape,context) and reuse it
for every capacity query, including free choice of either backing context.

1. Cached flat enumerates only complete decision tuples compatible with at least
   one single global array, carrying that array's membership throughout.
2. Grounded DP solves each of the four (shape,backing) environments using the
   shared factor cache and ordinary (Peak,E,T) pruning.
3. Shared conditional DP keeps one Tile witness with a vector of outcomes over
   its legal environments. It composes only matching global environments and
   compares states pointwise across all environments of the discarded state.
   All branches have real execution semantics. This is a finite conditional
   vector, **not** a proof of arbitrary-continuation resource-effect equivalence.

Report both decision-object counts and per-environment scalar work. A shared
object with four outcomes is not four free evaluations. Count root candidates
before Pareto, all intermediate combines, factor evaluations, retained vectors,
peak intermediate states, construction+compile+all-query time and memory.

Find witnessed prefix decisions that are dominated in one backing context but
not the other. Re-test every claimed pruning decision against all remaining
finite continuations and the independent complete frontier. A crossing witness
alone does not prove that a shared algorithm is better: independent grounded
DP with the same cache is the required baseline.

**Gate:** if actual contexts change choices but shared conditional DP offers no
advantage over cached per-environment grounded DP, preserve the data and stop
claiming Resource Effect as a demonstrated core algorithm. Do not add more
contexts, Graph machinery, or special pruning rules to manufacture a win.

Under these unchanged Tile choices the 32x192 legal domain is a subset of the
64x96 domain. Both use the same primitive model for an identical mapping, so this
study cannot prove a best-shape reversal. We will not add k=128 to manufacture
one. Shapes still constrain expansion and one global shape is maintained.

The per-block GB drain coefficient is V/k1, not N^2: every reduction block
writes its partial output to DRAM. Preliminary adapter checks exposed and
corrected that action-accounting omission before this experiment's enumeration;
no primitive energy/service coefficient was changed.
