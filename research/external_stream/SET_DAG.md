# End-to-end SET DAG comparison

```powershell
./research/external_stream/build_set_windows.ps1 -DagDriver
& ./libraries/stream/.venv/Scripts/python.exe -X utf8 -m research.external_stream.set_dag --capacities 524288 --rounds 64 --output research/local_set_dag.json
```

The driver links the pinned official SET sources. Both searches call its
`SchNode` allocator and cost model for complete RA-trees. Every method prices
the per-layer anchor and every zero-cut temporal and spatial anchor. One
reference spends the remaining budget on native `SA_search`. A second prices
uniformly sampled DAG partitions before native search. The guided method
ranks the same pool of ordered DAG partitions before native search. All legal
topological orders and cut subsets enter the common pool. Subsequent
annealing can produce deeper RA-trees in all methods.
The seed score uses estimated edge traffic, live SRAM, and array geometry.
Only native SET EDP selects incumbents. Every seed and annealing candidate
counts toward the same per-shape budget, including infeasible candidates.
The fresh winner replay is charged equally outside the search.

The common platform for both methods has six cores in a 3×2 mesh, 6,144 MACs,
the same global-buffer ceiling, and per-core shapes 16×64, 32×32 and 64×16.
Local Eyeriss storage and the native bus, NoC and DRAM settings are fixed.
The 512 KiB limit applies to aggregate global buffers and includes rounding
down to six identical per-core banks. This platform differs from the
single-array AccelForge projection. The per-layer seed does not fit on
diamond at 128 or 132 KiB under this six-core SET model.

The adapter maps GEMMs to 1×1 convolutions and binary operations to SET's
two-input Eltwise cost model. It checks the MAC count and leaf dependency
order, reprices each winner from its full RA-tree, and reconciles DRAM accesses,
energy components and whole-graph EDP. SET supplies native aggregate timing,
including NoC and DRAM bounds. This experiment prices both methods within
SET's model and does not establish per-port event equivalence to AccelForge.

The [initial diagnostic](results/set_dag_equal_64.json) seeded the reference
only with the per-layer tree. SET's native parent-creation mutation excludes
grouping all siblings, so a search started with multiple root children
cannot reach a zero-cut tree. The guided arm could seed that component. The
reported diagnostic gains therefore fail the common mapping-space gate.

With common anchors and 195 native evaluations per method, the guided method
ties or loses to the better control on every trial. The
[512 KiB report](results/set_dag_common_64_512k.json) covers all four DAGs;
the [256 KiB report](results/set_dag_common_64_256k.json) covers GLU and diamond.
The reports retain wall times and the independently replayed winners.

A [root-basin portfolio](results/set_dag_portfolio_64_512k.json) holds the
layerwise, one-segment spatial and one-segment temporal starts separately.
It spends the same total budget on actual shape–basin states. Against the
strongest included control per seed at 512 KiB, it wins four, ties twelve
and loses four. At [256 KiB](results/set_dag_portfolio_64_256k.json) it wins
two and ties eight. Different array selections explain part of the asymmetric
variation, but its median paired result is unfavorable.

The [topology experiment](results/set_dag_topology_64_512k.json) adds mesh
orientation and DRAM attachment locations. All candidates keep six cores,
6,144 MACs, seven NoC links, four DRAM attachments and the same buffer and
bandwidth budgets. The tie-aware architecture-first control spends its
remaining budget on the shapes tied on per-layer cost. Joint budget
allocation ties the best control in sixteen pairs and loses in four.

The [nested experiment](results/set_dag_nested_64_512k.json) offers each
seed policy the same nested templates. The driver exports SET's direct
predecessors and DRAM writeback flags. An independent tree walk derives the
spills from the closest common ancestor and checks the complete winner trees.
Guided search ties in thirteen cases and loses in seven. These findings apply
to the stated SET resource model and evaluation budget.
