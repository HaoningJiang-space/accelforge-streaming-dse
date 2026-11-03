"""Cross-capacity coverage requires a physical target architecture as oracle."""
from fractions import Fraction
import copy
import importlib
import json
import os
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import sympy

import common
import audit_exact_capacity as audit
from accelforge.mapper.FFM._pareto_df import exact_resources as exact
from accelforge.mapper.FFM._pareto_df.capacity_membership import pack_exclusions, is_membership_col
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from accelforge.mapper.FFM._pareto_df.df_convention import add_to_col


def test_exact_symbolic_capacity_never_sums_normalized_float32():
    x, y = sympy.symbols('x y', positive=True, integer=True)
    # This is the real failing 68 B tile, with a 96 B shared maximum.
    bits = exact.bit_array(8 * (4*x + 8*y + 4), {x:np.array([8]), y:np.array([4])}, 1)
    assert bits.tolist() == [68*8]
    assert bits[0] <= 68*8 and bits[0] > 68*8 - 1
    normalized = np.float32(32/96) + np.float32(32/96) + np.float32(4/96)
    assert normalized > np.float32(68/96)  # historical defect, not a tolerance test
    np.testing.assert_array_equal(exact.bit_array(8*x/y, {x:[8,12], y:[2,3]},2),[32,32])
    np.testing.assert_array_equal(exact.bit_array(sympy.ceiling(x/3)+sympy.Max(x,y),{x:[4,9],y:[5,3]},2),[7,12])
    assert exact.bit_array(sympy.Float(8),{},1)[0] == 8
    with pytest.raises(exact.ExactResourceError):
        exact.bit_array(sympy.Float(.1)*x,{x:[10]},1)
    with pytest.raises(exact.ExactResourceError):
        exact.bit_array(x/3,{x:[1]},1)


def test_bit_boundary_query_and_unit_contract():
    n = 64*2**20*8
    frame = pd.DataFrame({common.GB:[n-8,n,n+8],exact.capacity_column('GlobalBuffer'):[2*n]*3})
    pm = PmappingDataframe(frame,3,3,skip_pareto=True)
    public = exact.public_frame(pm.data)
    labels = [float((n-8)/(2*n)),.5,1.]
    for c,v in pack_exclusions('GlobalBuffer',labels,None,3).items():
        public[c] = v
    # A misleading low-precision display value cannot admit an oversized row.
    public[common.GB] = np.float32(.5)
    assert common.rows_for_capacity(public,(n-8)/2**23,2*n/2**23)[audit.RAW].tolist() == [n-8]
    assert common.rows_for_capacity(public,n/2**23,2*n/2**23)[audit.RAW].tolist() == [n-8,n]
    with pytest.raises(ValueError,match='absolute-bit'):
        common.rows_for_capacity(public.drop(columns=audit.RAW),n/2**23,2*n/2**23)
    with pytest.raises(exact.ExactResourceError,match='different capacities'):
        exact.check_units([frame,frame.assign(**{exact.capacity_column('GlobalBuffer'):n})])
    with pytest.raises(exact.ExactResourceError,match='schemas'):
        exact.check_units([frame,frame.drop(columns=exact.capacity_column('GlobalBuffer'))])
    with pytest.raises(exact.ExactResourceError):
        exact.public_frame(frame.assign(**{common.GB:1.5}))
    with pytest.raises(exact.ExactResourceError):
        exact.comparison_values([Fraction(2**60),Fraction(2**60+1)])


def test_checked_resource_arithmetic_and_callback_units():
    frame = pd.DataFrame({common.GB:[40,60], 'other':[1.,2.],
                          exact.capacity_column('GlobalBuffer'):[100,100]})
    add_to_col(frame,common.GB,'other')
    assert frame[common.GB].tolist() == [41,62]
    assert frame[common.GB].dtype == np.int64
    pm = PmappingDataframe(frame,2,2,skip_pareto=True)
    # Preserve the existing callback's normalized reservation interface.
    assert pm.filter_rows(lambda d:d[common.GB] <= .5).data[common.GB].tolist() == [41]
    frame[common.GB] = exact.MAX_EXACT
    with pytest.raises(exact.ExactResourceError):
        add_to_col(frame,common.GB,'other')


@pytest.fixture(scope='module')
def physical_references():
    common.af.set_n_parallel_jobs(1)
    return {c:audit.search(c) for c in (67,68,69)}


@pytest.mark.parametrize('backend,codec', [('independent','bitset'),('events','bitset'),('events','interval')])
def test_physical_targets_and_all_templates_match_shared_search(physical_references,backend,codec):
    shared = audit.search(96,[67,68,69,96],backend,codec)
    for cap,reference in physical_references.items():
        evidence = audit.compare(reference,shared,cap,96)
        assert evidence['templates'] == 24
        if cap == 68:
            assert evidence['pick']['reevaluated']['edp'] == pytest.approx(2.04476416e-16,rel=1e-10,abs=0)
            assert evidence['pick']['mapping_id'] == evidence['reference_pick']['mapping_id']
            assert evidence['pick']['reevaluated']['reservation_bits'][audit.RAW] == 544


def test_high_level_api_retains_source_membership(monkeypatch):
    api = importlib.import_module('accelforge.mapper.FFM.main')
    case = audit.CASE
    caps = [68/2**20,96/2**20]
    common.clear_switches()
    os.environ.update({**common.capacity_fractions_env(caps),'AF_VARIABLE_RESOURCES':'GlobalBuffer',
                    'AF_GENERATION_VARIABLE_RESOURCES':'GlobalBuffer','AF_TARGET_ENUMERATION':'events',
                    'AF_CAPACITY_MEMBERSHIP':'bitset'})
    spec = common.build(case,max(caps),common.RU)
    pm = api.make_pmappings(spec,print_number_of_pmappings=False)
    low = api.join_pmappings(copy.deepcopy(pm))
    monkeypatch.setattr(api,'make_pmappings',lambda *a,**k:copy.deepcopy(pm))
    high = api.map_workload_to_arch(spec,print_number_of_pmappings=False)
    common.clear_switches()
    columns = [c for c in low.data if is_membership_col(c)]
    assert columns
    pd.testing.assert_frame_equal(low.data[columns].reset_index(drop=True),high.data[columns].reset_index(drop=True))
    assert all(p['ok'] for p in common.validate_capacity_picks(case,caps,high.data))
    assert common.best_row(common.rows_for_capacity(high.data,caps[0],max(caps)))[audit.RAW] == 544


def test_benchmark_stops_and_saves_first_measured_bad_provenance(monkeypatch,tmp_path):
    import benchmark_membership_pushdown as bench
    calls = []
    def broken():
        raise RuntimeError('injected first-measurement reconstruction failure')
    def join(_):
        calls.append(1)
        return SimpleNamespace(data=pd.DataFrame({'Total<SEP>energy':[1.], 'Total<SEP>latency':[1.],
                            'Total<SEP>mapping':[broken if len(calls)==4 else lambda:object()]}))
    monkeypatch.setattr(common,'build',lambda *a,**k:None)
    monkeypatch.setattr(common,'make_pmappings',lambda *a,**k:None)
    monkeypatch.setattr(common,'join_pmappings',join)
    monkeypatch.setattr(common,'strict_evaluate',lambda *a,**k:dict(energy=1.,latency=1.,edp=1.))
    monkeypatch.setattr(common,'mapping_identity',lambda _: 'mapping')
    monkeypatch.setattr(common,'spatial_usage_shortfalls',lambda *a:[])
    monkeypatch.setattr(common,'rows_for_capacity',lambda data,*a:data)
    monkeypatch.setattr(bench,'input_signature',lambda _:[])
    monkeypatch.setattr(bench,'input_stats',lambda _: {})
    monkeypatch.setattr(bench,'live_frontiers',lambda data,caps:([[1.,1.]],[[1.,1.]]))
    output = tmp_path/'failed.json'
    monkeypatch.setattr('sys.argv',['benchmark','--case','counter','--count','2','--repeats','2','--output',str(output)])
    assert bench.main() == 2
    report = json.loads(output.read_text())
    assert len(calls) == 4  # three warmups, first measured run
    assert all(r['exact'] for r in report['runs'])
    assert report['runs'][-1]['repeat'] == 0
    assert not report['all_picks_valid']
    assert not report['runs'][-1]['picks_valid']
