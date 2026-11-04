"""Permutation chosen for structural Join must also choose numeric match keys."""
import importlib

import pytest

from research.tracking_audit import common
from research.tracking_audit.audit_attention_actions import numbers
from research.tracking_audit.shape_capacity_audit import build, rows_fitting, validate_pick


@pytest.fixture(scope='module')
def attention():
    from accelforge.util import get_n_parallel_jobs
    previous = get_n_parallel_jobs()
    common.af.set_n_parallel_jobs(1)
    case = common.Case('attention', 'nvdla', (128,1,64))
    metrics = common.RU | common.af.Metrics.ACTIONS
    spec = build(case, (64,96), 131072, metrics)
    result, _ = common.search(spec, join_env={'AF_VARIABLE_RESOURCES':'GlobalBuffer'})
    yield case, metrics, result
    common.af.set_n_parallel_jobs(previous)


@pytest.mark.parametrize('capacity', [8192,24576])
def test_attention_cost_and_all_tensor_actions_match_reconstruction(attention, capacity):
    case, metrics, result = attention
    row = common.best_row(rows_fitting(result.data, capacity))
    assert validate_pick(case, (64,96), capacity, row)['ok']
    target = build(case, (64,96), capacity, metrics)
    target.model.metrics = metrics
    target.mapping = row['Total<SEP>mapping']()
    evaluated = common.evaluate_mapping(target).data.iloc[0]
    reported_actions = {c:v for c,v in numbers(row).items() if 'action<SEP>' in c and v != 0}
    evaluated_actions = {c:v for c,v in numbers(evaluated).items() if 'action<SEP>' in c and v != 0}
    assert reported_actions
    assert reported_actions == evaluated_actions


def test_selected_compatibility_does_not_mutate_other_join_tasks():
    from types import SimpleNamespace
    module = importlib.import_module('accelforge.mapper.FFM._join_pmappings.join_pmappings')
    old = SimpleNamespace(tensors=())
    reservation = SimpleNamespace(name='X')
    new = SimpleNamespace(tensors=[reservation])
    group = SimpleNamespace(compatibility=old, tensors={'dead':'retained'}, mappings=object())
    changed = module._with_compatibility(group, new)
    assert group.compatibility is old and group.tensors == {'dead':'retained'}
    assert changed.compatibility is new
    assert changed.tensors == {'dead':'retained', 'X':reservation}
    assert changed.mappings is group.mappings
