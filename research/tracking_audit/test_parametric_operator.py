"""All-template terminal union, region holes and independently searched operators."""
import itertools
import json
from types import SimpleNamespace

import numpy as np
import pytest

from research.tracking_audit import parametric_operator as p


def points(box):
    return set(itertools.product(*(range(lo,hi+1) for lo,hi in box.ranges)))


@pytest.mark.parametrize('cut', [((1,3),(1,3),(1,3)),((2,2),(2,2),(2,2)),
                                ((2,4),(2,4),(2,4)),((4,5),(1,3),(1,3)),
                                ((1,1),(1,3),(1,3))])
def test_box_subtraction_covers_difference_without_overlap(cut):
    box = p.Box(((1,3),(1,3),(1,3)))
    other = p.Box(cut)
    result = p.subtract(box,other)
    seen = set()
    for r in result:
        assert not seen & points(r)
        seen |= points(r)
    assert seen == points(box)-points(other)


def test_overlay_retains_infeasible_gaps_and_non_byte_sized_regions():
    family = p.Box(((1,2),(1,2),(1,5)))
    # A template works at bytes 1,2 and 4,5, but not 3. The isolated bit-only
    # interval [17,23] contains no public integer-byte capacity.
    leaves = [SimpleNamespace(targets=(p.Box(((1,2),(1,2),(8,16))),
                                      p.Box(((1,2),(1,2),(32,40))))),
              SimpleNamespace(targets=(p.Box(((1,2),(1,2),(17,23))),))]
    template = SimpleNamespace(engine=SimpleNamespace(leaves=leaves))
    result = p.overlay({():(family,)},template,100)
    for point in points(family):
        keys = [key for key,boxes in result.items() if any(box.contains(point) for box in boxes)]
        assert keys == ([(None,)] if point[2]==3 else [(0,)])


def test_joint_budget_error_never_returns_a_partial_frontier():
    family = p.Box(((1,2),(1,2),(1,5)))
    template = SimpleNamespace(engine=SimpleNamespace(leaves=[
        SimpleNamespace(targets=(p.Box(((1,2),(1,2),(8,16))),))]))
    with pytest.raises(MemoryError,match='region budget'):
        p.overlay({():(family,)},template,1)


def test_terminal_pareto_preserves_only_available_provenance():
    costs = np.array([[1.,1.,8.],[1.,1.,8.],[2.,2.,16.]])
    np.testing.assert_array_equal(p.frontier_ids(costs,[0,1,2]),[0])
    # An equal cheaper-source ID outside this region must not be substituted.
    np.testing.assert_array_equal(p.frontier_ids(costs,[1,2]),[1])
    assert not len(p.frontier_ids(costs,[]))


@pytest.fixture(scope='module')
def compiled():
    p.b.common.af.set_n_parallel_jobs(1)
    p.b.common.clear_switches()
    # Warm only the unrelated generic Skyline JIT.
    p.b.frontier(np.array([[1.,2.,3.],[2.,1.,2.]]))
    family = p.Box(((8,128),(16,384),(32768,262144)))
    programs = p.prepare_all(256,(128,384,262144))
    assert len(programs) == 6
    return p.CompiledOperator(programs,family)


@pytest.mark.parametrize('point',[(48,128,135168),(24,256,131072),(96,64,65536),
                                  (31,127,65535),(33,129,65537)])
def test_complete_operator_matches_unrestricted_physical_ffm(compiled,point):
    case = p.b.common.Case('matmuls','nvdla',(1,256,256))
    spec = p.b.build(case,point[:2],point[2],p.b.common.RU)
    # This is the normal full make_pmappings/join_pmappings route, without
    # substituting the new prepared programs or limiting its template set.
    result,_ = p.b.common.search(spec)
    reference = p.b.frontier(result.data[[p.b.E,p.b.L,
        'reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right']].to_numpy())
    actual,ids = compiled.query(point)
    np.testing.assert_array_equal(actual,reference,strict=True)
    best = p.b.validate_selected(case,point,compiled.best_mapping(point))
    assert best['ok'] and best['exact_gb_match']
    assert len(ids) == len(actual)


def test_per_template_candidate_coverage_and_real_prefix_pareto(compiled):
    assert sum(t.engine.stats['pareto_calls'] for t in compiled.templates)>0
    for point in [(8,16,32768),(48,128,135168),(128,384,262144)]:
        physical = p.prepare_all(256,point)
        assert [x.template_key for x in physical] == [x.template_key for x in compiled.programs]
        for direct,template in zip(physical,compiled.templates):
            reference,_ = p.b.oracle(direct)
            selected,_ = template.query(point)
            np.testing.assert_array_equal(p.b.canonical_choices(selected),
                                          p.b.canonical_choices(reference),strict=True)


def test_query_has_no_enumeration_cost_or_pareto_work(compiled,monkeypatch):
    point = (48,128,135168)
    expected,ids = compiled.query(point)
    def forbidden(*a,**kw):
        raise AssertionError('query must use compiled terminal state')
    monkeypatch.setattr(p.b,'oracle',forbidden)
    monkeypatch.setattr(p.b,'selected_costs',forbidden)
    monkeypatch.setattr(p.b.tiles,'makepareto_numpy',forbidden)
    monkeypatch.setattr(p.b.tiles,'_expand_symbol_choices',forbidden)
    actual,actual_ids = compiled.query(point)
    assert compiled.best_mapping(point)['Total<SEP>mapping']()
    np.testing.assert_array_equal(actual,expected)
    actual[:]=0
    actual_ids[:]=-1
    np.testing.assert_array_equal(compiled.query(point)[0],expected)
    np.testing.assert_array_equal(compiled.query(point)[1],ids)
    for invalid in ((7,16,32768),(128,385,262144),(48.,128,135168),(48,128)):
        with pytest.raises(ValueError):
            compiled.query(invalid)
    for invalid_id in (-1,len(compiled.origins),1.5,True):
        with pytest.raises(ValueError):
            compiled.mapping(invalid_id)


def test_terminal_regions_cover_family_with_nonoverlapping_sources(compiled):
    boxes = [box for region in compiled.regions for box in region.boxes]
    volume = lambda box: np.prod([hi-lo+1 for lo,hi in box.ranges],dtype=object)
    assert sum(volume(box) for box in boxes) == volume(compiled.family)
    assert all(p.intersection(a,b) is None for i,a in enumerate(boxes) for b in boxes[i+1:])


def test_physical_audit_captures_every_template_candidate(compiled):
    from research.tracking_audit import benchmark_parametric_operator as audit
    point = (48,128,135168)
    front,_,records,_ = audit.physical_query(256,point)
    expected = audit.candidate_records(compiled.programs,[t.query(point)[0] for t in compiled.templates])
    assert len(records)==6 and records==expected
    np.testing.assert_array_equal(front,compiled.query(point)[0])


def test_summary_does_not_hide_an_early_run_mismatch(tmp_path):
    from research.tracking_audit.summarize_parametric_operator import run
    for mode in ('regions','independent','cached'):
        for i in range(1,4):
            bad = mode=='independent' and i==1
            report = dict(mode=mode,all_picks_valid=True,source_sha256={'x':'same'},template_ids=['t'],
                compilation={'templates':[]},queries=[dict(point=[48,128,135168],candidates={'t':'same'},
                frontier=[[2 if bad else 1,1,1]],validation={'ok':True,'exact_gb_match':True})])
            (tmp_path/f'{mode}{i}.json').write_text(json.dumps(report))
    with pytest.raises(ValueError,match='complete candidate/frontier mismatch'):
        run(tmp_path)
