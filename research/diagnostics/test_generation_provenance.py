import numpy as np
import pandas as pd
import pytest

from research.diagnostics.generation_provenance_3mm import GenerationProvenance, task_value, tile_key


def test_tile_lineage_preserves_high_integer_bits_and_rejects_lost_symbols():
    frame = pd.DataFrame({'e<SEP>x':np.array([2**63+7], dtype='uint64'), 'cost':[0.5]})
    assert tile_key(frame, ['x'], 'e') == [(2**63+7,)]
    with pytest.raises(AssertionError, match='lost'):
        tile_key(frame, ['y'], 'e')
    assert tile_key(pd.DataFrame({'x':[1.]}), ['x']) == [(1,)]
    with pytest.raises(AssertionError, match='integral'):
        tile_key(pd.DataFrame({'x':[1.5]}), ['x'])
    with pytest.raises(AssertionError, match='integral'):
        tile_key(pd.DataFrame({'x':[float(2**53)]}), ['x'])


def test_shared_task_with_one_frontier_descendant_gets_no_proportional_time_credit():
    tasks = [dict(id='a',tile_ids=['a0','a1','a2'],evaluation_s=5.),
        dict(id='b',tile_ids=['b0'],evaluation_s=2.)]
    batches = [dict(task_ids=['a','b'],non_job_s=1.)]
    result = task_value(tasks,batches,{'a0'},10.,12.)
    assert result['unused_model_rows']==3
    assert result['posthoc_whole_task_saving_s']==2.
    assert result['wholly_unused_batches']==0
    assert result['uncredited_generation_s']==2.
    assert result['fixed_other_cost_speedup_projection']==1.2


def test_wholly_unused_batch_is_counted_once_and_shared_setup_is_not_credited():
    tasks = [dict(id='a',tile_ids=['a0'],evaluation_s=3.),
        dict(id='b',tile_ids=[],evaluation_s=2.)]
    batches = [dict(task_ids=['a'],non_job_s=1.),dict(task_ids=['b'],non_job_s=1.)]
    result = task_value(tasks,batches,{'a0'},9.,10.)
    assert result['wholly_unused_batches']==1
    assert result['posthoc_whole_task_saving_s']==3.
    assert result['uncredited_generation_s']==2.


def test_all_frontier_rows_and_all_capacities_contribute_to_used_tile_union():
    audit = GenerationProvenance()
    audit.tasks = [dict(id='a',target='t',tile_ids=['a0','a1'],evaluation_s=1.),
        dict(id='b',target='t',tile_ids=['b0'],evaluation_s=1.)]
    audit.generation_s = 3.
    label = repr(((16,384),(131072,135168)))
    audit.roots[label] = [('a0',),('a1',),('b0',)]
    outputs = {(16,384,131072):pd.DataFrame({'energy':[1,2]},index=[0,1]),
        (16,384,135168):pd.DataFrame({'energy':[3]},index=[2])}
    result = audit.finish(outputs,4.)
    assert result['used_tile_ids']==['a0','a1','b0']
    assert result['summary']['tasks_without_final_descendants']==0
    assert sum(map(len,result['final_sources'].values()))==3


def test_observer_restores_native_functions_when_an_exception_occurs():
    from research.tracking_audit import common
    original = common.make_pmappings
    with pytest.raises(RuntimeError):
        with GenerationProvenance():
            assert common.make_pmappings is not original
            raise RuntimeError('probe')
    assert common.make_pmappings is original


def test_nonadditive_task_timing_fails_closed():
    with pytest.raises(AssertionError, match='double counts'):
        task_value([dict(id='a',tile_ids=[],evaluation_s=3.)],[],set(),2.,4.)
