"""Exact target membership must survive sharing, eviction and target reordering."""
import importlib
from types import SimpleNamespace

import numpy as np
import pytest
from sympy import Symbol

tiles = importlib.import_module(
    'accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')
Cache = tiles.EnumerationPrefixCache


def job():
    return SimpleNamespace(
        spec=SimpleNamespace(mapper=SimpleNamespace(ffm=SimpleNamespace(
            _count_option_for_mapsapce_size_evaluation=()))),
        n_total_pmappings=1, n_evaluated_pmappings=0, pmapping_keep_rates={},
        log_message=lambda *a: None, log_porp_pmappings_kept=lambda *a: None)


def problem(bound=360, usage_min=1.):
    x, y, z = [Symbol(s, integer=True, positive=True) for s in ('px', 'py', 'pz')]
    relations = tiles.SymbolRelations()
    relations.what_tiles_symbol = [(bound, x), (x, y), (y, 1), (bound, z), (z, 1)]
    relations.make_bounds()
    memory = (x * z + y) / (bound * bound + bound)
    objectives = [tiles.Objective('memory', memory, max_value=1),
                  tiles.Objective('usage_a', y / x, min_value=usage_min,
                                  try_best_if_none_reaches_min=True, only_care_if_valid=True),
                  tiles.Objective('usage_b', 1 / z, min_value=usage_min,
                                  try_best_if_none_reaches_min=True, only_care_if_valid=True)]
    return objectives, memory, dict(symbols=[x, y, z], what_tiles_symbol=relations)


@pytest.mark.parametrize('budget', [0, 128, 8 * 2**20])
@pytest.mark.parametrize('usage_min', [0., 1., 2.])
def test_matches_each_independent_target_with_two_fallbacks(monkeypatch, budget, usage_min):
    monkeypatch.setenv('AF_ENUMERATION_PREFIX_BYTES', str(budget))
    objectives, memory, args = problem(360, usage_min)
    # Includes an empty target, repeated targets, and reversed capacity order.
    targets = [1., .125, 1e-9, .5, .125]
    shared_job = job()
    choices, excluded = tiles.get_tile_shape_choices_for_targets(
        objectives, [(memory, b) for b in targets], job=shared_job, **args)
    for k, bound in enumerate(targets):
        target = tiles.Objective('capacity', memory, max_value=bound, only_care_if_valid=True)
        expected = tiles.get_tile_shape_choices(
            objectives[:1] + [target] + objectives[1:], job=job(), **args)
        np.testing.assert_array_equal(choices[~excluded[:, k]], np.unique(expected, axis=0))
    assert shared_job.enumeration_stats['peak_payload_bytes'] <= budget
    if budget == 8 * 2**20:
        assert shared_job.enumeration_stats['hits'] > 0
        assert shared_job.enumeration_stats['expanded_rows'] < shared_job.enumeration_stats['requested_rows']


@pytest.mark.parametrize('targets', [2, 4, 8, 16, 32, 64])
def test_non_nested_fallback_coverage_and_shared_expansion_count(monkeypatch, targets):
    from test_min_usage import enumerate_with_memory
    monkeypatch.setenv('AF_ENUMERATION_PREFIX_BYTES', str(2**20))
    fractions = np.linspace(.25, 1, targets)
    union, per_target = enumerate_with_memory(4, targets=fractions, usages=((1, 2), (1, 0)))
    expected = [enumerate_with_memory(4 * f, usages=((1, 2), (1, 0))) for f in fractions]
    assert per_target == expected
    assert union == set.union(*expected)


def test_cache_preserves_order_dtype_and_returns_immutable_results():
    cache = Cache(4096)
    original = np.array([[1, 2], [3, 4]], dtype=np.int64)
    calls = []
    def expand(prefix):
        calls.append(1)
        return np.column_stack((prefix, np.ones(len(prefix), dtype=prefix.dtype)))
    first = cache.expand('z', ('x', 'y'), original, lambda: expand(original))
    second = cache.expand('z', ('x', 'y'), original.copy(), lambda: expand(original))
    assert second is first and len(calls) == 1
    with pytest.raises(ValueError):
        second[0, 0] = 7
    for prefix in (original[::-1], original.astype(np.float64), original + 1):
        result = cache.expand('z', ('x', 'y'), prefix, lambda: expand(prefix))
        np.testing.assert_array_equal(result[:, :2], prefix)
        assert result.dtype == prefix.dtype
    cache.expand('z', ('y', 'x'), original, lambda: expand(original))
    assert len(calls) == 5


def test_eviction_and_oversize_bypass_do_not_change_results():
    cache = Cache(80)
    for i in (1, 2, 1):
        prefix = np.array([[i]], dtype=np.int64)
        expected = np.full((4, 2), i, dtype=np.int64)
        result = cache.expand('y', ('x',), prefix, lambda: expected.copy())
        np.testing.assert_array_equal(result, expected)
    assert cache.stats['hits'] == 0 and cache.stats['evictions'] == 2
    prefix = np.zeros((100, 2), dtype=np.int64)
    result = cache.expand('y', ('x',), prefix, lambda: prefix.copy())
    assert result.flags.writeable
    assert cache.stats['peak_payload_bytes'] <= 80


def test_bad_budget_rejected():
    with pytest.raises(ValueError, match='nonnegative'):
        Cache(-1)


def test_initial_tile_shape_uses_existing_stride_relation(monkeypatch):
    monkeypatch.setenv('AF_ENUMERATION_PREFIX_BYTES', '4096')
    stride = Symbol('residual_stride', positive=True, integer=True)
    initial = Symbol('residual_initial', positive=True, integer=True)
    relations = tiles.SymbolRelations()
    relations.what_tiles_symbol = [(8, stride), (stride, 1)]
    relations.tile_shape_and_initial = [(stride, initial)]
    relations.delta_choices = [(initial, frozenset({0, 1}))]
    relations.make_bounds()
    # This path previously called a nonexistent SymbolRelations.get_stride().
    choices, excluded = tiles.get_tile_shape_choices_for_targets(
        [], [(stride / 8, .5), (stride / 8, 1.)], symbols=[stride, initial],
        what_tiles_symbol=relations, job=job(), keep_symbols=[stride, initial])
    np.testing.assert_array_equal(choices, [[1, 1], [1, 2], [2, 2], [2, 3],
                                          [4, 4], [4, 5], [8, 8]])
    np.testing.assert_array_equal(excluded[:, 0], [False] * 6 + [True])
    assert not excluded[:, 1].any()


def test_real_glu_templates_match_reference_choices_and_membership(monkeypatch):
    import copy
    import common
    calls = []
    original = tiles.get_tile_shape_choices_for_targets

    def audited(objectives, capacity_targets, **kwargs):
        targets = capacity_targets
        reference_job = copy.copy(kwargs['job'])
        reference_job.messages = []
        reference_job.pmapping_keep_rates = dict(kwargs['job'].pmapping_keep_rates)
        result = original(objectives, targets, **kwargs)
        if targets:
            with monkeypatch.context() as m:
                m.setenv('AF_ENUMERATION_PREFIX_BYTES', '0')
                expected = original(objectives, targets, **{**kwargs, 'job': reference_job})
            np.testing.assert_array_equal(result[0], expected[0])
            np.testing.assert_array_equal(result[1], expected[1])
            calls.append(kwargs['job'].enumeration_stats)
        return result

    monkeypatch.setattr(tiles, 'get_tile_shape_choices_for_targets', audited)
    common.af.set_n_parallel_jobs(1)
    caps = [128 / 2**20, 256 / 2**20, 1024 / 2**20]
    case = common.Case('glu', 'nvdla', (8, 16, 32))
    common.search(common.build(case, max(caps), common.RU),
                  {**common.capacity_fractions_env(caps),
                   'AF_GENERATION_VARIABLE_RESOURCES': 'GlobalBuffer',
                   'AF_ENUMERATION_PREFIX_BYTES': str(2**20)},
                  {'AF_VARIABLE_RESOURCES': 'GlobalBuffer'})
    assert calls and sum(s['hits'] for s in calls) > 0
