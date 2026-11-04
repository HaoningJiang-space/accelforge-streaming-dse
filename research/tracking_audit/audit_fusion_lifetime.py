"""Rebuild real FFM winners/frontiers and audit restricted phase ledgers."""
import argparse
import copy
from collections import Counter
import hashlib
import json
from pathlib import Path

from research.tracking_audit import common
from research.tracking_audit.audit_fusion_cut import actions
from research.tracking_audit.fusion_lifetime_ledger import mapping_ledger, validate_dense_contract
from research.tracking_audit.shape_capacity_audit import build, validate_pick


def run(output):
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    metrics = common.RU | common.af.Metrics.ACTIONS
    shape = (4,8)
    archive = Path(__file__).parent/'results/fusion_cut'
    paths = [Path(__file__),Path(__file__).with_name('fusion_lifetime_ledger.py'),
             Path(__file__).with_name('fusion_cut_inspect.py'),common.ROOT/'examples/workloads/matmuls.yaml',
             common.ROOT/'examples/arches/nvdla.yaml', archive/'audit.json',archive/'larger.json']
    report = dict(scope='representative per-phase reservation scopes, not cut capacity or pruning',
                  source_sha256={str(p.relative_to(common.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                  cases=[],all_valid=False)
    output.parent.mkdir(parents=True,exist_ok=True)
    def save():
        output.write_text(json.dumps(report,indent=2)+'\n')
    for dimensions,capacities,reference in [((4,8),(68,96,128),'audit.json'),((8,16),(512,),'larger.json')]:
        case = common.Case('matmuls','nvdla',(2,*dimensions))
        old = json.loads((archive/reference).read_text())
        for capacity in capacities:
            previous = next(s for s in old['searches'] if s['capacity_bytes']==capacity)
            spec = build(case,shape,capacity,metrics)
            contract = validate_dense_contract(spec,*dimensions)
            result,_ = common.search(spec)
            case_result = dict(dimensions=dimensions,shape=shape,capacity_bytes=capacity,contract=contract,rows=[])
            report['cases'].append(case_result)
            for index in range(len(result.data)):
                row = result.data.iloc[index]
                mapping = row['Total<SEP>mapping']()
                ident = common.mapping_identity(mapping)
                match = [x for x in previous['rows'] if x['mapping_id']==ident]
                if not match:
                    raise AssertionError('reconstructed mapping missing from previous audit')
                log = mapping_ledger(mapping,*dimensions,capacity*8,contract=contract)
                verified = validate_pick(case,shape,capacity,row)
                target = build(case,shape,capacity,metrics)
                target.model.metrics = metrics
                target.mapping = copy.deepcopy(mapping)
                evaluated = common.evaluate_mapping(target).data.iloc[0]
                if actions(row) != actions(evaluated):
                    raise AssertionError('reconstructed per-tensor actions differ')
                model_peak = int(evaluated['reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right'])
                peak_matches = (log['phase_peak_bits']==model_peak) if log['status']=='phase_scopes_only' else None
                case_result['rows'].append(dict(mapping_id=ident,ledger=log,validation=verified,
                    action_counts_match=True,model_peak_bits=model_peak,phase_peak_matches_model=peak_matches,
                    reference_indices=[x['index'] for x in match]))
                save()
            if Counter(r['mapping_id'] for r in case_result['rows']) != Counter(r['mapping_id'] for r in previous['rows']):
                raise AssertionError('frontier mapping IDs differ from previous audit')
    report['all_valid'] = all(c['rows'] and all(r['validation']['ok'] and r['action_counts_match']
        and (r['phase_peak_matches_model'] is not False) and not r['ledger']['safe_to_prune']
        for r in c['rows']) for c in report['cases'])
    save()
    if not report['all_valid']:
        raise AssertionError('some ledgers or re-evaluations do not match')
    print(json.dumps(dict(all_valid=True,rows=sum(len(x['rows']) for x in report['cases']))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output)
