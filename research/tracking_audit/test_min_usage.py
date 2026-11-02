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
