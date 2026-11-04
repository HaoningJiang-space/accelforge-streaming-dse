"""All-template candidate/terminal audits plus normal full-FFM physical searches."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from research.tracking_audit import benchmark_parametric_operator as a


def endpoint_queries(compiled):
    """Exercise each joint execution cell and both faces of each terminal box."""
    candidates = set()
    for boxes in compiled.execution_cells.values():
        for box in boxes:
            candidates.add(tuple((lo+hi)//2 for lo,hi in box.ranges))
    faces = set()
    for region in compiled.regions:
        for box in region.boxes:
            for side in (0,1):
                point = tuple(interval[side] for interval in box.ranges)
                faces.add(point)
                for axis in range(3):
                    for delta in (-1,1):
                        neighbor = list(point)
                        neighbor[axis] += delta
                        neighbor = tuple(neighbor)
                        if compiled.family.contains(neighbor):
                            faces.add(neighbor)
    return sorted(candidates),sorted(faces)


def run(output,physical_limit):
    a.b.common.af.set_n_parallel_jobs(1)
    a.b.common.clear_switches()
    case = a.b.common.Case('matmuls','nvdla',(1,256,256))
    programs = a.p.prepare_all(256,tuple(hi for lo,hi in a.FAMILY.ranges))
    compiled = a.p.CompiledOperator(programs,a.FAMILY)
    centers,faces = endpoint_queries(compiled)
    # Query point selection is after compilation; the compiler never sees it.
    selected = sorted(set(faces[i] for i in np.linspace(0,len(faces)-1,physical_limit,dtype=int)))
    physical_points = sorted(set(selected+a.query_points(64)))
    records = dict(config=a.b.common.effective_config(case),source_sha256=a.sources(),
                   audit_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   joint_cell_queries=len(centers),terminal_face_candidates=len(faces),
                   physical_queries=len(physical_points),projections=[],physical=[])
    a.b.save(output,records)
    for index,point in enumerate(centers):
        front,_ = compiled.query(point)
        ref,_,choices,_ = a.independent_query(programs,point)
        expected = a.candidate_records(programs,choices)
        actual = a.candidate_records(programs,[t.query(point)[0] for t in compiled.templates])
        same = expected==actual and np.array_equal(front,ref)
        records['projections'].append(dict(point=point,all_template_tiles=expected==actual,
                                          frontier=np.array_equal(front,ref)))
        if not same:
            records['failure'] = dict(point=point,expected=expected,actual=actual,front=front.tolist(),reference=ref.tolist())
            a.b.save(output,records)
            raise AssertionError(f'prepared oracle mismatch at {point}')
        if (index+1)%50 == 0:
            a.b.save(output,records)
            print(f'prepared projection {index+1}/{len(centers)}',flush=True)
    a.b.save(output,records)
    for index,point in enumerate(physical_points):
        actual,ids = compiled.query(point)
        reference,ref_pick,candidates,_ = a.physical_query(256,point)
        expected = a.candidate_records(programs,[t.query(point)[0] for t in compiled.templates])
        same = np.array_equal(actual,reference) and candidates==expected
        record = dict(point=point,all_template_tiles=candidates==expected,
                      frontier=np.array_equal(actual,reference),rows=len(actual))
        records['physical'].append(record)
        if not same:
            records['failure'] = dict(point=point,expected=expected,actual=candidates,
                                      frontier=actual.tolist(),reference=reference.tolist())
            a.b.save(output,records)
            raise AssertionError(f'normal full FFM mismatch at {point}')
        # All returned frontier vectors, not just the best EDP, must have a valid
        # source Mapping. Cache only identical source IDs AND physical points.
        validations = [a.b.validate_selected(case,point,compiled.mapping(i)) for i in ids]
        record['all_frontier_mappings_valid'] = all(v['ok'] and v['exact_gb_match'] for v in validations)
        record['mapping_ids'] = [v['mapping_id'] for v in validations]
        record['independent_best'] = a.b.validate_selected(case,point,ref_pick)
        a.b.save(output,records)
        print(f'physical full FFM {index+1}/{len(physical_points)}; {len(ids)} frontier mappings valid',flush=True)
    records['all_passed'] = True
    records['frontier_re_evaluations'] = sum(r['rows'] for r in records['physical'])
    a.b.save(output,records)
    print(json.dumps({k:v for k,v in records.items() if k in (
        'joint_cell_queries','physical_queries','frontier_re_evaluations','all_passed')}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--physical-limit',type=int,default=64)
    args=parser.parse_args()
    if args.physical_limit < 1:
        parser.error('physical-limit must be positive')
    run(args.output,args.physical_limit)
