"""A synthetic FFM prefix-Pareto counterexample to single-interval membership.

Resource units are abstract; this is not a reconstructed physical Mapping.
The shared Event algorithm reproduces the independent FFM policy exactly.
"""
import argparse
import json
import os
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from audit_interval_structure import program, job, tiles, events
from accelforge.mapper.FFM._pareto_df.capacity_membership import encode_membership, membership_for_target
from accelforge.mapper.FFM._pareto_df.interval_membership import is_interval_col


def reproduce():
    objectives,memory,args=program(1,3,0,minimums=(2.,2.))
    # Equivalent normalized usages, both with threshold 1 rather than 2.
    for i in (1,2):
        objectives[i]=tiles.Objective(objectives[i].name,objectives[i].formula/2,
            min_value=1.,try_best_if_none_reaches_min=True,only_care_if_valid=True)
    capacities=[6,10,28]
    bounds=[c/14520 for c in capacities]
    witness=np.array([2,1,2])

    def independent():
        rows=[]
        for b in bounds:
            extra=tiles.Objective('target',memory,max_value=b,only_care_if_valid=True)
            rows.append(np.unique(tiles.get_tile_shape_choices(
                objectives[:1]+[extra]+objectives[1:],job=job(),**args),axis=0))
        return rows

    prefix_calls=[]
    original=events.TargetEnumerator.pareto
    def observed(enumerator,state,goals):
        before=enumerator.stats['pareto_calls']
        result=original(enumerator,state,goals)
        if enumerator.stats['pareto_calls']>before:
            prefix_calls.append(len(enumerator.done))
        return result

    with patch.dict(os.environ,{'AF_TARGET_ENUMERATION':'events','AF_CAPACITY_MEMBERSHIP':'interval',
                                'AF_ENUMERATION_PREFIX_BYTES':'0','AF_ENUMERATION_PARETO_BYTES':'0'}):
        references=independent()
        j=job()
        with patch.object(events.TargetEnumerator,'pareto',observed):
            choices,excluded=tiles.get_tile_shape_choices_for_targets(
                objectives,[(memory,b) for b in bounds],job=j,**args)
        for i,reference in enumerate(references):
            np.testing.assert_array_equal(choices[~excluded[:,i]],reference)
        present=[bool(np.any(np.all(rows==witness,axis=1))) for rows in references]
        assert present==[True,False,True]
        frame=pd.DataFrame(encode_membership('GlobalBuffer',bounds,excluded,len(choices)))
        assert not any(is_interval_col(c) for c in frame), 'must retain the membership hole'
        for i,b in enumerate(bounds):
            np.testing.assert_array_equal(membership_for_target(frame,'GlobalBuffer',b),~excluded[:,i])
        # Diagnostic ablation only: the complete run has one actual Pareto call,
        # at the two-symbol prefix. Disabling it removes this re-entry witness.
        with patch.object(tiles,'makepareto_numpy',lambda matrix,*a,**kw:np.ones(len(matrix),dtype=bool)):
            without=independent()
    return dict(capacity_units=capacities,capacity_fractions=bounds,resource_formula=str(memory),
                usages=[str(o.formula) for o in objectives[1:3]],thresholds=[1,1],
                cost=str(objectives[-1].formula),symbol_order=[str(s) for s in args['symbols']],
                relations='120 -> ix -> iy -> 1; 120 -> iz -> 1',
                witness=witness.tolist(),allowed=present,independent=[r.tolist() for r in references],
                event_choices=choices.tolist(),event_excluded=excluded.tolist(),
                actual_pareto_prefix_lengths=prefix_calls,event_stats=j.target_enumeration_stats,
                backend='bitset',shared_matches_independent=True,
                pareto_disabled_choices=[r.tolist() for r in without],
                pareto_disabled_allowed=[bool(np.any(np.all(r==witness,axis=1))) for r in without])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    report=reproduce()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    main()
