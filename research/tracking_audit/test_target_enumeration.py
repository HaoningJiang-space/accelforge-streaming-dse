"""Capacity-event search must exactly reproduce each target's ordered history."""
import copy
import importlib

import numpy as np
import pytest
import sympy

from test_enumeration_prefix import job, problem
from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.target_enumeration import (
    Cohort, capacity_events, merge_cohorts,
)

tiles = importlib.import_module(
    'accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')


def oracle(objectives, targets, args):
    first_min = next((i for i, o in enumerate(objectives) if o.try_best_if_none_reaches_min), len(objectives))
    results = []
    for formula, bound in targets:
        extra = tiles.Objective('capacity', formula, max_value=bound, only_care_if_valid=True)
        results.append(np.unique(tiles.get_tile_shape_choices(
            objectives[:first_min] + [extra] + objectives[first_min:], job=job(), **args), axis=0))
    return results


def check_targets(objectives, targets, args, monkeypatch):
    expected = oracle(objectives, targets, args)
    monkeypatch.setenv('AF_TARGET_ENUMERATION', 'events')
    j = job()
    choices, excluded = tiles.get_tile_shape_choices_for_targets(objectives, targets, job=j, **args)
    expected_union = np.unique(np.concatenate(expected), axis=0)
    assert choices.dtype == expected_union.dtype
    np.testing.assert_array_equal(choices, expected_union)
    for i, plain in enumerate(expected):
        np.testing.assert_array_equal(choices[~excluded[:, i]], plain)
    return j.target_enumeration_stats


def test_exhausted_target_preserves_union_dtype_promotion(monkeypatch):
    tile = sympy.Symbol('dtype_tile', positive=True, integer=True)
    relations = tiles.SymbolRelations()
    relations.what_tiles_symbol = [(4, tile), (tile, 1)]
    relations.make_bounds()
    args = dict(symbols=[tile], what_tiles_symbol=relations, keep_symbols=[tile])
    monkeypatch.setenv('AF_TARGET_ENUMERATION', 'events')
    for bounds, dtype in [((.25, 1.), np.int64), ((.01, 1.), np.float64), ((.001, .01), np.float64)]:
        choices, _ = tiles.get_tile_shape_choices_for_targets(
            [], [(tile / 4, b) for b in bounds], job=job(), **args)
        assert choices.dtype == dtype


@pytest.mark.parametrize('minimum', [0., 1., 2.])
@pytest.mark.parametrize('fallbacks', [1, 2])
def test_single_and_ordered_fallbacks_match_each_target(monkeypatch, minimum, fallbacks):
    objectives, memory, args = problem(360, minimum)
    targets = [(memory, b) for b in (1., .125, 1e-9, .5, .125, .99)]
    stats = check_targets(objectives[:1 + fallbacks], targets, args, monkeypatch)
    assert stats['supported'] == 1
    assert stats['state_expansions'] < stats['target_expansions']
    assert stats['expanded_rows'] < stats['target_expanded_rows']
    assert stats['value_evaluations'] < stats['target_value_evaluations']


@pytest.mark.parametrize('k', [2, 4, 8, 16, 32, 64])
def test_non_nested_history_does_not_take_union_between_fallbacks(monkeypatch, k):
    from test_min_usage import enumerate_with_memory
    monkeypatch.setenv('AF_TARGET_ENUMERATION', 'events')
    fractions = np.linspace(.25, 1, k)
    union, actual = enumerate_with_memory(4, targets=fractions, usages=((1, 2), (1, 0)))
    expected = [enumerate_with_memory(4 * f, usages=((1, 2), (1, 0))) for f in fractions]
    assert actual == expected
    assert union == set.union(*expected)


@pytest.mark.parametrize('dtype', [np.float32, np.float64])
def test_capacity_events_preserve_threshold_rounding_and_input_order(dtype):
    values = np.array([.5, .25, .5, .75, 1.], dtype=dtype)
    bounds = [float(.5 - 1 / 2**27), np.float64(.5 - 1 / 2**27), .5,
              .25, 1., 0., np.nan, np.inf, sympy.Rational(1, 2)]
    parts = capacity_events(values, tuple(range(len(bounds))), bounds)
    seen = []
    for targets, mask in parts:
        for target in targets:
            np.testing.assert_array_equal(mask, values <= bounds[target])
            seen.append(target)
    assert sorted(seen) == list(range(len(bounds)))
    # Also exercise the sorted-event fast path without SymPy/NaN fallbacks.
    for targets, mask in capacity_events(values, tuple(range(6)), bounds):
        for target in targets:
            np.testing.assert_array_equal(mask, values <= bounds[target])


@pytest.mark.parametrize('values', [0.5000000001, np.float32(.5),
                                  np.array([2**60, 2**60 + 1], dtype=np.int64),
                                  np.array([np.nan, np.inf, .5])])
def test_event_fallback_matches_scalar_and_nonfinite_comparisons(values):
    bounds = [np.float32(.5), .5, np.float64(.5), 2**60]
    for targets, mask in capacity_events(values, tuple(range(4)), bounds):
        for target in targets:
            np.testing.assert_array_equal(mask, values <= bounds[target])


def test_an_unsupported_threshold_does_not_disable_other_targets():
    values = np.array([.25, .5, 1.], dtype=np.float32)
    bounds = [.25, 'unsupported', 1.]
    expected = [[True, False, False], [True, True, True], [True, True, True]]
    for targets, mask in capacity_events(values, (0, 1, 2), bounds):
        for target in targets:
            np.testing.assert_array_equal(mask, expected[target])


def test_initial_shapes_and_fused_loop_limits(monkeypatch):
    stride = sympy.Symbol('event_stride', positive=True, integer=True)
    initial = sympy.Symbol('event_initial', positive=True, integer=True)
    relations = tiles.SymbolRelations()
    relations.what_tiles_symbol = [(8, stride), (stride, 1)]
    relations.tile_shape_and_initial = [(stride, initial)]
    relations.delta_choices = [(initial, frozenset({0, 1}))]
    relations.make_bounds()
    args = dict(symbols=[stride, initial], what_tiles_symbol=relations,
                keep_symbols=[stride, initial], max_loop_check_groups=[(0, [stride])])
    check_targets([], [(stride / 8, .5), (stride / 8, 1.)], args, monkeypatch)


def test_merging_requires_same_row_order_dtype_and_pareto_history():
    values = np.array([[1, 2], [2, 1]], dtype=np.int64)
    history = (frozenset({('x', 'min')}),)
    states = [Cohort(values, (0,), history), Cohort(values.copy(), (1,), history),
              Cohort(values[::-1], (2,), history), Cohort(values.astype(float), (3,), history),
              Cohort(values, (4,), ())]
    stats = {'state_merges': 0}
    merged = merge_cohorts(states, stats)
    assert len(merged) == 4 and merged[0].targets == (0, 1)
    assert stats['state_merges'] == 1


@pytest.mark.parametrize('seed', [7, 813, 2603])
def test_deterministic_small_space_fuzz(monkeypatch, seed):
    rng = np.random.default_rng(seed)
    for _ in range(20):
        objectives, memory, args = problem(int(rng.choice([12, 24, 60, 120])), float(rng.choice([.125, .5, 1., 2.])))
        # Include hard/exclusive constraints and retained cost objectives, with
        # >100 partial rows in some cases to exercise the real Pareto path.
        objectives[1].inclusive = bool(rng.integers(2))
        objectives[2].try_best_if_none_reaches_min = bool(rng.integers(2))
        objectives.append(tiles.Objective('cost', args['symbols'][0] + args['symbols'][2]))
        targets = [(memory, float(f)) for f in [1., *rng.uniform(.0001, .95, 5)]]
        # A different ordered constraint program can legitimately return different
        # candidates. Compare each shuffled program to its own per-target oracle,
        # never to another constraint order. Include repeated and empty targets.
        targets.extend([(memory, 1e-10), targets[1]])
        rng.shuffle(targets)
        rng.shuffle(objectives)
        rng.shuffle(args['symbols'])
        check_targets(objectives, targets, args, monkeypatch)


@pytest.mark.parametrize('mode,budget', [('independent', 0), ('independent', 8388608), ('events', 0)])
@pytest.mark.parametrize('with_objective', [False, True])
def test_pareto_keep_rate_uses_input_size(monkeypatch, mode, budget, with_objective):
    from accelforge.mapper.FFM._make_pmappings.pmapper_job import Job
    x, y = sympy.symbols('rate_x rate_y', positive=True, integer=True)
    relations = tiles.SymbolRelations()
    relations.what_tiles_symbol = [(60, x), (x, 1), (60, y), (y, 1)]
    relations.make_bounds()
    objectives = [tiles.Objective('cost', x + y)] if with_objective else []
    monkeypatch.setenv('AF_TARGET_ENUMERATION', mode)
    monkeypatch.setenv('AF_ENUMERATION_PREFIX_BYTES', '0')
    monkeypatch.setenv('AF_ENUMERATION_PARETO_BYTES', str(budget))
    j = job()
    j.log_porp_pmappings_kept = lambda *a, **kw: Job.log_porp_pmappings_kept(j, *a, **kw)
    choices, _ = tiles.get_tile_shape_choices_for_targets(
        objectives, [((x + y) / 120, 1.)], symbols=[x, y],
        what_tiles_symbol=relations, job=j)
    # 12 divisors per rank: all 144 pairs satisfy capacity, then collapse to one.
    assert len(choices) == 1
    assert j.pmapping_keep_rates['Pareto'] == pytest.approx(1 / 144)
    assert j.n_total_pmappings * np.prod(list(j.pmapping_keep_rates.values())) == pytest.approx(1)


@pytest.mark.parametrize('mode', ['independent', 'events'])
def test_deferred_fallback_counts_retained_rows(monkeypatch, mode):
    from accelforge.mapper.FFM._make_pmappings.pmapper_job import Job
    x, y = sympy.symbols('deferred_x deferred_y', positive=True, integer=True)
    relations = tiles.SymbolRelations()
    relations.what_tiles_symbol = [(4, x), (x, 1), (4, y), (y, 1)]
    relations.make_bounds()
    objectives = [tiles.Objective('usage', x + y, min_value=1000,
                                  try_best_if_none_reaches_min=True, only_care_if_valid=True)]
    monkeypatch.setenv('AF_TARGET_ENUMERATION', mode)
    j = job()
    j.log_porp_pmappings_kept = lambda *a, **kw: Job.log_porp_pmappings_kept(j, *a, **kw)
    choices, _ = tiles.get_tile_shape_choices_for_targets(
        objectives, [((x + y) / 8, 1.)], symbols=[x, y],
        what_tiles_symbol=relations, job=j)
    # The first partial stage reaches no minimum, but keeps all rows because
    # fallback is deferred. Only the complete stage selects the maximum.
    np.testing.assert_array_equal(choices, [[4, 4]])
    assert j.pmapping_keep_rates['usage'] == pytest.approx(1 / 9)
    assert j.n_total_pmappings * np.prod(list(j.pmapping_keep_rates.values())) == pytest.approx(1)


def test_unsupported_modes_use_independent_enumeration(monkeypatch):
    objectives, memory, args = problem(12, 2.)
    targets = [(memory, .5), (memory, 1.)]
    monkeypatch.setattr(tiles.pareto_module, 'TOLERANCE', .1)
    expected = oracle(objectives, targets, args)
    monkeypatch.setenv('AF_TARGET_ENUMERATION', 'events')
    j = job()
    choices, excluded = tiles.get_tile_shape_choices_for_targets(objectives, targets, job=j, **args)
    assert j.target_enumeration_stats == {'supported': 0}
    for i, plain in enumerate(expected):
        np.testing.assert_array_equal(choices[~excluded[:, i]], plain)


def test_work_statistics_do_not_survive_backend_switches(monkeypatch):
    objectives, memory, args = problem(12, 2.)
    targets, j = [(memory, .5), (memory, 1.)], job()
    for mode in ('independent', 'events', 'independent'):
        monkeypatch.setenv('AF_TARGET_ENUMERATION', mode)
        tiles.get_tile_shape_choices_for_targets(objectives, targets, job=j, **args)
        if mode == 'events':
            assert j.target_enumeration_stats['supported'] == 1
            assert j.enumeration_stats == j.enumeration_pareto_stats == {}
        else:
            assert j.target_enumeration_stats == {}
            assert j.enumeration_stats['requests'] > 0


@pytest.mark.parametrize('case_config', [
    ('glu', (8, 16, 32), [128, 256, 1024], None),
    ('glu', (8, 16, 32), [128, 256, 1024], 'GlobalBuffer:0.25,4'),
    ('matmuls', (2, 4, 8), [64, 128], 'GlobalBuffer:32,256'),
])
def test_real_templates_match_independent_choices_and_membership(monkeypatch, case_config):
    import common
    original = tiles.get_tile_shape_choices_for_targets
    comparisons = []

    def audited(objectives, capacity_targets, **kwargs):
        targets = capacity_targets
        reference_job = copy.copy(kwargs['job'])
        reference_job.messages = []
        reference_job.pmapping_keep_rates = dict(kwargs['job'].pmapping_keep_rates)
        result = original(objectives, targets, **kwargs)
        if targets:
            with monkeypatch.context() as m:
                m.setenv('AF_TARGET_ENUMERATION', 'independent')
                m.setenv('AF_ENUMERATION_PREFIX_BYTES', '0')
                m.setenv('AF_ENUMERATION_PARETO_BYTES', '0')
                expected = original(objectives, targets, **{**kwargs, 'job': reference_job})
            detail = (f'{kwargs["job"].mapping.compact_str()}\n'
                      f'objectives={[(o.name, o.formula, o.max_value, o.min_value, o.only_care_if_valid, o.try_best_if_none_reaches_min) for o in objectives]}\n'
                      f'symbols={kwargs["symbols"]}; targets={targets}')
            assert result[0].dtype == expected[0].dtype, detail
            np.testing.assert_array_equal(result[0], expected[0], err_msg=detail)
            np.testing.assert_array_equal(result[1], expected[1], err_msg=detail)
            assert kwargs['job'].pmapping_keep_rates == pytest.approx(reference_job.pmapping_keep_rates), detail
            assert kwargs['job'].n_total_pmappings == pytest.approx(reference_job.n_total_pmappings), detail
            comparisons.append(kwargs['job'].target_enumeration_stats)
        return result

    monkeypatch.setattr(tiles, 'get_tile_shape_choices_for_targets', audited)
    common.af.set_n_parallel_jobs(1)
    workload, params, cap_bytes, scales = case_config
    caps = [c / 2**20 for c in cap_bytes]
    env = {**common.capacity_fractions_env(caps), 'AF_GENERATION_VARIABLE_RESOURCES': 'GlobalBuffer',
           'AF_TARGET_ENUMERATION': 'events'}
    if scales is not None:
        env['AF_LATENCY_SCALES'] = scales
    common.search(common.build(common.Case(workload, 'nvdla', params), max(caps), common.RU),
                  env, {'AF_VARIABLE_RESOURCES': 'GlobalBuffer'})
    assert comparisons and any(s['supported'] for s in comparisons)
