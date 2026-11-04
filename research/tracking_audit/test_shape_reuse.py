"""Cross-shape execution reuse must not transfer shape-specific pruning."""
import importlib

import numpy as np
import pytest
from sympy import Symbol

from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.enumeration_reuse import EnumerationReuse, current
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, search_grid
from test_enumeration_prefix import job, problem

tiles = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')


@pytest.fixture(autouse=True)
def serial():
    from accelforge.util import get_n_parallel_jobs
    previous = get_n_parallel_jobs()
    common.af.set_n_parallel_jobs(1)
    yield
    common.af.set_n_parallel_jobs(previous)


@pytest.mark.parametrize('budget', [0, 64, 2**20])
def test_shape_fallbacks_and_order_remain_independent(budget):
    # Different utilization thresholds generate different prefix histories.
    programs = [problem(36, usage) for usage in (1., .25, 2., .5)]
    expected = [tiles.get_tile_shape_choices(objs, job=job(), **args)
                for objs, _, args in programs]
    with EnumerationReuse(budget) as reuse:
        for i in (3, 0, 2, 1, 0):
            objs, _, args = programs[i]
            with reuse.target(i):
                actual = tiles.get_tile_shape_choices(objs, job=job(), **args)
            np.testing.assert_array_equal(actual, expected[i])
    assert reuse.stats['peak_payload_bytes'] <= budget
    if budget == 2**20:
        assert reuse.stats['cross_target_hits'] > 0
        assert reuse.stats['expanded_rows'] < reuse.stats['requested_rows']
    assert not reuse.entries and not reuse.compiled and current() is None


def test_relation_changes_order_dtype_and_mode_cannot_alias():
    x = Symbol('x', positive=True, integer=True)
    rel = tiles.SymbolRelations()
    rel.what_tiles_symbol = [(12, x), (x, 1)]
    rel.make_bounds()
    with EnumerationReuse() as reuse:
        for bound, imperfect in ((12, False), (8, False), (8, True), (12, False)):
            rel.what_tiles_symbol = [(bound, x), (x, 1)]
            rel.make_bounds()
            actual = tiles._expand_symbol_choices(x, None, [], rel, imperfect)
            expected = tiles._compute_symbol_choices(x, None, [], rel, imperfect)
            np.testing.assert_array_equal(actual, expected)
        assert reuse.stats['expansions'] == 3
        prefix = np.array([[1], [2]])
        for arr, done in ((prefix, [x]), (prefix[::-1], [x]),
                          (prefix.astype(np.float32), [x]), (prefix, ['other'])):
            actual = reuse.expand('y', arr, done, rel, False, lambda: arr.copy())
            np.testing.assert_array_equal(actual, arr)
            assert actual.dtype == arr.dtype
            with pytest.raises(ValueError):
                actual[0, 0] = 100


def test_compile_key_preserves_symbol_order_and_coefficients():
    x, y = Symbol('x'), Symbol('y')
    with EnumerationReuse() as reuse:
        a = tiles.compile_objective([x, y], x - 2*y)
        b = tiles.compile_objective([y, x], x - 2*y)
        c = tiles.compile_objective([x, y], 2*x - y)
        assert (a(2., 3.), b(2., 3.), c(2., 3.)) == (-4., -1., 1.)
        assert tiles.compile_objective([x, y], x - 2*y) is a
        assert reuse.stats['compilations'] == 3


def test_initial_delta_order_is_part_of_expansion_contract():
    stride, initial = Symbol('stride'), Symbol('initial')
    rel = tiles.SymbolRelations()
    rel.what_tiles_symbol = [(8, stride), (stride, 1)]
    rel.tile_shape_and_initial = [(stride, initial)]
    rel.delta_choices = [(initial, (0, 1))]
    rel.make_bounds()
    prefix = np.array([[2]])
    with EnumerationReuse() as reuse:
        for deltas in ((0, 1), (1, 0)):
            rel.delta_choices = [(initial, deltas)]
            expected = tiles._compute_symbol_choices(initial, prefix, [stride], rel, False)
            actual = tiles._expand_symbol_choices(initial, prefix, [stride], rel, False)
            np.testing.assert_array_equal(actual, expected)
        assert reuse.stats['expansions'] == 2


def test_scope_cleans_up_after_exception_and_rejects_parallel_use():
    with pytest.raises(RuntimeError):
        with EnumerationReuse():
            raise RuntimeError('interrupted')
    assert current() is None
    common.af.set_n_parallel_jobs(2)
    with pytest.raises(ValueError, match='one worker'):
        with EnumerationReuse():
            pass


def test_real_shape_frontiers_and_reconstruction():
    case = common.Case('matmuls', 'nvdla', (3, 32, 32))
    shapes, caps = [(4, 16), (8, 8)], [1024, 4096]
    reference = search_grid(case, shapes, caps, 'max_frontier')
    shared = search_grid(case, shapes, caps, 'reuse_frontier')
    assert reference['numeric_frontiers'] == shared['numeric_frontiers']
    assert shared['reuse_stats']['cross_target_hits'] > 0
    assert all(p['ok'] for p in shared['picks'])
    assert [p.get('edp') for p in reference['picks']] == [p.get('edp') for p in shared['picks']]


def test_shape_builder_checks_dimensions_and_attention_extract():
    case = common.Case('attention', 'nvdla', (16, 1, 8))
    spec = build(case, (4, 16), 1024, common.RU)
    assert [e.name for e in spec.workload.einsums] == ['QK', 'QK_softmax', 'AV']
    assert [d.fanout for d in spec.arch.find('ArrayFanout').spatial] == [4, 16]
    for shape in ((0, 16), (4, 16, 1), (4.5, 16)):
        with pytest.raises(ValueError):
            build(case, shape, 1024, common.RU)


def test_real_attention_frontiers_and_reconstruction():
    case = common.Case('attention', 'nvdla', (16, 1, 8))
    shapes, caps = [(4, 16), (8, 8)], [256, 1024]
    reference = search_grid(case, shapes, caps, 'max_frontier')
    shared = search_grid(case, shapes, caps, 'reuse_frontier')
    assert reference['numeric_frontiers'] == shared['numeric_frontiers']
    assert all(p['ok'] for p in shared['picks'])
    assert [p.get('edp') for p in reference['picks']] == [p.get('edp') for p in shared['picks']]
