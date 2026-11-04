"""Whole single-operator region compilation, retaining all FFM templates.

This is terminal Energy/Latency/GlobalBuffer Pareto composition. It is not a
Fusion Join: no partial boundary or lifetime state is dropped inside a graph.
"""
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import time
from unittest.mock import patch

import numpy as np

from research.tracking_audit import benchmark_parametric_template as b
from research.tracking_audit.parametric_template import Box, compact_boxes


def prepare_all(size, point):
    """Generate every template once; capture every model before Tile enumeration."""
    if type(size) is not int or size <= 0 or size & (size-1):
        raise ValueError('requires a power-of-two MatMul size')
    spec = b.build(b.common.Case('matmuls','nvdla',(1,size,size)),point[:2],point[2],b.common.RU)
    evaluated = spec._spec_eval_expressions(eval_arch=False,eval_non_arch=True)
    jobs = b.pmapper.get_jobs(evaluated,b.common.RU,evaluated.workload.einsum_names,True)
    b.pmapper._fill_jobs_with_memories_to_track(jobs,evaluated,b.common.RU,False)
    candidates = [(json.dumps(b.mapping_structure(j.mapping),sort_keys=True),j)
                  for groups in jobs.values() for group in groups.values() for j in group]
    candidates.sort(key=lambda pair:pair[0])
    if not candidates or len({key for key,_ in candidates}) != len(candidates):
        raise ValueError('expected nonempty, unique canonical template identities')
    programs = []
    original = b.tiles.run_model

    class StopPreparation(Exception):
        pass

    for key,job in candidates:
        captured = {}
        def model(j):
            result = original(j)
            captured['model'] = result[1]
            return result
        def stop(**kwargs):
            captured.update(kwargs)
            raise StopPreparation
        with patch.object(b.tiles,'run_model',model), patch.object(b.tiles,'get_tile_shape_choices_for_targets',stop):
            try:
                b.tiles._make_tile_shapes(job)
            except StopPreparation:
                pass
        kwargs = {k:captured[k] for k in ('symbols','what_tiles_symbol','job','keep_symbols','max_loop_check_groups')}
        programs.append(b.Program(kwargs,captured['objectives'],captured['model'],key,point,spec))
    return programs


def intersection(a,b):
    ranges = tuple((max(x[0],y[0]),min(x[1],y[1])) for x,y in zip(a.ranges,b.ranges))
    return None if any(lo>hi for lo,hi in ranges) else Box(ranges)


def subtract(box,cut):
    """Disjoint boxes representing box minus cut, including uncovered holes."""
    overlap = intersection(box,cut)
    if overlap is None:
        return [box]
    pieces, core = [],box
    for axis,(lo,hi) in enumerate(overlap.ranges):
        a,z = core.ranges[axis]
        if a < lo:
            pieces.append(core.cut(axis,a,lo-1))
        if hi < z:
            pieces.append(core.cut(axis,hi+1,z))
        core = core.cut(axis,lo,hi)
    return pieces


def byte_boxes(state):
    for box in state.targets:
        lo,hi = box.ranges[2]
        lo,hi = (lo+7)//8,hi//8
        if lo <= hi:
            yield Box((*box.ranges[:2],(lo,hi)))


def overlay(cells, template, max_boxes):
    """Refine existing cells by one complete template's execution partition.

    None explicitly represents infeasibility in that template. Missing a region
    must never discard an architecture that another template can serve.
    """
    regions = [(i,box) for i,state in enumerate(template.engine.leaves) for box in byte_boxes(state)]
    groups = defaultdict(list)
    for key,boxes in cells.items():
        pending = list(boxes)
        for index,region in regions:
            remainder = []
            for box in pending:
                match = intersection(box,region)
                if match is None:
                    remainder.append(box)
                else:
                    groups[key+(index,)].append(match)
                    remainder.extend(subtract(box,region))
            pending = remainder
            if not pending:
                break
        groups[key+(None,)].extend(pending)
        if sum(map(len,groups.values())) > max_boxes:
            raise MemoryError('joint region budget exceeded; no candidates discarded')
    return {key:compact_boxes(boxes) for key,boxes in groups.items() if boxes}


def frontier_ids(costs, ids):
    if not len(ids):
        return np.empty(0,dtype=np.int64)
    # Stable global provenance on equal vectors. Never use numeric equality to
    # substitute a Mapping that is absent from this architecture's selected set.
    ids = np.unique(ids)
    values = costs[ids]
    mask = b.tiles.makepareto_numpy(values,['min']*3)
    ids = ids[mask]
    _,first = np.unique(costs[ids],axis=0,return_index=True)
    return ids[first]


@dataclass
class TerminalRegion:
    boxes: tuple[Box,...]
    ids: np.ndarray


class CompiledOperator:
    def __init__(self,programs,family,max_boxes=50000):
        self.programs = sorted(programs,key=lambda p:p.template_key)
        if not self.programs or len({p.template_key for p in programs}) != len(programs):
            raise ValueError('all template identities must be nonempty and unique')
        self.family = family
        self.templates = []
        self.origins = []
        offsets,parts,template_stats = [],[],[]
        for i,program in enumerate(self.programs):
            t0 = time.perf_counter()
            template = b.CompiledTemplate(program,family)
            offsets.append(len(self.origins))
            self.templates.append(template)
            self.origins.extend((i,j) for j in range(len(template.choices)))
            parts.append(template.costs)
            template_stats.append(dict(template_id=hashlib.sha256(program.template_key.encode()).hexdigest(),
                compile_s=time.perf_counter()-t0,cost_rows=template.cost_rows,**template.engine.stats))
        self.costs = np.concatenate(parts)
        # Reduce each template's terminal frontier before inter-template union.
        local_ids = []
        for offset,template in zip(offsets,self.templates):
            local_ids.append([frontier_ids(self.costs,[offset+template.choice_index[tuple(row)]
                              for row in state.choices.tolist()]) for state in template.engine.leaves])
        cells,stages = {():(family,)},[]
        start = time.perf_counter()
        for i,template in enumerate(self.templates):
            cells = overlay(cells,template,max_boxes)
            stages.append(dict(templates=i+1,states=len(cells),boxes=sum(map(len,cells.values()))))
        overlay_s = time.perf_counter()-start
        self.execution_cells = cells
        start = time.perf_counter()
        groups = defaultdict(list)
        input_rows = 0
        for key,boxes in cells.items():
            ids = [r for i,leaf in enumerate(key) if leaf is not None for r in local_ids[i][leaf]]
            input_rows += len(ids)
            keep = tuple(int(v) for v in frontier_ids(self.costs,ids))
            groups[keep].extend(boxes)
        self.regions = [TerminalRegion(compact_boxes(boxes),np.array(ids,dtype=np.int64))
                        for ids,boxes in groups.items()]
        self.stats = dict(templates=template_stats,overlay_stages=stages,overlay_s=overlay_s,
                          joint_pareto_s=time.perf_counter()-start,joint_pareto_input_rows=input_rows,
                          terminal_frontiers=len(self.regions),terminal_boxes=sum(len(r.boxes) for r in self.regions),
                          unique_cost_rows=len(self.costs),terminal_rows=sum(len(r.ids) for r in self.regions))

    def query(self,point):
        point = tuple(point)
        if len(point) != 3 or any(type(v) is not int for v in point) or not self.family.contains(point):
            raise ValueError('query outside the integer architecture family')
        matches = [r for r in self.regions if any(box.contains(point) for box in r.boxes)]
        if len(matches) != 1:
            raise AssertionError('terminal regions must partition the entire family')
        ids = matches[0].ids.copy()
        return self.costs[ids].copy(),ids

    def mapping(self,source_id):
        if isinstance(source_id,(bool,np.bool_)) or not isinstance(source_id,(int,np.integer)) or not 0 <= source_id < len(self.origins):
            raise ValueError('invalid compiled Mapping source ID')
        i,j = self.origins[int(source_id)]
        t = self.templates[i]
        return b.reconstruct_best(t.program,t.choices[j:j+1],t.costs[j:j+1])

    def best_mapping(self,point):
        costs,ids = self.query(point)
        return self.mapping(ids[int(np.argmin(costs[:,0]*costs[:,1]))]) if len(ids) else None
