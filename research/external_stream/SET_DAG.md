# End-to-end SET DAG comparison

```powershell
./research/external_stream/build_set_windows.ps1 -DagDriver
& ./libraries/stream/.venv/Scripts/python.exe -X utf8 -m research.external_stream.set_dag --capacities 524288 --rounds 64 --output research/local_set_dag.json
```

The driver links the pinned official SET sources. Both searches call its
`SchNode` allocator and cost model for complete RA-trees. The reference uses
the native unconstrained `SA_search` starting from per-layer execution. The
guided search spends part of its budget pricing ordered DAG partitions with
temporal or spatial children, then runs the same native `SA_search` starting
from its best seed. All legal topological orders and cut subsets enter the
seed ranking. Subsequent annealing can produce deeper RA-trees in both arms.
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

At [195 candidate evaluations per method](results/set_dag_equal_64.json),
diamond improves in all five paired runs, with 40.0–61.5% lower EDP. Both
methods choose the same array geometry for those runs. GLU improves in one
run and ties in four, residual ties in all five, and asymmetric improves in
one and ties in four. The raw records include search wall time and array
choices. Candidate evaluations define the search budget in this experiment.
