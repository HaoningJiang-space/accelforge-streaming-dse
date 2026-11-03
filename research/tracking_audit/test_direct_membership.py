"""Direct packed output must preserve every target's ordered enumeration result."""
import importlib

import numpy as np
import pandas as pd
import pytest

from test_enumeration_prefix import job, problem
from accelforge.mapper.FFM._pareto_df.target_membership import PackedMembership, build_target_membership
from accelforge.mapper.FFM._pareto_df.capacity_membership import pack_exclusions, expand_membership

tiles = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')


def unpack(packed):
    return np.column_stack([((packed.words[:, i // 64] >> np.uint64(i % 64)) & np.uint64(1)) == 0
                            for i in range(packed.n_targets)])


@pytest.mark.parametrize('k', [1, 63, 64, 65, 129, 1024])
@pytest.mark.parametrize('n', [0, 17])
def test_direct_builder_and_sorted_schema_match_dense(n, k, monkeypatch):
    rng = np.random.default_rng(k)
    groups = [(rng.integers(0, n, 13) if n else [], rng.integers(0, k, 11)) for _ in range(7)]
    dense = build_target_membership(n, k, groups)
    original = np.ones

    def guard(shape, *args, **kwargs):
        assert shape != (n, k), 'packed construction allocated a dense membership matrix'
        return original(shape, *args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(np, 'ones', guard)
        packed = build_target_membership(n, k, groups, 'packed')
    np.testing.assert_array_equal(unpack(packed), dense)
    assert packed.words.nbytes == n * ((k + 63) // 64) * 8
    # Non-sorted labels must permute ORIGINAL-order bits, including word boundaries.
    fractions = list(reversed([(i + 1) / k for i in range(k)]))
    actual = pd.DataFrame(pack_exclusions('GlobalBuffer', fractions, packed, n))
    expected = pd.DataFrame(pack_exclusions('GlobalBuffer', fractions, dense, n))
    pd.testing.assert_frame_equal(actual, expected)


@pytest.mark.parametrize('backend', ['independent', 'events'])
@pytest.mark.parametrize('k', [2, 65, 129])
def test_direct_enumeration_preserves_empty_duplicate_targets_and_fallbacks(monkeypatch, backend, k):
    monkeypatch.setenv('AF_TARGET_ENUMERATION', backend)
    objectives, memory, args = problem(60, 1.)
    bounds = np.linspace(.001, 1., k).tolist()
    bounds += [1e-12, .001, 1.]
    np.random.default_rng(31).shuffle(bounds)
    targets = [(memory, b) for b in bounds]
    choices, dense = tiles.get_tile_shape_choices_for_targets(objectives, targets, job=job(), **args)
    actual, packed = tiles.get_tile_shape_choices_for_targets(objectives, targets, job=job(),
                                                              membership_format='packed', **args)
    assert actual.dtype == choices.dtype
    np.testing.assert_array_equal(actual, choices)
    np.testing.assert_array_equal(unpack(packed), dense)


def test_direct_empty_output_and_explicit_reference_fallback(monkeypatch):
    monkeypatch.setenv('AF_TARGET_ENUMERATION', 'events')
    objectives, memory, args = problem(12, 1.)
    targets = [(memory, 1e-12), (memory, 1e-10)]
    choices, packed = tiles.get_tile_shape_choices_for_targets(objectives, targets, job=job(),
                                                              membership_format='packed', **args)
    assert choices.shape[0] == 0 and packed.words.shape == (0, 1)
    from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates import target_enumeration
    monkeypatch.setattr(target_enumeration, 'enumerate_targets', lambda *a, **kw: None)
    targets.append((memory, 1.))
    choices, dense = tiles.get_tile_shape_choices_for_targets(objectives, targets, job=job(), **args)
    actual, packed = tiles.get_tile_shape_choices_for_targets(objectives, targets, job=job(),
                                                              membership_format='packed', **args)
    np.testing.assert_array_equal(actual, choices)
    np.testing.assert_array_equal(unpack(packed), dense)
