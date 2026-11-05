"""No-local-pruning control, scalar execution, and order/budget metamorphisms."""
from random import Random

import pytest

from research.joint_synthesis.graph_ir import TwoMM, CostModel
from research.joint_synthesis.graph_dp import solve
from research.joint_synthesis.exhaustive_oracle import exhaustive
from research.joint_synthesis.validate import independent_frontier
from research.joint_synthesis.hardware_ir import GridAxis, HardwareEnvelope, NormalizedPrices
from research.joint_synthesis.architecture_synth import synthesize
from research.joint_synthesis.validate_architecture import validate_configuration


def cases():
    rng=Random(20261108)
    for i in range(4):
        yield TwoMM(*(rng.randint(1,3)for _ in range(4))),CostModel(*(rng.randint(1,9)for _ in range(4)))


@pytest.mark.parametrize('graph,model',list(cases()))
def test_no_local_pruning_pruned_dp_and_scalar_grammar_have_same_joint_frontier(graph,model):
    reference,raw_stats=solve(graph,model,local_pruning=False,layout_pruning=False)
    actual,stats=solve(graph,model)
    observations,_=exhaustive(graph,model)
    expected=independent_frontier(observations)
    assert {d.vector for d in reference}=={d.vector for d in actual}==expected
    assert raw_stats['materialized_complete_pairs']==raw_stats['raw_complete_pairs']
    assert stats['materialized_complete_pairs']<raw_stats['materialized_complete_pairs']
    grid=HardwareEnvelope(GridAxis(1,3),GridAxis(1,3),GridAxis(4,32,4),GridAxis(1,3))
    checked=validate_configuration(actual,observations,model,grid,NormalizedPrices(),64)
    assert checked['exact_full_joint_frontier_equal'] and checked['all_budget_et_frontiers_equal']


def test_candidate_interface_pair_and_hardware_order_do_not_change_numeric_results():
    graph=TwoMM(2,2,2,2);model=CostModel(2,3,7,5)
    root,_=solve(graph,model)
    grid=HardwareEnvelope(GridAxis(1,3),GridAxis(1,3),GridAxis(4,32,4),GridAxis(1,5))
    expected,_=synthesize(root,grid,budget_ceiling=64)
    for seed in (1,7,29):
        shuffled,_=solve(graph,model,order_seed=seed)
        assert {d.vector for d in shuffled}=={d.vector for d in root}
        Random(seed).shuffle(shuffled)
        family,_=synthesize(shuffled,grid,budget_ceiling=64)
        assert {d.vector for d in family.designs}=={d.vector for d in expected.designs}
        previous=None
        for budget in range(65):
            assert {(d.energy,d.latency)for d in family.query_budget(budget)}=={
                (d.energy,d.latency)for d in expected.query_budget(budget)}
            best=family.best_edp(budget)
            if previous is not None:assert best is not None and best.edp<=previous
            if best is not None:previous=best.edp
