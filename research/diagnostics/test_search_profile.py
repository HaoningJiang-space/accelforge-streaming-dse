import pandas as pd
import sympy

from research.diagnostics.profile_3mm_search import numeric_frontier,SearchPhases
from research.diagnostics.search_repetition import Observations,freeze


def test_numeric_contract_keeps_resource_bits_only_in_ru_and_ignores_source_ties():
    frame=pd.DataFrame({'Total<SEP>energy':[1.,1.],'Total<SEP>latency':[2.,2.],
        'reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right':pd.Series([7,7],dtype='uint64'),
        'source':['a','b']})
    el=numeric_frontier(frame,False);ru=numeric_frontier(frame,True)
    assert len(el['columns'])==2 and len(ru['columns'])==3
    assert ru['values']['reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right']==[7]
    assert type(ru['values']['reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right'][0])is int


def test_observations_separate_cache_requests_from_actual_recomputation():
    seen=Observations();seen.add('key','a',10,True);seen.add('key','b',10,False)
    result=seen.summary()
    assert result['repeated_requests']==1 and result['repeated_actual_calls']==0
    assert result['keys_seen_at_multiple_targets']==1 and result['requested_rows']==20
    seen.add('key','c',10,True)
    assert seen.summary()['repeated_actual_rows']==10


def test_forensic_symbols_do_not_collapse_distinct_assumptions():
    assert freeze(sympy.Symbol('x',positive=True))!=freeze(sympy.Symbol('x',integer=True))


def test_phase_wrappers_restore_after_exception():
    from research.tracking_audit import common
    original=common.make_pmappings
    try:
        with SearchPhases():
            assert common.make_pmappings is not original
            raise RuntimeError('probe')
    except RuntimeError:pass
    assert common.make_pmappings is original


def test_filter_audit_counts_exact_gb_row_rejections_and_restores_native_method():
    from research.diagnostics.resource_filter_3mm import FilterAudit
    from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
    frame=pd.DataFrame({'resource_capacity_bits<SEP>GlobalBuffer':[80,80],
        'reservation<SEP>GlobalBuffer<SEP>0<SEP>right':[64,96],
        'Total<SEP>energy':[1.,2.],'Total<SEP>latency':[2.,1.]})
    state=PmappingDataframe(frame,2,2,skip_pareto=True)
    original=PmappingDataframe.limit_capacity
    with FilterAudit()as audit:state.limit_capacity(drop_valid_reservations=False)
    observed=audit.stats['other_outside_merge']
    assert observed['capacity_input_rows']==2
    assert observed['capacity_dropped_rows']==observed['gb_invalid_rows']==1
    assert len(state.data)==1 and PmappingDataframe.limit_capacity is original
