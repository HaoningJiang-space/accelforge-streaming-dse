"""Projection preparation must not cache mutable workload state or tile results."""
import importlib
from types import SimpleNamespace

import numpy as np
import pytest
import sympy

from accelforge.frontend.mapping import Temporal
from accelforge.frontend._workload_isl import _symbolic as symbolic
from accelforge.mapper.FFM._pareto_df.df_convention import stride2col, initial2col

tiles = importlib.import_module(
    'accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')


class Accesses(dict):
    def __iter__(self):
        return iter(self.values())


def einsum_for(projections):
    return SimpleNamespace(
        rank_variables=['h', 'r', 'c', 'unused'],
        tensor_accesses=Accesses({name: SimpleNamespace(name=name, projection=projection)
                                 for name, projection in projections.items()}))


def test_parse_once_by_expression_and_return_fresh_containers(monkeypatch):
    symbolic._parse_projection_expr.cache_clear()
    parser = sympy.parsing.sympy_parser
    original = parser.parse_expr
    calls = []

    def counted(expression):
        calls.append(expression)
        return original(expression)

    monkeypatch.setattr(parser, 'parse_expr', counted)
    einsum = einsum_for({'A': {'H': '2*h + r', 'C': 'c'}})
    expected = symbolic.get_projection_expr(einsum, 'A')
    first = symbolic.get_rank_variable_relevancy(einsum, 'A')
    assert isinstance(first['h'], symbolic.PartiallyRelevant)
    assert isinstance(first['r'], symbolic.PartiallyRelevant)
    assert isinstance(first['c'], symbolic.Relevant)
    assert isinstance(first['unused'], symbolic.Irrelevant)
    expected.clear()
    first['h'].rank = 'changed'
    assert symbolic.get_rank_variable_relevancy(einsum, 'A')['h'].rank == 'H'
    assert set(symbolic.get_projection_expr(einsum, 'A')) == {'H', 'C'}
    assert calls == ['2*h + r', 'c']
    einsum.tensor_accesses['A'].projection['H'] = 'h'
    assert isinstance(symbolic.get_rank_variable_relevancy(einsum, 'A')['h'], symbolic.Relevant)
    assert calls == ['2*h + r', 'c', 'h']


def test_relevancy_preserves_first_matching_rank_and_constant_indices():
    einsum = einsum_for({'A': {'First': 'h', 'Second': 'h+r', 'Constant': '7'}})
    result = symbolic.get_rank_variable_relevancy(einsum, 'A')
    assert isinstance(result['h'], symbolic.Relevant) and result['h'].rank == 'First'
    assert isinstance(result['r'], symbolic.PartiallyRelevant) and result['r'].rank == 'Second'
    assert isinstance(result['c'], symbolic.Irrelevant)


@pytest.mark.parametrize('values', [[1, 2, 4], []])
def test_rank_columns_use_current_shapes_tiles_and_projection_order(values):
    htile = sympy.Symbol('test_htile', positive=True, integer=True)
    outer = Temporal(rank_variable='h', tile_shape=htile)
    inner = Temporal(rank_variable='r', tile_shape=2)
    unfused = Temporal(rank_variable='h', tile_shape=1)
    outer._fused = inner._fused = True
    unfused._fused = False
    einsum = einsum_for({'A': {'H': '2*h+r'}, 'B': {'H': '3*h+r', 'Constant': '17'}})
    job = SimpleNamespace(einsum_name='E', spec=SimpleNamespace(
        workload=SimpleNamespace(einsums={'E': einsum})), rank_variable_bounds={'h': 32, 'r': 7})
    for bound, factor in ((32, 3), (64, 5)):
        job.rank_variable_bounds = {'h': bound, 'r': 7}
        einsum.tensor_accesses['B'].projection['H'] = f'{factor}*h+r'
        data = {htile.name: np.array(values, dtype=np.float32)}
        tiles._calculate_iterations_and_rank_columns(
            [outer, inner, unfused], job, data, job.rank_variable_bounds)
        np.testing.assert_array_equal(np.asarray(data[stride2col('H', 0)], dtype=float),
                                      np.array(values) * factor)
        np.testing.assert_array_equal(data[initial2col('H', 0)], np.array(values) * factor + 7)
        assert data[stride2col('H', 1)] == 2
        assert data[initial2col('H', 1)] == factor * bound + 2
        assert stride2col('H', 2) not in data
        assert stride2col('Constant', 0) not in data


def test_projection_evaluator_keeps_float_precision_and_empty_batches():
    h, r = sympy.symbols('h r')
    expr = sympy.Rational(2, 3) * h + r + 1
    symbols, names, coefficients, evaluate = tiles._prepare_rank_projection(expr)
    original = sympy.lambdify(symbols, expr)
    for dtype in (np.float32, np.float64, np.int64):
        for n in (0, 3):
            args = [np.arange(n, dtype=dtype) + (2 if s == h else 4) for s in symbols]
            actual, expected = evaluate(*args), original(*args)
            assert actual.dtype == expected.dtype
            np.testing.assert_array_equal(actual, expected)
    assert coefficients[names.index('h')] == sympy.Rational(2, 3)


@pytest.mark.parametrize('left,right', [
    (0, -3), (0, 0), (1, 2), (1., 2),
    (sympy.Rational(1, 3), sympy.Rational(1, 2)),
    (sympy.Symbol('unknown_stat', real=True), 0),
    (sympy.Symbol('positive_stat', positive=True), 0),
    (sympy.Symbol('negative_stat', negative=True), 0),
    (sympy.oo, 2), (np.int64(3), np.int64(4)),
])
def test_statistic_maximum_preserves_sympy_semantics_and_operand_ownership(left, right):
    from accelforge.model._looptree.reuse.symbolic.symbolic import BuffetStats
    a, b = BuffetStats(max_occupancy=left), BuffetStats(max_occupancy=right)
    expected = sympy.Max(left, right)
    for _ in range(2):
        result = a + b
        assert result.max_occupancy == expected
        assert type(result.max_occupancy) is type(expected)
        result.max_occupancy = 999
        assert a.max_occupancy == left and b.max_occupancy == right


def test_cached_maximum_keeps_numeric_types_distinct():
    from accelforge.model._looptree.reuse.symbolic.symbolic import _maximum_stat
    _maximum_stat.cache_clear()
    assert type(_maximum_stat(2, 1)) is type(sympy.Max(2, 1))
    assert type(_maximum_stat(2., 1)) is type(sympy.Max(2., 1))
    assert _maximum_stat.cache_info().misses == 2
