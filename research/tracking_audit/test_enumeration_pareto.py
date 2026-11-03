import importlib

import numpy as np
import pytest

from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.enumeration_pareto import EnumerationParetoCache
from accelforge.mapper.FFM._pareto_df import pareto

tiles = importlib.import_module(
    'accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')


def test_exact_masks_preserve_ties_goals_dtype_and_row_order():
    cache = EnumerationParetoCache(2**20)
    matrix = np.array([[1, 3, 0], [2, 2, 0], [1, 3, 0], [4, 4, 0], [5, 5, 1]], dtype=np.float64)
    requests = [(matrix, ['min', 'min', 'diff']),
                (matrix[::-1], ['min', 'min', 'diff']),
                (matrix, ['max', 'min', 'diff']),
                (matrix.astype(np.float32), ['min', 'min', 'diff']),
                (np.array([[1, 2], [2, 4], [3, 3], [6, 1.]]), ['min_per_prime_factor', 'max'])]
    for data, goals in requests:
        expected = pareto.makepareto_numpy(data, goals, dirty=True)
        for _ in range(2):
            mask = cache.prune(data, goals, 0., lambda: pareto.makepareto_numpy(data, goals, dirty=True))
            np.testing.assert_array_equal(mask, expected)
        with pytest.raises(ValueError):
            mask[0] = not mask[0]
    assert cache.stats['computations'] == len(requests)
    assert cache.stats['hits'] == len(requests)


@pytest.mark.parametrize('budget', [0, 1, 50, 2**20])
def test_mask_eviction_and_changed_inputs_do_not_leak_results(budget):
    cache = EnumerationParetoCache(budget)
    for values in ([[1., 3.], [2., 2.]], [[3., 3.], [2., 2.]], [[1., 3.], [2., 2.]]):
        matrix = np.array(values)
        original = matrix.copy()
        expected = pareto.makepareto_numpy(matrix, ['min', 'min'], dirty=True)
        actual = cache.prune(matrix, ['min', 'min'], 0., lambda: pareto.makepareto_numpy(matrix, ['min', 'min'], dirty=True))
        np.testing.assert_array_equal(expected, actual)
        np.testing.assert_array_equal(matrix, original)
    assert cache.stats['peak_payload_bytes'] <= budget
    if budget == 50:
        assert cache.stats['evictions'] == 2


def test_approximate_and_nonfinite_requests_bypass_cache(monkeypatch):
    cache = EnumerationParetoCache(2**20)
    for tol in (.1, .2):
        monkeypatch.setattr(pareto, 'TOLERANCE', tol)
        matrix = np.array([[1., 1.01], [1.01, 1.]])
        expected = pareto.makepareto_numpy(matrix, ['min', 'min'], dirty=True)
        for _ in range(2):
            result = cache.prune(matrix, ['min', 'min'], tol,
                                lambda: pareto.makepareto_numpy(matrix, ['min', 'min'], dirty=True))
            np.testing.assert_array_equal(expected, result)
    for dtype in (float, object):
        matrix = np.array([[np.nan]], dtype=dtype)
        for _ in range(2):
            cache.prune(matrix, ['min'], 0., lambda: np.ones(1, dtype=bool))
    assert cache.stats['hits'] == 0 and cache.stats['payload_bytes'] == 0


def test_target_tile_sets_and_membership_match_with_shared_pareto(monkeypatch):
    from test_enumeration_prefix import problem, job
    for minimum in (0., 1., 2.):
        objectives, memory, args = problem(360, minimum)
        targets = [(memory, t) for t in (1., .125, .5, .125)]
        monkeypatch.setenv('AF_ENUMERATION_PARETO_BYTES', '0')
        expected = tiles.get_tile_shape_choices_for_targets(objectives, targets, job=job(), **args)
        for budget in (128, 8 * 2**20):
            monkeypatch.setenv('AF_ENUMERATION_PARETO_BYTES', str(budget))
            shared_job = job()
            result = tiles.get_tile_shape_choices_for_targets(objectives, targets, job=shared_job, **args)
            np.testing.assert_array_equal(result[0], expected[0])
            np.testing.assert_array_equal(result[1], expected[1])
            assert shared_job.enumeration_pareto_stats['peak_payload_bytes'] <= budget


def test_real_glu_templates_match_without_either_execution_cache(monkeypatch):
    import copy
    import common
    original = tiles.get_tile_shape_choices_for_targets
    comparisons = []

    def check(objectives, capacity_targets, **kwargs):
        reference_job = copy.copy(kwargs['job'])
        reference_job.messages = []
        reference_job.pmapping_keep_rates = dict(kwargs['job'].pmapping_keep_rates)
        result = original(objectives, capacity_targets, **kwargs)
        if capacity_targets:
            with monkeypatch.context() as m:
                m.setenv('AF_ENUMERATION_PREFIX_BYTES', '0')
                m.setenv('AF_ENUMERATION_PARETO_BYTES', '0')
                expected = original(objectives, capacity_targets, **{**kwargs, 'job': reference_job})
            np.testing.assert_array_equal(result[0], expected[0])
            np.testing.assert_array_equal(result[1], expected[1])
            comparisons.append(True)
        return result

    monkeypatch.setattr(tiles, 'get_tile_shape_choices_for_targets', check)
    common.af.set_n_parallel_jobs(1)
    case = common.Case('glu', 'nvdla', (8, 16, 32))
    caps = [128 / 2**20, 256 / 2**20, 1024 / 2**20]
    common.search(common.build(case, max(caps), common.RU),
                  {**common.capacity_fractions_env(caps), 'AF_GENERATION_VARIABLE_RESOURCES': 'GlobalBuffer',
                   'AF_ENUMERATION_PARETO_BYTES': str(8 * 2**20)},
                  {'AF_VARIABLE_RESOURCES': 'GlobalBuffer'})
    assert comparisons
