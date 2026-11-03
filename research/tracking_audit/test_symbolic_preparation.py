"""Formula analysis may be shared; target-specific constraint state may not."""
import importlib
from collections import Counter
from types import SimpleNamespace

import numpy as np
from sympy import Symbol

tiles = importlib.import_module(
    'accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')


def test_completed_constraint_does_not_clear_cached_formula_goals():
    tile = Symbol('cache_test_tile', positive=True, integer=True)
    relations = tiles.SymbolRelations()
    relations.what_tiles_symbol = [(4, tile), (tile, 1)]
    relations.make_bounds()
    job = SimpleNamespace(
        spec=SimpleNamespace(mapper=SimpleNamespace(ffm=SimpleNamespace(
            _count_option_for_mapsapce_size_evaluation=(),
        ))),
        n_total_pmappings=1, n_evaluated_pmappings=0,
        log_message=lambda *a: None, log_porp_pmappings_kept=lambda *a: None,
    )
    goals = tiles.partition_formula(tile, {tile}, relations.bounds)
    assert goals[tile].goal == 'min'
    tiles.get_tile_shape_choices([
        tiles.Objective('capacity', tile, max_value=4, only_care_if_valid=True),
    ], [tile], relations, job, keep_symbols=[tile])
    assert goals[tile].goal == 'min'
    assert tiles.partition_formula(tile, {tile}, relations.bounds)[tile].goal == 'min'


def test_targets_share_compilation_but_not_constraint_results(monkeypatch):
    tile = Symbol('prepared_tile', positive=True, integer=True)
    relations = tiles.SymbolRelations()
    relations.what_tiles_symbol = [(4, tile), (tile, 1)]
    relations.make_bounds()
    job = SimpleNamespace(
        spec=SimpleNamespace(mapper=SimpleNamespace(ffm=SimpleNamespace(
            _count_option_for_mapsapce_size_evaluation=(),
        ))),
        n_total_pmappings=1, n_evaluated_pmappings=0, pmapping_keep_rates={},
        log_message=lambda *a: None, log_porp_pmappings_kept=lambda *a: None,
    )
    compiled = Counter()
    original = tiles.util._lambdify_type_check

    def compile_once(symbols, formula):
        compiled[(tuple(symbols), formula)] += 1
        return original(symbols, formula)

    monkeypatch.setattr(tiles.util, '_lambdify_type_check', compile_once)
    objectives = [tiles.Objective('memory', 1 / tile, max_value=1),
                  tiles.Objective('usage', 1 / (2 * tile), min_value=1,
                                  only_care_if_valid=True, try_best_if_none_reaches_min=True)]
    choices, excluded = tiles.get_tile_shape_choices_for_targets(
        objectives, ((1 / tile, .5), (1 / tile, 1.)), symbols=[tile],
        what_tiles_symbol=relations, job=job, keep_symbols=[tile],
    )
    np.testing.assert_array_equal(choices, [[1], [2]])
    np.testing.assert_array_equal(excluded, [[True, False], [False, True]])
    assert compiled and max(compiled.values()) == 1
    assert objectives[0].max_value == 1  # Target-local state must not leak back.


def test_formula_logging_is_reused_but_mutable_goals_are_not():
    from sympy import Max
    text = tiles.SymbolicText()
    x = Symbol('log_x', positive=True)
    formula = Max(x, 1 / x) + x**2
    goals = {formula: tiles.Goal('min'), x: tiles.Goal('diff')}
    assert text(formula) == str(formula)
    assert text.goals(goals) == repr(goals)
    misses = text._str.cache_info().misses
    repr_misses = text._repr.cache_info().misses
    goals[formula].goal = 'max'
    assert text(formula) == str(formula)
    assert text.goals(goals) == repr(goals)
    assert text._str.cache_info().misses == misses
    assert text._repr.cache_info().misses == repr_misses
