"""Untimed rejection accounting after native Join materialization."""
import argparse
from contextlib import ExitStack
import hashlib
import importlib
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np

from research.diagnostics.profile_3mm_search import execute,snapshots,common
from accelforge.mapper.FFM._pareto_df import exact_resources as exact
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import nameloop2col


class FilterAudit:
    def __init__(self):self.scope='other';self.in_merge=0;self.stats={}
    def __enter__(self):
        self.stack=ExitStack()
        cls=importlib.import_module('accelforge.mapper.FFM._join_pmappings.pmapping_dataframe').PmappingDataframe
        limit,pareto,merge=cls.limit_capacity,cls.make_pareto,cls.merge_next
        for name,scope in (('make_pmappings','generation'),('join_pmappings','join')):
            original=getattr(common,name)
            def wrapped(*args,_original=original,_scope=scope,**kwargs):
                old=self.scope;self.scope=_scope
                try:return _original(*args,**kwargs)
                finally:self.scope=old
            self.stack.enter_context(patch.object(common,name,wrapped))
        def bucket():
            label=self.scope+('_inside_merge'if self.in_merge else'_outside_merge')
            return self.stats.setdefault(label,dict(capacity_calls=0,capacity_input_rows=0,
                capacity_dropped_rows=0,gb_invalid_rows=0,pareto_calls=0,pareto_input_rows=0,pareto_dropped_rows=0))
        def capacity(frame,*args,**kwargs):
            stat=bucket();before=len(frame.data);invalid=np.zeros(before,dtype=bool)
            right=frame.right_reservations.get('GlobalBuffer',())
            columns=([nameloop2col('GlobalBuffer',max(right))]if right else[])+[
                nameloop2col('GlobalBuffer',i,left=True)for i in frame.left_reservations.get('GlobalBuffer',())]
            cap=exact.capacity(frame.data,'GlobalBuffer')
            for c in columns:invalid|=frame.data[c].to_numpy()>cap
            result=limit(frame,*args,**kwargs)
            dropped=before-len(frame.data)
            if dropped<np.count_nonzero(invalid):raise AssertionError('GB rejection is not a subset of actual capacity rejections')
            stat['capacity_calls']+=1;stat['capacity_input_rows']+=before
            stat['capacity_dropped_rows']+=dropped;stat['gb_invalid_rows']+=int(np.count_nonzero(invalid))
            return result
        def dominance(frame,*args,**kwargs):
            stat=bucket();before=len(frame.data);result=pareto(frame,*args,**kwargs)
            stat['pareto_calls']+=1;stat['pareto_input_rows']+=before
            stat['pareto_dropped_rows']+=before-len(frame.data)
            return result
        def joined(*args,**kwargs):
            self.in_merge+=1
            try:return merge(*args,**kwargs)
            finally:self.in_merge-=1
        self.stack.enter_context(patch.object(cls,'limit_capacity',capacity))
        self.stack.enter_context(patch.object(cls,'make_pareto',dominance))
        self.stack.enter_context(patch.object(cls,'merge_next',joined))
        return self
    def __exit__(self,*args):return self.stack.__exit__(*args)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--variant',choices=('cached_ru','events_ru'),required=True)
    p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    common.af.set_n_parallel_jobs(1);common.clear_switches()
    with FilterAudit()as audit:outputs,_=execute(args.variant)
    reference=json.loads(args.reference.read_text())
    if snapshots(outputs,True)!=reference['frontiers']:raise AssertionError('rejection tracing changed frontiers')
    result=dict(status='complete',variant=args.variant,observations=audit.stats,frontiers_equal=True,
        timing_claim=False,row_scope='Row occurrences, not unique mappings. Native NumPy-prefix pruning is separate. No claim that rejected pairs can all be eliminated earlier.',
        source_sha256={str(f.relative_to(common.ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in (Path(__file__),Path(__file__).with_name('profile_3mm_search.py'))})
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['observations']),flush=True)


if __name__=='__main__':main()
