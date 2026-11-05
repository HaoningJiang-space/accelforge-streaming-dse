"""Check the elimination law against native transfer, rounding and real FFM."""
from copy import deepcopy
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from accelforge.mapper.FFM._join_pmappings.compatibility import Compatibility
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from accelforge.util import fzs
from research.graph_coopt.conditional_elimination import candidate_mask, strict_addition_guard
from research.graph_coopt.resource_effect import (
    UnsupportedEffect, compile_effects, covered, evaluate, normalize,
)
from research.graph_coopt.audit_conditional_elimination import audit
from research.tracking_audit import common


GB = 'reservation<SEP>GlobalBuffer<SEP>'
E, T = 'Total<SEP>energy', 'Total<SEP>latency'


@pytest.fixture(autouse=True)
def reference_environment():
    common.clear_switches()
    yield
    common.clear_switches()


def operands(peaks=(640, 576), active=(512, 768), energy=(1e-9, 2e-9), rhs=(0, 256)):
    left = pd.DataFrame({
        'resource_capacity_bits<SEP>GlobalBuffer': [10000] * len(peaks),
        GB + '0<SEP>left': peaks, GB + '0<SEP>right': [0] * len(peaks),
        GB + '1<SEP>left': active,
        E: np.array(energy, dtype=np.float32), T: np.full(len(peaks), 1e-8, dtype=np.float32),
        'tensor<SEP>dead': np.arange(len(peaks)),
        'A<SEP>compressed_index': np.arange(len(peaks)),
    })
    right = pd.DataFrame({
        'resource_capacity_bits<SEP>GlobalBuffer': [10000] * len(rhs),
        GB + '0<SEP>right': rhs, GB + '1<SEP>right': [x + 10 for x in rhs],
        E: np.full(len(rhs), 3e-9, dtype=np.float32), T: np.full(len(rhs), 1e-8, dtype=np.float32),
        'B<SEP>compressed_index': np.arange(len(rhs)),
    })
    pdf = lambda frame: PmappingDataframe(frame, len(frame), len(frame), skip_pareto=True)
    plan = dict(left_match=[], right_match=[], shared_tensors=[], make_empty_result=False,
                shared_to_free=[], live_to_alloc=[], remaining_symbols=set(), max_nloops=1, min_nloops=0,
                column_schema=None, column_operations=None, right_dropcols=None, numeric_program=None)
    return pdf(left), pdf(right), plan


def test_resource_vector_tradeoff_can_have_uniform_effect_dominance():
    left, right, plan = operands()
    _, coordinate = candidate_mask(left, right, plan, mode='coordinates')
    assert coordinate['rows_after'] == 2
    mask, effect = candidate_mask(left, right, plan, mode='effect')
    assert mask.tolist() == [True, False]
    assert effect['rows_after'] == 1
    assert effect['dropped_dead_tensor_columns'] == ['tensor<SEP>dead']
    assert not effect['target_optimum_used'] and not effect['suffix_completion_oracle_used']


def test_max_plus_cover_proves_all_nonnegative_bindings_not_sampled_points():
    # max(640,512+x) <= max(576,768+x) for every x>=0.
    a = normalize([((0,), 640), ((1,), 512)])
    b = normalize([((0,), 576), ((1,), 768)])
    assert covered(a, b)
    assert not covered(b, a)
    for x in range(2049):
        assert evaluate(a, (x,)) <= evaluate(b, (x,))


def test_shadow_matches_native_column_arithmetic_before_pareto():
    rng = np.random.default_rng(52)
    peaks, active = rng.integers(0, 1000, (2, 12))
    rhs = rng.integers(0, 1000, 13)
    left, right, plan = operands(peaks, active, np.linspace(1e-9, 2e-9, 12), rhs)
    variables, profiles = compile_effects(left, right, plan)
    empty = Compatibility(fzs())
    # Test-only: expose every composed row rather than only its Pareto subset.
    with patch.object(PmappingDataframe, 'make_pareto', lambda *args, **kwargs: None):
        result = left.merge_next(right, 0, -1, set(), [], set(), empty, empty, empty,
                                 ignored_resources=set(), drop_valid_reservations=False,
                                 _prepared_join_plan=deepcopy(plan))
    assert len(result.data) == len(peaks) * len(rhs)
    for i in range(len(result.data)):
        p = int(result.data['A<SEP>compressed_index'].iloc[i])
        r = int(result.data['B<SEP>compressed_index'].iloc[i])
        values = tuple(int(right.data[c].iloc[r]) for c in variables)
        for c, expression in profiles[p].items():
            assert evaluate(expression, values) == result.data[c].iloc[i]


def test_elimination_keeps_distinct_requirements_and_small_cost_ties():
    left, right, plan = operands(energy=(1e-9, np.nextafter(np.float32(1e-9), np.float32(np.inf))))
    assert candidate_mask(left, right, plan, mode='effect')[0].all()
    left, right, plan = operands()
    left.data['fused_loop<SEP>required'] = [1, 2]
    right.data['fused_loop<SEP>other'] = [1, 2]
    plan.update(left_match=['fused_loop<SEP>required'], right_match=['fused_loop<SEP>other'])
    assert candidate_mask(left, right, plan, mode='effect')[0].all()


def test_float_guard_protects_strictness_for_bounded_native_addition():
    rng = np.random.default_rng(18)
    for p, q, r in rng.uniform(1e-10, 1e-7, (1000, 3)):
        p, q = sorted((np.float32(p), np.float32(q)))
        if strict_addition_guard(float(p), float(q), float(r)):
            assert np.float32(p + np.float32(r)) < np.float32(q + np.float32(r))
    assert not strict_addition_guard(1e-9, 2e-9, 1e12)


def test_unknown_arithmetic_or_budget_does_not_remove_candidates():
    left, right, plan = operands()
    plan['shared_to_free'] = ['uncompiled tensor']
    mask, report = candidate_mask(left, right, plan, mode='effect')
    assert mask.all() and report['status'] == 'unknown'
    left, right, plan = operands()
    assert candidate_mask(left, right, plan, max_rows=1)[0].all()
    left.data['reservation<SEP>Legacy<SEP>0<SEP>right'] = 0.5
    assert candidate_mask(left, right, plan, mode='effect')[0].all()
    with pytest.raises(UnsupportedEffect):
        normalize([((i, 129-i), 0) for i in range(129)])


def test_reduction_does_not_hide_invalid_resource_units_or_fractional_bits():
    for mode in ('coordinates', 'live_coordinates', 'effect'):
        left, right, plan = operands()
        right.data['resource_capacity_bits<SEP>GlobalBuffer'] = 9999
        mask, report = candidate_mask(left, right, plan, mode=mode)
        assert mask.all() and report['reason'] == 'invalid_exact_resource_contract'
        left, right, plan = operands()
        left.data[GB + '1<SEP>left'] = [512.0, 768.5]
        mask, report = candidate_mask(left, right, plan, mode=mode)
        assert mask.all() and report['reason'] == 'invalid_exact_resource_contract'


def test_real_conditional_elimination_without_completion_oracle():
    result = audit(3, 4, 8, (4, 8), 128)
    effect = result['variants']['effect']
    assert effect['work']['materialized_pairs'] < result['native']['materialized_pairs']
    assert effect['full_numeric_frontier_equal'] and effect['full_mapping_sources_equal']
    assert result['native_transfer_validation']['checked_rows'] > 0
    assert not result['native_transfer_validation']['unknown']
    assert not result['target_optimum_used'] and not result['completion_response_oracle_used']
    assert not result['candidate_generation_avoided'] and not result['cross_architecture_rule_established']
