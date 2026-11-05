from pathlib import Path
import sys
import subprocess

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
