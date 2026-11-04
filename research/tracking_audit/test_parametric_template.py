"""Regions are built before query points; independent FFM remains the oracle."""
import copy
import itertools

import numpy as np
import pytest
import sympy

from research.tracking_audit import benchmark_parametric_template as bench
from research.tracking_audit.audit_interval_structure import job, program, tiles
from research.tracking_audit.parametric_template import (
    Box, RegionEnumerator, RegionState, compact_boxes, split_events,
)


@pytest.fixture(autouse=True)
def isolated_modes(monkeypatch):
    # A previous differential test must not silently disable prefix Pareto.
    monkeypatch.setenv('AF_ENUMERATION_PREFIX_BYTES', '0')
    monkeypatch.setenv('AF_ENUMERATION_PARETO_BYTES', '0')
    monkeypatch.setattr(tiles.pareto_module, 'TOLERANCE', 0)
    monkeypatch.setattr(tiles, 'IMPERFECT', False)


@pytest.mark.parametrize('minimum', [False, True])
def test_integer_events_include_exact_and_fractional_boundaries(minimum):
    family = Box(((1,2),(1,2),(1,10)))
    values = np.array([1, sympy.Rational(7,2), 4, 11], dtype=object)
    parts = split_events((family,), 2, values, minimum)
    for point in itertools.product(range(1,3),range(1,3),range(1,11)):
        masks = [mask for boxes,mask in parts if any(b.contains(point) for b in boxes)]
        assert len(masks) == 1
        np.testing.assert_array_equal(masks[0], values >= point[2] if minimum else values <= point[2])


def test_compaction_never_fills_a_hole():
    boxes = [Box(((1,1),(1,1),(1,2))), Box(((2,2),(1,1),(1,2))),
             Box(((1,2),(1,1),(4,5)))]
    result = compact_boxes(boxes)
    assert len(result) == 2
    for point in itertools.product(range(1,3),[1],range(1,6)):
        assert any(b.contains(point) for b in result) == (point[2] != 3)


def test_capacity_event_keeps_one_bit_boundary_above_float32_precision():
    requirement = 2**28
    box = Box(((1,1),(1,1),(requirement-1,requirement+1)))
    parts = split_events((box,),2,np.array([requirement],dtype=np.int64))
    assert len(parts) == 2
    for capacity in (requirement-1,requirement,requirement+1):
        mask = next(mask for boxes,mask in parts if any(b.contains((1,1,capacity)) for b in boxes))
        assert bool(mask[0]) == (capacity >= requirement)


@pytest.mark.parametrize('ranges', [((1,2),), ((1,2),(1,2),(1,2,3)),
                                   ((1,2),(1,2),(0,2)), ((1,2),(1,2),(2,1))])
def test_invalid_families_rejected(ranges):
    with pytest.raises(ValueError):
        Box(ranges)


def test_exhaustive_three_parameter_ordered_fallback_projection():
    x,y = sympy.symbols('rx ry', positive=True, integer=True)
    relations = tiles.SymbolRelations()
    relations.what_tiles_symbol = [(12,x),(x,1),(12,y),(y,1)]
    relations.make_bounds()
    objectives = [tiles.Objective('capacity',x+y,max_value=24,exact=True),
                  tiles.Objective('x_limit',x,max_value=12,only_care_if_valid=True,exact=True),
                  tiles.Objective('y_limit',y,max_value=12,only_care_if_valid=True,exact=True),
                  tiles.Objective('x_usage',x,min_value=12,only_care_if_valid=True,try_best_if_none_reaches_min=True,exact=True),
                  tiles.Objective('y_usage',y,min_value=12,only_care_if_valid=True,try_best_if_none_reaches_min=True,exact=True),
                  tiles.Objective('cost',x+2*y)]
    axes = {'capacity':2,'x_limit':0,'y_limit':1,'x_usage':0,'y_usage':1}
    args = dict(symbols=[x,y],what_tiles_symbol=relations)
    engine = RegionEnumerator(tiles,objectives,Box(((1,5),(1,5),(1,12))),axes=axes,job=job(),**args).build()
    # Query order is deliberately unrelated to event order.
    points = list(itertools.product(range(1,6),range(1,6),range(1,13)))
    np.random.default_rng(89).shuffle(points)
    for point in points:
        independent = copy.deepcopy(objectives)
        for o in independent:
            if o.name in axes:
                if o.max_value is not None:
                    o.max_value = point[axes[o.name]]
                else:
                    o.min_value = point[axes[o.name]]
        reference = tiles.get_tile_shape_choices(independent,job=job(),**args)
        np.testing.assert_array_equal(engine.query(point),reference,strict=True)
    assert engine.stats['state_expansions'] < len(points)*2
    with pytest.raises(ValueError,match='single-use'):
        engine.build()


def test_prefix_pareto_noncontiguous_membership_matches_every_integer_capacity():
    objectives,memory,args = program(1,3,0,minimums=(2.,2.))
    # Raw resource units: this is a policy counterexample, not a physical model.
    raw = sympy.expand(memory*14520)
    objectives[0] = tiles.Objective('memory',raw,max_value=14520)
    capacity = tiles.Objective('target',raw,max_value=128,only_care_if_valid=True,exact=True)
    objectives.insert(1,capacity)
    engine = RegionEnumerator(tiles,objectives,Box(((1,1),(1,1),(1,128))),
                              axes={'target':2},job=job(),**args).build()
    observed = []
    for c in range(1,129):
        reference_obj = copy.deepcopy(objectives)
        reference_obj[1].max_value = c
        expected = tiles.get_tile_shape_choices(reference_obj,job=job(),**args)
        actual = engine.query((1,1,c))
        np.testing.assert_array_equal(actual,expected,strict=True)
        if np.any(np.all(actual == [2,1,2],axis=1)):
            observed.append(c)
    assert observed == [5,6]+list(range(26,129))
    assert engine.stats['pareto_calls'] > 0


def test_coalescing_requires_order_dtype_and_pareto_history():
    objectives,_,args = program(1,3,0,bound=12)
    engine = RegionEnumerator(tiles,objectives,Box(((1,1),(1,1),(1,10))),axes={},job=job(),**args)
    a = np.array([[1,2],[3,4]],dtype=np.int64)
    states = [RegionState(rows,(Box(((1,1),(1,1),(i,i))),),history)
              for i,(rows,history) in enumerate([(a,()),(a.copy(),()),(a[::-1],()),
                  (a.astype(float),()),(a,(frozenset({('x','min')}),))],1)]
    merged = engine.merge(states)
    assert len(merged) == 4
    assert merged[0].targets == (Box(((1,1),(1,1),(1,2))),)


def test_state_budget_fails_explicitly_instead_of_dropping_candidates():
    objectives,_,args = program(1,3,0,bound=12)
    engine = RegionEnumerator(tiles,objectives,Box(((1,1),(1,1),(1,10))),axes={},
                              max_rows=1,job=job(),**args)
    with pytest.raises(MemoryError,match='state budget'):
        engine.build()


@pytest.fixture(scope='module')
def real_compiled():
    bench.common.af.set_n_parallel_jobs(1)
    bench.common.clear_switches()
    p = bench.prepare(256,(128,384,256*1024))
    return p,bench.CompiledTemplate(p,Box(((8,128),(16,384),(32*1024,256*1024))))


@pytest.mark.parametrize('point', [(48,128,132*1024),(24,256,128*1024),(96,64,64*1024),
                                  (31,127,65535),(32,128,65536),(33,129,65537)])
def test_unseen_physical_architectures_match_tiles_and_full_template_frontier(real_compiled,point):
    p,compiled = real_compiled
    actual,front = compiled.query(point)
    direct = bench.prepare(256,point,p.template_key)
    expected,_ = bench.oracle(direct)
    np.testing.assert_array_equal(bench.canonical_choices(actual),bench.canonical_choices(expected),strict=True)
    np.testing.assert_array_equal(front,bench.frontier(bench.selected_costs(direct,expected)),strict=True)


def test_query_neither_enumerates_nor_evaluates_costs_and_returns_copies(real_compiled,monkeypatch):
    _,compiled = real_compiled
    def forbidden(*a,**kw):
        raise AssertionError('query must use only the compiled representation')
    monkeypatch.setattr(tiles,'_expand_symbol_choices',forbidden)
    monkeypatch.setattr(bench,'selected_costs',forbidden)
    point = (48,128,132*1024)
    choices,costs = compiled.query(point)
    expected_choices,expected_costs = choices.copy(),costs.copy()
    choices[:] = 0
    costs[:] = 0
    again = compiled.query(point)
    assert compiled.best_mapping(point)['Total<SEP>mapping']()
    np.testing.assert_array_equal(again[0],expected_choices)
    np.testing.assert_array_equal(again[1],expected_costs)
    for invalid in ((48,128,32767),(129,128,65536),(48.,128,65536),(48,128)):
        with pytest.raises(ValueError):
            compiled.query(invalid)


def test_real_selected_mapping_resource_and_cost_reconstruct(real_compiled):
    _,compiled = real_compiled
    point = (48,128,132*1024)
    result = bench.validate_selected(bench.common.Case('matmuls','nvdla',(1,256,256)),
                                     point,compiled.best_mapping(point))
    assert result['ok'] and result['exact_gb_match']


def test_unsupported_non_power_of_two_workload_is_explicit():
    with pytest.raises(ValueError,match='power-of-two'):
        bench.prepare(255,(32,192,65536))


def test_inexact_parameter_bound_rejected():
    objectives,_,args = program(1,3,0,bound=12)
    with pytest.raises(ValueError,match='exact arithmetic'):
        RegionEnumerator(tiles,objectives,Box(((1,1),(1,1),(1,10))),
                         axes={'memory':2},job=job(),**args)
