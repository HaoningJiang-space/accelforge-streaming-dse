"""Inspect real reconstructed two-MatMul FFM mappings; do not prune them."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

from research.tracking_audit import common
from research.tracking_audit.fusion_cut_inspect import inspect_whole_tensor_cut
from research.tracking_audit.shape_capacity_audit import build, mapping_structure, validate_pick


def actions(row):
    return {str(c):float(row[c]) for c in row.index if '<SEP>action<SEP>' in c and float(row[c]) != 0}


def audit(capacities, shape, output, dimensions=(4,8)):
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    case = common.Case('matmuls','nvdla',(2,*dimensions))
    metrics = common.RU | common.af.Metrics.ACTIONS
    paths = [Path(__file__),Path(__file__).with_name('fusion_cut_inspect.py'),
             common.ROOT/'examples/workloads/matmuls.yaml',common.ROOT/'examples/arches/nvdla.yaml']
    report = dict(scope='structural inspection only; no physical spill certificate or pruning',
                  case=str(case), shape=shape, capacities_bytes=capacities,
                  source_sha256={str(p.relative_to(common.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                  # Known only for the specific checked workload template, not a
                  # general inference from arbitrary tensor projections.
                  workload_T1_full_bits=dimensions[0]*dimensions[1]*8, searches=[], all_valid=False)
    output.parent.mkdir(parents=True,exist_ok=True)
    def save():
        output.write_text(json.dumps(report,indent=2)+'\n')
    for capacity in capacities:
        spec = build(case,shape,capacity,metrics)
        result,stats = common.search(spec)
        record = dict(capacity_bytes=capacity,search=stats,rows=[])
        report['searches'].append(record)
        save()
        for index in range(len(result.data)):
            row = result.data.iloc[index]
            mapping = row['Total<SEP>mapping']()
            cut = inspect_whole_tensor_cut(mapping)
            row_report = dict(index=index, mapping_id=common.mapping_identity(mapping), cut=cut,
                              mapping=mapping_structure(mapping), validation=None)
            record['rows'].append(row_report)
            try:
                row_report['validation'] = validate_pick(case,shape,capacity,row)
                target = build(case,shape,capacity,metrics)
                target.model.metrics = metrics
                target.mapping = copy.deepcopy(mapping)
                evaluated = common.evaluate_mapping(target).data
                if len(evaluated) != 1:
                    raise ValueError('expected one re-evaluated row')
                evaluated = evaluated.iloc[0]
                left, right = actions(row), actions(evaluated)
                if left != right:
                    raise ValueError('per-tensor action counts disagree after reconstruction')
                for column in ('Total<SEP>energy',common.LATENCY):
                    if not math.isclose(float(row[column]),float(evaluated[column]),rel_tol=1e-6,abs_tol=0):
                        raise ValueError('cost disagrees after reconstruction: '+column)
                row_report['actions_match'] = True
                row_report['t1_mainmemory_actions_bits'] = {c:v for c,v in right.items()
                    if '<SEP>MainMemory<SEP>T1<SEP>' in c}
                row_report['globalbuffer_peak_bits'] = int(evaluated['reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right'])
            except Exception as error:
                row_report['error'] = f'{type(error).__name__}: {error}'
                save()
                raise
            save()
    report['all_valid'] = bool(report['searches']) and all(
        r['rows'] and all(x.get('validation',{}).get('ok') and x.get('actions_match') for x in r['rows'])
        for r in report['searches'])
    save()
    if not report['all_valid']:
        raise AssertionError('missing results or failed re-evaluation')
    print(json.dumps({'all_valid':True,'searches':[(x['capacity_bytes'],len(x['rows'])) for x in report['searches']]}))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--capacities',nargs='+',type=int,default=[68,96,128])
    p.add_argument('--shape',nargs=2,type=int,default=[4,8])
    p.add_argument('--dimensions',nargs=2,type=int,default=[4,8],metavar=('M','KN'))
    a=p.parse_args()
    if any(x <= 0 for x in a.capacities + a.shape + a.dimensions):
        p.error('capacities, shape and dimensions must be positive')
    audit(a.capacities,tuple(a.shape),a.output,tuple(a.dimensions))
