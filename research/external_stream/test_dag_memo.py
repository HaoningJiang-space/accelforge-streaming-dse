from dataclasses import replace
from types import SimpleNamespace

import pytest
from xdsl.dialects.builtin import MemRefType
from xdsl.dialects.memref import AllocOp, SubviewOp

from stream import api
from stream.stages.context import StageContext
from stream.workload.normalization import expand_normalizations
from stream.workload.workload import Workload

from research.external_stream.dag import build, verify_graph
from research.external_stream.dag_host import evaluate, graph_order
from research.external_stream.dag_host_order import order_choices
from research.external_stream.dag_memo import group_key, native_memo
from research.runtime.dag_cases import asymmetric, glu


@pytest.mark.parametrize("held,placements,memories", [
    ({"gb": {"skip": 64}}, {}, ["dram"]),
    ({}, {"skip": "gb"}, ["dram"]),
    ({}, {}, ["dram0", "dram1"]),
])
def test_memo_rejects_cross_group_state(held, placements, memories):
    ctx = StageContext.from_kwargs(workload=object(), held=held, artifacts=False,
                                   mapping=SimpleNamespace(edge_placements=placements),
                                   accelerator=SimpleNamespace(offchip_memories=memories), output_path="unused")
    with native_memo() as stats:
        stage = api._ALLOCATION_STAGES[0](api._ALLOCATION_STAGES[1:], ctx)
        with pytest.raises(ValueError, match="single DRAM"):
            tuple(stage.run())
    assert stats["hits"] == stats["entries"] == 0


def test_tensor_view_changes_key(tmp_path):
    workload = build(glu())
    edge = workload.get_node_by_name("X")
    original = edge.outputs[0]
    rows, width = original.shape
    source_type = MemRefType(original.operand_type, (rows+1, width))
    source = AllocOp([], [], source_type)
    views = [replace(original, subview=SubviewOp.from_static_parameters(
        source, source_type, [offset, 0], [rows, width], [1, 1])) for offset in (0, 1)]

    def nodes(view):
        for node in workload.nodes:
            if node == edge:
                yield replace(node, outputs=(view,))
            elif original in getattr(node, "inputs", ()):
                yield replace(node, inputs=tuple(view if t == original else t for t in node.inputs))
            else:
                yield node

    mapping_path = tmp_path / "mapping.yaml"
    mapping_path.write_text("same generated mapping", encoding="utf-8")
    first, second = (group_key(Workload(list(nodes(view))), mapping_path) for view in views)
    assert first != second


def test_full_dag_reuse_respects_hardware_and_solver_contract():
    workload = build(glu())
    shape = (32, 192, 131072)
    uncached = evaluate(workload, shape, (), 10)
    with native_memo() as stats:
        evaluate(workload, shape, None, 10)
        cached = evaluate(workload, shape, (), 10)
        evaluate(workload, shape, (), 9)
        evaluate(workload, (48, 128, 131072), (), 10)
    assert uncached["groups"] == cached["groups"]
    assert stats["hits"] == 1 and stats["misses"] == 3


def test_equal_cost_allocations_with_different_placements_are_never_cached(tmp_path):
    workload = build(glu())
    group_path = tmp_path / "out" / "group_0"
    group_path.mkdir(parents=True)
    for file in (tmp_path / "core.yaml", tmp_path / "nvdla_geometry.yaml", group_path / "mapping.yaml"):
        file.write_text("stable experiment input", encoding="utf-8")
    ctx = StageContext.from_kwargs(
        workload=workload, mapping=SimpleNamespace(edge_placements={}), held={}, artifacts=False,
        accelerator=SimpleNamespace(offchip_memories=["dram"]), output_path=str(group_path),
        backend="ortools_gscip", time_limit_s=10, route_alternatives=1, temporal_mapping_type="uneven",
        loma_lpf_limit=6, tile_search=True, nb_cols_to_use=4, families=SimpleNamespace(specs=lambda: ()),
    )
    outputs = iter(("gb", "dram"))

    def allocate(_remaining, _context):
        solve_stats = SimpleNamespace(status="OPTIMAL", mip_gap=0)
        result = SimpleNamespace(estimated_cycles=20, solution=SimpleNamespace(solve_stats=solve_stats),
                                 mapping=SimpleNamespace(edge_placements={"skip": next(outputs)}))
        return SimpleNamespace(run=lambda: iter((StageContext.from_kwargs(allocation=result),)))

    with native_memo() as stats:
        stage = api._ALLOCATION_STAGES[0]([allocate], ctx)
        assert next(stage.run()).get("allocation").mapping.edge_placements["skip"] == "gb"
        assert next(stage.run()).get("allocation").mapping.edge_placements["skip"] == "dram"
    assert stats["hits"] == stats["entries"] == 0


def test_native_cuts_use_the_canonical_fork_order():
    graph = asymmetric()
    orders = order_choices(graph)
    assert len(orders) == 2
    canonical = set()
    for order, _ in orders:
        workload = expand_normalizations(build(graph, order))
        verify_graph(workload, graph)
        canonical.add(graph_order(workload))
    assert canonical == {("Stem", "Narrow", "Right", "Wide", "Left", "Merge", "Y")}
