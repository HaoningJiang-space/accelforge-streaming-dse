"""Probe region endpoints with independently constructed physical architectures.

No future query points are supplied to the compiler. This is an additional
correctness audit, not a performance run: oracle preparation and reconstruction
are intentionally performed for every point, including empty regions.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from research.tracking_audit import benchmark_parametric_template as b
from research.tracking_audit.parametric_template import Box


def boundary_points(compiled):
    points = set()
    for state in compiled.engine.leaves:
        for box in state.targets:
            # Internal C is bits. Only integer-byte architectures are queried.
            lo = (box.ranges[2][0]+7)//8
            hi = box.ranges[2][1]//8
            if lo > hi:
                continue
            for side,capacity in ((0,lo),(1,hi)):
                point = (box.ranges[0][side],box.ranges[1][side],capacity)
                points.add(point)
                # Cross a resource or shape boundary by its smallest unit.
                for axis in range(3):
                    for delta in (-1,1):
                        neighbor = list(point)
                        neighbor[axis] += delta
                        neighbor = tuple(neighbor)
                        if compiled.family_bytes.contains(neighbor):
                            points.add(neighbor)
    return sorted(points)


def run(output):
    b.common.af.set_n_parallel_jobs(1)
    b.common.clear_switches()
    family = Box(((8,128),(16,384),(32*1024,256*1024)))
    program = b.prepare(256,(128,384,256*1024))
    compiled = b.CompiledTemplate(program,family)
    points = boundary_points(compiled)
    report = dict(config=b.common.effective_config(b.common.Case('matmuls','nvdla',(1,256,256))),
                  source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in (Path(__file__),Path(b.__file__),Path(__file__).with_name('parametric_template.py'))},
                  family=family.ranges, points=len(points), results=[])
    b.save(output,report)
    for i,point in enumerate(points):
        choices,costs = compiled.query(point)
        physical = b.prepare(256,point,program.template_key)
        reference,_ = b.oracle(physical)
        expected = b.frontier(b.selected_costs(physical,reference))
        same_tiles = np.array_equal(b.canonical_choices(choices),b.canonical_choices(reference))
        same_frontier = np.array_equal(costs,expected)
        check = b.validate_selected(b.common.Case('matmuls','nvdla',(1,256,256)),
                                    point,compiled.best_mapping(point))
        report['results'].append(dict(point=point,tiles=same_tiles,frontier=same_frontier,
                                      rows=len(choices),reconstruction=check))
        b.save(output,report)
        if not same_tiles or not same_frontier or not check['ok']:
            raise AssertionError(f'boundary mismatch at {point}')
        if (i+1)%25 == 0:
            print(f'{i+1}/{len(points)} physical endpoint queries passed',flush=True)
    report['all_passed'] = True
    b.save(output,report)
    print(json.dumps(dict(points=len(points),all_passed=True)),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output)
