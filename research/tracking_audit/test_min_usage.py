"""Exercise min-usage fallback through the real tile enumerator, without a search."""
from types import SimpleNamespace

import numpy as np
import pytest
from sympy import Symbol

from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes import (
    Objective,
    SymbolRelations,
    get_tile_shape_choices,
)


def enumerate_tiles(min_usage, fallback=True):
    tile = Symbol("tile", positive=True, integer=True)
    relations = SymbolRelations()
    relations.what_tiles_symbol = [(4, tile), (tile, 1)]
    relations.make_bounds()
    job = SimpleNamespace(
        spec=SimpleNamespace(mapper=SimpleNamespace(ffm=SimpleNamespace(
            _count_option_for_mapsapce_size_evaluation=(),
        ))),
        n_total_pmappings=1,
        n_evaluated_pmappings=0,
        log_message=lambda *args: None,
        log_porp_pmappings_kept=lambda *args: None,
    )
    # Four rank elements mapped onto eight spatial instances: usage = 4 / tile / 8.
    return get_tile_shape_choices(
        [Objective("usage", 1 / (2 * tile), min_value=min_usage,
                   only_care_if_valid=True, try_best_if_none_reaches_min=fallback)],
        [tile], relations, job, keep_symbols=[tile],
    ).ravel()


@pytest.mark.parametrize("minimum, expected", [(1.0, [1]), (0.5, [1]), (0.25, [1, 2])])
def test_prefers_highest_usage_when_minimum_cannot_be_reached(minimum, expected):
    np.testing.assert_array_equal(np.sort(enumerate_tiles(minimum)), expected)


def test_hard_minimum_still_rejects_all_below_threshold():
    assert enumerate_tiles(1.0, fallback=False).size == 0


def test_min_usage_fallback_is_capacity_dependent():
    # This is the counterexample behind the grid coverage limitation, not a
    # relaxation of min_usage: both enumerations must obey the existing policy.
    tile = Symbol('tile', positive=True, integer=True)
    results = {}
    for capacity in (2, 4):
        relations = SymbolRelations()
        relations.what_tiles_symbol = [(4, tile), (tile, 1)]
        relations.make_bounds()
        job = SimpleNamespace(
            spec=SimpleNamespace(mapper=SimpleNamespace(ffm=SimpleNamespace(
                _count_option_for_mapsapce_size_evaluation=(),
            ))),
            n_total_pmappings=1, n_evaluated_pmappings=0,
            log_message=lambda *a: None, log_porp_pmappings_kept=lambda *a: None,
        )
        results[capacity] = get_tile_shape_choices([
            Objective('memory', 4 / tile, max_value=capacity),
            Objective('usage', 1 / (2 * tile), min_value=1., only_care_if_valid=True,
                      try_best_if_none_reaches_min=True),
        ], [tile], relations, job, keep_symbols=[tile]).ravel()
    np.testing.assert_array_equal(results[2], [2])
    np.testing.assert_array_equal(results[4], [1])
    # The larger search's retained candidate needs four units and cannot serve
    # capacity two, where the independent search kept a different candidate.
    assert not (4 / results[4] <= 2).any()


def enumerate_with_memory(capacity_units, targets=(), usages=((1, 2),)):
    """Tiles kept for memory 4/tile units, normalized by capacity_units, and min-usage
    objectives usage = a / (b * tile) or tile / 8 (b == 0), each with fallback."""
    from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes import (
        get_tile_shape_choices_for_targets,
    )
    tile = Symbol('tile', positive=True, integer=True)
    relations = SymbolRelations()
    relations.what_tiles_symbol = [(4, tile), (tile, 1)]
    relations.make_bounds()
    job = SimpleNamespace(
        spec=SimpleNamespace(mapper=SimpleNamespace(ffm=SimpleNamespace(
            _count_option_for_mapsapce_size_evaluation=(),
        ))),
        n_total_pmappings=1, n_evaluated_pmappings=0, pmapping_keep_rates={},
        log_message=lambda *a: None, log_porp_pmappings_kept=lambda *a: None,
    )
    memory = (4 / tile) / capacity_units
    objectives = [Objective('memory', memory, max_value=1)]
    for i, (a, b) in enumerate(usages):
        objectives.append(Objective(f'usage{i}', a / (b * tile) if b else tile / 8, min_value=1.,
                                    only_care_if_valid=True, try_best_if_none_reaches_min=True))
    choices, excluded = get_tile_shape_choices_for_targets(
        objectives, tuple((memory, f) for f in targets), symbols=[tile],
        what_tiles_symbol=relations, job=job, keep_symbols=[tile],
    )
    tiles = choices.ravel().tolist()
    if excluded is None:
        return set(tiles)
    # Per target: the rows that target's enumeration kept.
    return set(tiles), [{t for t, out in zip(tiles, excluded[:, k]) if not out}
                        for k in range(len(targets))]


@pytest.mark.parametrize('usages', [((1, 2),), ((1, 2), (1, 0))])
def test_capacity_targets_cover_every_target_capacity(usages):
    # Independent searches at 2 and 4 units against one search at 4 units with targets
    # 0.5 and 1. The second case chains two fallbacks: applying the second one to the
    # union of the first one's survivors lost tile 1 (found in review).
    small, large = enumerate_with_memory(2, usages=usages), enumerate_with_memory(4, usages=usages)
    assert (small, large) == ({2}, {1})
    union, per_target = enumerate_with_memory(4, targets=(0.5, 1.0), usages=usages)
    assert union == small | large
    # Membership is exact per target, so tile 2 (kept for 0.5, fits 1.0 too) is not
    # returned for the full capacity, where the independent search removed it.
    assert per_target == [small, large]


def test_single_full_target_matches_the_plain_search():
    union, per_target = enumerate_with_memory(4, targets=(1.0,))
    assert union == per_target[0] == enumerate_with_memory(4)


@pytest.mark.parametrize('usage, minimum, fallback, expected_rows', [
    (0.75, 1., True, 1),
    (0.75, 1., False, 0),
    (1., 1., False, 1),
    (1.25, 1., True, 0),
])
def test_fixed_template_checks_constraints_without_tile_variables(usage, minimum, fallback, expected_rows):
    job = SimpleNamespace(n_evaluated_pmappings=0, log_porp_pmappings_kept=lambda *a: None)
    choices = get_tile_shape_choices([
        Objective('memory', usage, max_value=1),
        Objective('min_usage', usage, min_value=minimum, try_best_if_none_reaches_min=fallback),
    ], [], SymbolRelations(), job)
    assert choices.shape == (expected_rows, 0)


def test_fixed_template_capacity_membership_includes_only_feasible_targets():
    from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes import (
        get_tile_shape_choices_for_targets,
    )
    job = SimpleNamespace(n_total_pmappings=1, n_evaluated_pmappings=0,
                          pmapping_keep_rates={}, log_porp_pmappings_kept=lambda *a: None)
    choices, excluded = get_tile_shape_choices_for_targets(
        [Objective('memory', .75, max_value=1)], ((.75, .5), (.75, 1.)),
        symbols=[], what_tiles_symbol=SymbolRelations(), job=job,
    )
    assert choices.shape == (1, 0)
    np.testing.assert_array_equal(excluded, [[True, False]])


def test_real_fixed_template_survives_shared_capacity_search():
    import common
    common.af.set_n_parallel_jobs(1)
    case = common.Case('matmuls', 'nvdla', (1, 1, 1))
    caps = [64 / 2**20, 128 / 2**20]
    expected = {}
    for variant in ('indep', 'var', 'push'):
        for cap, data, _ in common.run_variant(variant, case, caps):
            assert len(data) == 1
            pick = common.check_pick(case, cap, common.best_row(data))
            assert pick['ok'], pick
            edp = pick['reevaluated']['edp']
            if variant == 'indep':
                expected[cap] = edp
            else:
                assert edp == expected[cap]


def capacity_fractions(monkeypatch, value, metrics):
    from accelforge.frontend import arch
    from accelforge.mapper.FFM._make_pmappings.make_pmappings import _capacity_fractions_from_env
    monkeypatch.setenv('AF_GENERATION_CAPACITY_FRACTIONS', value)
    gb = arch.Memory(name='GlobalBuffer', size=8)
    return _capacity_fractions_from_env({'E': [SimpleNamespace(flattened_arch=[gb])]}, metrics)


def test_capacity_fractions_are_parsed_and_include_one(monkeypatch):
    from accelforge.frontend.mapper.metrics import Metrics
    ru = Metrics.ENERGY | Metrics.LATENCY | Metrics.RESOURCE_USAGE
    assert capacity_fractions(monkeypatch, 'GlobalBuffer:0.25, 0.5', ru) == ('GlobalBuffer', (0.25, 0.5, 1.0))


@pytest.mark.parametrize('value', ['GlobalBuffer', 'GlobalBuffer:0', 'GlobalBuffer:1.5', 'GlobalBuffer:x', 'Nope:0.5'])
def test_bad_capacity_fractions_are_rejected(monkeypatch, value):
    from accelforge.frontend.mapper.metrics import Metrics
    with pytest.raises(ValueError):
        capacity_fractions(monkeypatch, value, Metrics.ENERGY | Metrics.LATENCY | Metrics.RESOURCE_USAGE)


def test_capacity_fractions_require_resource_usage(monkeypatch):
    from accelforge.frontend.mapper.metrics import Metrics
    with pytest.raises(ValueError, match='RESOURCE_USAGE'):
        capacity_fractions(monkeypatch, 'GlobalBuffer:0.5', Metrics.ENERGY | Metrics.LATENCY)
