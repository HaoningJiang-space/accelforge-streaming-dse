"""Formula analysis may be shared; target-specific constraint state may not."""
import importlib
from types import SimpleNamespace

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
