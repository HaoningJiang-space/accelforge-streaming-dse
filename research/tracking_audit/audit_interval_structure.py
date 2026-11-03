"""Search partial FFM programs for noncontiguous membership, with per-target oracles.

This is a bounded search, not a proof of interval structure for FFM. In addition
to final candidates, inspect merged intermediate cohorts (history included).
"""
import argparse
import importlib
import itertools
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import sympy

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
tiles = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')
events = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.target_enumeration')


def job():
    return SimpleNamespace(spec=SimpleNamespace(mapper=SimpleNamespace(ffm=SimpleNamespace(
        _count_option_for_mapsapce_size_evaluation=()))), n_total_pmappings=1,
        n_evaluated_pmappings=0, pmapping_keep_rates={},
        log_message=lambda *a: None, log_porp_pmappings_kept=lambda *a: None)


def program(first, second, cost, bound=120, minimums=(1.,1.)):
    x, y, z = sympy.symbols('ix iy iz', integer=True, positive=True)
    relations = tiles.SymbolRelations()
    relations.what_tiles_symbol = [(bound,x),(x,y),(y,1),(bound,z),(z,1)]
    relations.make_bounds()
    usages = [y/x, x/y, 1/z, z/x, x/z, y/z]
    memory = (x*z+y)/(bound*bound+bound)
    objectives = [tiles.Objective('memory', memory, max_value=1)]
    for name, usage, threshold in [('first',usages[first],minimums[0]),('second',usages[second],minimums[1])]:
        objectives.append(tiles.Objective(name, usage, min_value=threshold,
                          try_best_if_none_reaches_min=True, only_care_if_valid=True))
    objectives.append(tiles.Objective('cost', x+z if cost == 0 else x*z+y))
    return objectives, memory, dict(symbols=[x,y,z],what_tiles_symbol=relations)


def run_count(allowed):
    return np.sum(allowed & ~np.concatenate([np.zeros((len(allowed),1),dtype=bool), allowed[:,:-1]],axis=1),axis=1)


def audit(first,second,cost,bounds,minimums=(1.,1.)):
    objectives,memory,args = program(first,second,cost,minimums=minimums)
    original = events.merge_cohorts
    original_pareto = events.TargetEnumerator.pareto
    intermediate = dict(max_runs=0, observations=0, witness=None)
    pareto_by_prefix = {}
    def observed_pareto(enumerator,state,goals):
        before = enumerator.stats['pareto_calls']
        result = original_pareto(enumerator,state,goals)
        calls = enumerator.stats['pareto_calls'] - before
        if calls:
            prefix = len(enumerator.done)
            pareto_by_prefix[prefix] = pareto_by_prefix.get(prefix,0) + calls
        return result
    def observed(states,stats):
        result = original(states,stats)
        for s in result:
            ids = sorted(s.targets)
            runs = 1 + sum(b != a+1 for a,b in zip(ids,ids[1:]))
            intermediate['observations'] += 1
            if runs > intermediate['max_runs']:
                intermediate['max_runs'] = runs
                if runs > 1:
                    intermediate['witness'] = dict(targets=ids, choices=s.choices.tolist(), history=repr(s.history))
        return result
    os.environ['AF_TARGET_ENUMERATION']='events'
    events.merge_cohorts = observed
    events.TargetEnumerator.pareto = observed_pareto
    try:
        j = job()
        choices, excluded = tiles.get_tile_shape_choices_for_targets(
            objectives,[(memory,b) for b in bounds],job=j,**args)
    finally:
        events.merge_cohorts = original
        events.TargetEnumerator.pareto = original_pareto
    references = []
    for i,b in enumerate(bounds):
        extra = tiles.Objective('target',memory,max_value=b,only_care_if_valid=True)
        reference = np.unique(tiles.get_tile_shape_choices(
            objectives[:1]+[extra]+objectives[1:],job=job(),**args),axis=0)
        np.testing.assert_array_equal(choices[~excluded[:,i]],reference)
        references.append(reference)
    expected_union = np.unique(np.concatenate(references),axis=0)
    np.testing.assert_array_equal(choices,expected_union,strict=True)
    counts = run_count(~excluded)
    witnesses = np.flatnonzero(counts>1)
    return dict(program=[first,second,cost],minimums=minimums,formulae=[str(o.formula) for o in objectives],
                rows=len(choices),max_final_runs=int(counts.max(initial=0)),
                final_witnesses=[dict(tile=choices[i].tolist(),targets=np.flatnonzero(~excluded[i]).tolist()) for i in witnesses],
                intermediate=intermediate,pareto_by_prefix=pareto_by_prefix,
                stats=j.target_enumeration_stats,oracle_equal=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    # Include exhausted targets, pressure events, and the full generation capacity.
    bounds=np.geomspace(1e-5,1.,32).tolist()
    report=dict(bound=120,bounds=bounds,runs=[])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    # Include unattainable and mixed thresholds, not only constraints satisfied
    # by the all-ones Tile. Those profiles actually exercise ordered fallback.
    profiles=[(1.,1.),(2.,2.),(.5,2.),(2.,.5)]
    for *indices, minimums in itertools.product(range(6),range(6),range(2),profiles):
        row=audit(*indices,bounds,minimums=minimums)
        report['runs'].append(row)
        a.output.write_text(json.dumps(report,indent=2)+'\n')
        print(indices,minimums,'final runs',row['max_final_runs'],'cohort runs',row['intermediate']['max_runs'],
              'Pareto calls',row['stats']['pareto_calls'],flush=True)
    report['summary']=dict(programs=len(report['runs']),oracle_projections=len(bounds)*len(report['runs']),
        max_final_runs=max(r['max_final_runs'] for r in report['runs']),
        max_cohort_runs=max(r['intermediate']['max_runs'] for r in report['runs']),
        programs_with_pareto=sum(r['stats']['pareto_calls']>0 for r in report['runs']),
        programs_with_partial_pareto=sum(any(prefix<3 for prefix in r['pareto_by_prefix']) for r in report['runs']),
        all_equal=all(r['oracle_equal'] for r in report['runs']))
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(report['summary'],flush=True)


if __name__=='__main__':
    main()
