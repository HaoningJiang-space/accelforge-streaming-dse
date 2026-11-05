"""Budget, baseline and model contracts for the architecture/mapping RQ1 audit."""
import math

import pytest

from research.graph_coopt.architecture_mapping_coupling import (
    Point, budget_comparisons, evaluate_frozen, make_spec,
    search_point, switch_observations,
)
from research.graph_coopt.workload_dag import WorkloadDAG
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, validate_pick


def record(shape, edp, cap=4096, scale=1.):
    point = Point(*shape, cap, scale)
    return dict(key=point.key, point=dict(px=shape[0], py=shape[1], capacity_bytes=cap,
                                         gb_latency_scale=scale),
                budget=list(point.budget), edp=edp)


def test_complete_architecture_enumeration_is_the_joint_reference():
    records = [record(shape, cost) for shape, cost in zip(((8, 32), (16, 16), (32, 8)), (6., 10., 12.))]
    frozen = {r['key']: dict(feasible=False) for r in records}
    result = budget_comparisons(records, frozen, (16, 16))[0]
    assert result['reference_edp'] == 6.
    assert math.isclose(result['fixed_nominal_shape']['relative_edp_gap'], 10 / 6 - 1)
    assert not result['grid_reference_globally_optimal_claimed']


def test_different_sram_and_bandwidth_budgets_are_not_free_architecture_choices():
    records = [record(shape, cost, cap, scale)
               for cap, scale, costs in ((4096, 1., (6., 10., 12.)),
                                         (8192, 1., (3., 1., 2.)),
                                         (4096, 4., (20., 19., 10.)))
               for shape, cost in zip(((8, 32), (16, 16), (32, 8)), costs)]
    frozen = {r['key']: dict(feasible=False) for r in records}
    results = budget_comparisons(records, frozen, (16, 16))
    assert len(results) == 3
    assert {r['reference_edp'] for r in results} == {6., 1., 10.}
    assert all(r['budget']['pe_count'] == 256 for r in results)


def test_infeasible_frozen_mapping_has_no_numeric_regret():
    records = [record(shape, cost) for shape, cost in zip(((8, 32), (16, 16), (32, 8)), (6., 10., 12.))]
    result = budget_comparisons(records, {r['key']: dict(feasible=False) for r in records}, (16, 16))[0]
    assert result['fixed_anchor_mapping']['feasible_shapes'] == 0
    assert result['fixed_anchor_mapping']['relative_edp_gap'] is None


def test_a_legal_transfer_better_than_the_heuristic_grid_is_not_clamped():
    records = [record(shape, cost) for shape, cost in zip(((8, 32), (16, 16), (32, 8)), (6., 10., 12.))]
    frozen = {r['key']: dict(feasible=True, edp=3.) for r in records}
    result = budget_comparisons(records, frozen, (16, 16))[0]
    assert result['fixed_anchor_mapping']['relative_edp_gap'] == -.5
    assert result['best_known_edp'] == 3.


def test_selected_mapping_id_change_is_not_a_proven_optimum_set_change():
    a, b = record((16, 16), 1., 4096), record((16, 16), 1., 8192)
    for r, identity, tied in ((a, 'a', ['a', 'b']), (b, 'b', ['b', 'c'])):
        r.update(mapping_id=identity, tied_mapping_ids=tied, tied_set_complete=True, gb_bits=32,
                 graph=dict(signature=identity, intermediate_storage_components={}))
    change = switch_observations([a, b])[0]
    assert change['selected_mapping_changed']
    assert not change['complete_tied_sets_disjoint']
    b['tied_set_complete'] = False
    assert switch_observations([a, b])[0]['complete_tied_sets_disjoint'] is None


def test_builder_and_resource_point_validate_bandwidth_and_exact_bytes():
    case = common.Case('matmuls', 'nvdla', (2, 4, 8))
    assert build(case, (16, 16), 1024, common.RU, 4.).arch.find('GlobalBuffer').latency_scale == 4.
    for scale in (0., -1., math.inf, math.nan):
        with pytest.raises(ValueError):
            Point(16, 16, 1024, scale)
        with pytest.raises(ValueError):
            build(case, (16, 16), 1024, common.RU, scale)
    with pytest.raises(ValueError):
        Point(16, 16, 1024.5, 1.)


def test_real_bandwidth_query_uses_the_target_model_and_preserves_frozen_decisions():
    common.clear_switches()
    common.af.set_n_parallel_jobs(1)
    case = common.Case('matmuls', 'nvdla', (2, 8, 16))
    point = Point(16, 16, 1024, 4096.)
    dag = WorkloadDAG.from_workload(make_spec(case, point).workload)
    result, mapping = search_point(case, point, dag)
    assert result['validation']['ok']
    assert 'T1' in result['graph']['intermediate_storage_components']
    assert not result['graph']['lifetime_sufficiency_proven']
    transferred = evaluate_frozen(case, Point(16, 16, 1024, 1.), mapping, result)
    assert transferred['feasible']
    assert transferred['mapping_id'] == result['mapping_id']
    assert transferred['latency'] < result['latency']
    assert math.isclose(transferred['energy'], result['energy'], rel_tol=1e-6)
    too_small = evaluate_frozen(case, Point(1, 1, 1024, 1.), mapping, result)
    assert not too_small['feasible'] and too_small['reason'] == 'spatial_binding_does_not_fit'
    # The existing validator must reject costs from another bandwidth if its
    # new optional bandwidth argument is accidentally omitted.
    fake_row = {'Total<SEP>mapping': lambda: mapping, 'Total<SEP>energy': result['energy'],
                'Total<SEP>latency': result['latency']}
    with pytest.raises(ValueError, match='reconstruction_cost_mismatch'):
        validate_pick(case, point.shape, point.capacity_bytes, fake_row)
