"""Six fixed-mapping re-evaluations to verify effect-contract flags, not search."""
import argparse
import functools
import hashlib
import inspect
import json
from pathlib import Path
from unittest.mock import patch

from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from research.diagnostics import causal_3mm
from research.tracking_audit import common


def verify():
    common.af.set_n_parallel_jobs(1);common.clear_switches()
    archive=json.loads(causal_3mm.SOURCE.read_text())
    old=json.loads((common.ROOT/'research/diagnostics/results/causal_3mm_controls.json').read_text())
    records=[]
    original=PmappingDataframe.merge_next;signature=inspect.signature(original)
    for pick in archive['runs'][0]['picks']:
        flags=[]
        @functools.wraps(original)
        def observed(*args,**kwargs):
            bound=signature.bind(*args,**kwargs);bound.apply_defaults();v=bound.arguments
            flags.append(dict(shared_loop_index=v['shared_loop_index'],
                next_shared_loop_index=v['next_shared_loop_index'],
                aliases=[dict(tensor=str(t.name),resource=str(t.resource_name),scope=t.above_loop_index)
                    for t in v['duplicated_aliased_tensors']]))
            return original(*args,**kwargs)
        mapping=causal_3mm.restore(pick['mapping'])
        with patch.object(PmappingDataframe,'merge_next',observed):
            result=causal_3mm.replay(mapping,pick['shape'],pick['capacity_bytes'])
        expected=next(r for r in old['replays']if r['shape']==pick['shape']and
            r['source_capacity_bytes']==pick['capacity_bytes']and r['capacity_bytes']==pick['capacity_bytes'])
        if result['globalbuffer_peak_bits']!=expected['globalbuffer_peak_bits']:
            raise AssertionError('fixed-source peak changed')
        if len(flags)!=len(result['join_resource_transfers']):raise AssertionError('missing Join flags')
        supported=all(not f['aliases']and not t['shared_to_free']and not t['live_to_alloc']and
            t['next_shared_loop_index']==-1 for f,t in zip(flags,result['join_resource_transfers']))
        records.append(dict(shape=pick['shape'],capacity_bytes=pick['capacity_bytes'],
            mapping_id=result['mapping_id'],peak_bits=result['globalbuffer_peak_bits'],
            join_flags=flags,closed_no_adjustment_contract=supported,
            resource_transfers=result['join_resource_transfers']))
    return dict(status='complete',fixed_mapping_evaluations=len(records),mapping_search_calls=0,
        all_six_contracts_verified=all(r['closed_no_adjustment_contract']for r in records),records=records,
        scope='New fixed-mapping contract probes only; no scalar hardware simulation or mapspace search.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=verify()
    result['source_sha256']={str(p.relative_to(common.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__),Path(causal_3mm.__file__))}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k]for k in ('fixed_mapping_evaluations','mapping_search_calls','all_six_contracts_verified')}),flush=True)


if __name__=='__main__':main()
