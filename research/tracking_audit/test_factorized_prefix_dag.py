import copy
import itertools
from unittest.mock import patch

import numpy as np
import pytest
import sympy

from research.tracking_audit import benchmark_parametric_template as bench
from research.tracking_audit import parametric_operator as op
from research.tracking_audit.audit_interval_structure import job, program, tiles
from research.tracking_audit.factorized_prefix_dag import FactorizedPrefixRegions, IdState
from research.tracking_audit.parametric_template import Box, RegionEnumerator


def small_problem():
    x,y = sympy.symbols('dag_x dag_y',positive=True,integer=True)
    relations=tiles.SymbolRelations()
    relations.what_tiles_symbol=[(12,x),(x,1),(12,y),(y,1)]
    relations.make_bounds()
    objectives=[tiles.Objective('capacity',x+y,max_value=24,exact=True),
        tiles.Objective('x_limit',x,max_value=12,only_care_if_valid=True,exact=True),
        tiles.Objective('y_limit',y,max_value=12,only_care_if_valid=True,exact=True),
        tiles.Objective('x_usage',x,min_value=12,only_care_if_valid=True,try_best_if_none_reaches_min=True,exact=True),
        tiles.Objective('y_usage',y,min_value=12,only_care_if_valid=True,try_best_if_none_reaches_min=True,exact=True),
        tiles.Objective('cost',x+2*y)]
    return objectives,dict(symbols=[x,y],what_tiles_symbol=relations),{
        'capacity':2,'x_limit':0,'y_limit':1,'x_usage':0,'y_usage':1}


def test_two_ordered_fallbacks_match_every_point_and_choice_order():
    objectives,args,axes=small_problem(); family=Box(((1,5),(1,5),(1,12)))
    reference=RegionEnumerator(tiles,copy.deepcopy(objectives),family,axes=axes,job=job(),**copy.deepcopy(args)).build()
    actual=FactorizedPrefixRegions(tiles,copy.deepcopy(objectives),family,axes=axes,job=job(),**copy.deepcopy(args)).build()
    for point in itertools.product(range(1,6),range(1,6),range(1,13)):
        np.testing.assert_array_equal(actual.query(point),reference.query(point),strict=True)
    assert actual.stats['shared_expanded_rows'] <= actual.stats['requested_expanded_rows']


def test_noncontiguous_membership_and_prefix_pareto_match_every_capacity():
    objectives,memory,args=program(1,3,0,minimums=(2.,2.))
    raw=sympy.expand(memory*14520)
    objectives[0]=tiles.Objective('memory',raw,max_value=14520)
    objectives.insert(1,tiles.Objective('target',raw,max_value=128,only_care_if_valid=True,exact=True))
    engine=FactorizedPrefixRegions(tiles,copy.deepcopy(objectives),Box(((1,1),(1,1),(1,128))),
                                   axes={'target':2},job=job(),**copy.deepcopy(args)).build()
    observed=[]
    for capacity in range(1,129):
        independent=copy.deepcopy(objectives);independent[1].max_value=capacity
        expected=tiles.get_tile_shape_choices(independent,job=job(),**copy.deepcopy(args))
        actual=engine.query((1,1,capacity))
        np.testing.assert_array_equal(actual,expected,strict=True)
        if np.any(np.all(actual==[2,1,2],axis=1)):
            observed.append(capacity)
    assert observed==[5,6]+list(range(26,129))
    assert engine.stats['pareto_calls']>0


def test_factorized_budget_fails_explicitly():
    objectives,args,axes=small_problem()
    with pytest.raises(MemoryError,match='budget'):
        FactorizedPrefixRegions(tiles,objectives,Box(((1,5),(1,5),(1,12))),axes=axes,
                                max_rows=1,job=job(),**args).build()


def test_identical_ids_cannot_merge_different_history_or_order():
    objectives,args,axes=small_problem()
    engine=FactorizedPrefixRegions(tiles,objectives,Box(((1,1),(1,1),(1,4))),axes=axes,job=job(),**args)
    box=lambda c:Box(((1,1),(1,1),(c,c)))
    ids=np.array([0,1],dtype=np.uint32)
    states=[IdState(ids,(box(1),)),IdState(ids.copy(),(box(2),)),
            IdState(ids[::-1],(box(3),)),IdState(ids,(box(4),),(frozenset({('x','min')}),))]
    merged=engine._merge(states)
    assert len(merged)==3 and merged[0].targets==(Box(((1,1),(1,1),(1,2))),)


def test_loop_limit_keeps_the_same_ordered_prefixes():
    objectives,args,axes=small_problem(); family=Box(((1,2),(1,2),(1,6)))
    args['max_loop_check_groups']=[(0,[args['symbols'][0]])]
    original=RegionEnumerator(tiles,copy.deepcopy(objectives),family,axes=axes,job=job(),**copy.deepcopy(args)).build()
    factorized=FactorizedPrefixRegions(tiles,copy.deepcopy(objectives),family,axes=axes,job=job(),**copy.deepcopy(args)).build()
    for point in itertools.product(range(1,3),range(1,3),range(1,7)):
        np.testing.assert_array_equal(factorized.query(point),original.query(point),strict=True)


@pytest.mark.parametrize('seed',[7,813,2603])
def test_shuffled_symbol_and_constraint_orders_match_their_own_reference(seed):
    rng=np.random.default_rng(seed)
    for _ in range(5):
        objectives,args,axes=small_problem();family=Box(((1,3),(1,3),(1,8)))
        rng.shuffle(objectives);rng.shuffle(args['symbols'])
        original=RegionEnumerator(tiles,copy.deepcopy(objectives),family,axes=axes,job=job(),**copy.deepcopy(args)).build()
        actual=FactorizedPrefixRegions(tiles,copy.deepcopy(objectives),family,axes=axes,job=job(),**copy.deepcopy(args)).build()
        for point in itertools.product(range(1,4),range(1,4),range(1,9)):
            np.testing.assert_array_equal(actual.query(point),original.query(point),strict=True)


@pytest.mark.parametrize('index',[1,3])
def test_real_heavy_template_all_regions_and_histories_match(index):
    from research.tracking_audit.benchmark_parametric_operator import FAMILY
    bench.common.af.set_n_parallel_jobs(1)
    bench.common.clear_switches()
    program=op.prepare_all(256,tuple(hi for _,hi in FAMILY.ranges))[index]
    expected=bench.CompiledTemplate(program,FAMILY)
    with patch.object(bench,'RegionEnumerator',FactorizedPrefixRegions):
        actual=bench.CompiledTemplate(program,FAMILY)
    assert len(actual.engine.leaves)==len(expected.engine.leaves)
    for l,r in zip(actual.engine.leaves,expected.engine.leaves):
        assert l.targets==r.targets and l.history==r.history
        np.testing.assert_array_equal(l.choices,r.choices,strict=True)
    for l,r in zip(actual.frontiers,expected.frontiers):
        np.testing.assert_array_equal(l,r,strict=True)
    assert actual.engine.stats['shared_expanded_rows'] <= actual.engine.stats['requested_expanded_rows']
    assert actual.engine.stats['peak_state_bytes'] == actual.engine.stats['peak_id_bytes'] > 0
    for point in ((48,128,135168),(24,256,131072),(96,64,65536),
                  (31,127,65535),(32,128,65536),(33,129,65537)):
        physical=bench.prepare(256,point,program.template_key)
        direct,_=bench.oracle(physical)
        choices,frontier=actual.query(point)
        np.testing.assert_array_equal(bench.canonical_choices(choices),bench.canonical_choices(direct),strict=True)
        np.testing.assert_array_equal(frontier,bench.frontier(bench.selected_costs(physical,direct)),strict=True)


def test_summary_rejects_a_mismatch_in_an_earlier_repeat(tmp_path):
    import json
    from research.tracking_audit.summarize_prefix_dag import run
    for index in (1,3):
        for mode in ('region','dag','cached'):
            for repeat in (1,2,3):
                queries=[dict(point=[i,1,1],choices={'rows':1,'sha256':'ok'},frontier=[[1,2,3]],cumulative_s=i+1,
                              reconstruction={'ok':True,'exact_gb_match':True})
                         for i in range(256)]
                if index==1 and mode=='dag' and repeat==1:
                    queries[0]['choices']['sha256']='wrong'
                record=dict(template=index,mode=mode,source_sha256={'code':'same'},queries=queries,
                    all_sampled_reconstructions_valid=True,total_s=1,preprocess_s=1,search_peak_rss_gib=1,
                    compilation={},cache_work={})
                (tmp_path/f'{index}_{mode}_{repeat}.json').write_text(json.dumps(record))
    with pytest.raises(ValueError,match='candidate or complete frontier'):
        run(tmp_path)
