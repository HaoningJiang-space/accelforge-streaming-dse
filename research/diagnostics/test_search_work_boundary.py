"""Check observation boundaries/counters, not runtime thresholds."""
import inspect
from unittest.mock import patch

import pytest

from research.joint_synthesis import search_engine as engine
from research.joint_synthesis.graph_ir import TwoMM, CostModel
from research.joint_synthesis.exhaustive_oracle import exhaustive
from research.joint_synthesis.validate import independent_frontier
from research.diagnostics.search_work_boundary import WorkObservation, observe
from research.diagnostics.profile_search_work import POLICIES


@pytest.mark.parametrize('policy',list(POLICIES.values()))
@pytest.mark.parametrize('shape',[(1,1,1,1),(2,2,2,2)])
def test_observation_preserves_every_plan_statistic_and_counts_real_operations(policy,shape):
    graph, model = TwoMM(*shape), CostModel()
    expected = engine.TwoMMSearch(graph,model,policy).solve()
    actual, trace = observe(graph,model,policy)
    assert actual == expected
    assert trace['exclusive_partition_equal']
    assert sum(trace['exclusive_buckets_s'].values()) == pytest.approx(trace['search_inclusive_s'])
    assert all(v['exclusive_s']>=0 and v['failed_calls']==0 for v in trace['scopes'].values())
    assert trace['composition']['complete_plan_constructions'] == expected[1]['materialized_complete_pairs']
    assert trace['no_evaluation_avoided_before_local_pareto']
    assert trace['stages']['produce']['evaluations'] == (12 if shape[0]==1 else 96)
    assert trace['stages']['consume']['evaluations'] == (12 if shape[0]==1 else 96)
    assert trace['scopes']['provider.generate']['calls']==1
    if not policy.local_pruning:
        assert trace['stages']['produce']['pareto_add_calls']==0
        assert trace['composition']['complete_plan_constructions']==(162 if shape[0]==1 else 10368)


def test_profiled_policy_frontiers_agree_with_independent_scalar_execution():
    graph, model = TwoMM(1,1,1,1), CostModel(2,3,7,5)
    values, stats = exhaustive(graph,model)
    expected = independent_frontier(values)
    assert stats['complete_plans_traced']==162
    for policy in POLICIES.values():
        (root,_),_ = observe(graph,model,policy)
        assert {d.vector for d in root}==expected


def test_instrumentation_restores_descriptors_and_functions_after_failure():
    original = engine.summarize
    descriptor = inspect.getattr_static(engine.StageCatalog,'build')
    def fail(*args,**kwargs):
        raise ValueError('test local evaluation failed')
    with patch.object(engine,'summarize',fail):
        with pytest.raises(ValueError,match='test local evaluation failed'):
            observe(TwoMM(1,1,1,1),CostModel(),engine.SearchPolicy())
        assert engine.summarize is fail
        assert inspect.getattr_static(engine.StageCatalog,'build') is descriptor
        assert not WorkObservation._active
    assert engine.summarize is original
    observe(TwoMM(1,1,1,1),CostModel(),engine.SearchPolicy())


def test_reject_nested_or_reused_context_without_disturbing_outer_observer():
    original = engine.summarize
    observation = WorkObservation()
    with observation:
        wrapped = engine.summarize
        with pytest.raises(RuntimeError,match='fresh serial'):
            with WorkObservation():
                pass
        assert engine.summarize is wrapped and WorkObservation._active
    assert engine.summarize is original and not WorkObservation._active
    with pytest.raises(RuntimeError,match='fresh serial'):
        with observation:
            pass
