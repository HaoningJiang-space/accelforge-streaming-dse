"""Reuse native allocation subproblems inside STREAM's full DAG evaluation."""

from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from stream import api
from stream.stages.context import StageContext
from stream.stages.generation.placement_generation import PlacementGenerationStage
from stream.stages.stage import Stage
from stream.workload.node import ComputationNode, InEdge, OutEdge


def group_key(workload, mapping_path):
    # The general IR omits affine maps, tensor views and the input edge's parameter flag.
    nodes = []
    for node in workload.nodes:
        tensors = (*getattr(node, "inputs", ()), *getattr(node, "outputs", ()))
        views = tuple((t.name, str(t.operand_type), str(t.subview)) for t in tensors)
        if isinstance(node, ComputationNode):
            fields = tuple(str(m) for m in node.operand_mapping), node.fused_kernel, node.window_extents
        elif isinstance(node, (InEdge, OutEdge)):
            fields = getattr(node, "parameter", None), node.declared
        else:
            raise TypeError(f"unsupported group node {type(node).__name__}")
        nodes.append((type(node), node.name, views, fields))
    return mapping_path.read_bytes(), tuple(nodes), json.dumps(workload.get_ir())


@contextmanager
def native_memo():
    """Install a benchmark-only cache for one fixed SolveOptions contract."""
    cache = {}
    stats = dict(hits=0, misses=0, entries=0, reuse_keys={})

    class ReuseGroup(Stage):
        reads = ("workload", "mapping", "accelerator", "output_path", "held", "artifacts")
        result_writes = ("allocation", "memory_accesses")

        def run(self):
            ctx = self.ctx
            child, *rest = self.list_of_callables
            if (ctx.get("artifacts") or ctx.get("held") or ctx.get("mapping").edge_placements
                    or len(ctx.get("accelerator").offchip_memories) != 1):
                raise ValueError("allocation memo requires a single DRAM and no external SRAM placements")
            group_path = Path(ctx.get("output_path"))
            spec_path = group_path.parent.parent
            hardware = tuple((spec_path / name).read_bytes() for name in ("nvdla_geometry.yaml", "core.yaml"))
            options = tuple(ctx.data[name] for name in ("backend", "time_limit_s", "route_alternatives",
                            "temporal_mapping_type", "loma_lpf_limit", "tile_search", "nb_cols_to_use"))
            families = ctx.data["families"].specs()
            signature = (hardware, options, families, *group_key(ctx.get("workload"), group_path / "mapping.yaml"))
            key = sha256(repr(signature).encode()).hexdigest()
            if key in cache:
                stats["hits"] += 1
                stats["reuse_keys"][key]["hits"] += 1
                # The vendor fusion driver reads only these two fields from a group's result.
                yield StageContext(data={**ctx.data, **cache[key]})
                return
            stats["misses"] += 1
            result, = child(rest, ctx).run()
            allocation = result.data["allocation"]
            solve = allocation.solution.solve_stats
            if solve.status == "OPTIMAL" and solve.mip_gap == 0 and not allocation.mapping.edge_placements:
                cache[key] = {name: result.data[name] for name in self.result_writes}
                stats["reuse_keys"][key] = dict(hits=0, solve_time_s=solve.solve_time_s, mip_gap=solve.mip_gap)
            yield result

    stages = api._ALLOCATION_STAGES
    if stages[0] is not PlacementGenerationStage:
        raise ValueError("unexpected STREAM allocation pipeline")
    with patch.object(api, "_ALLOCATION_STAGES", [ReuseGroup, *stages]):
        yield stats
    stats["entries"] = len(cache)
