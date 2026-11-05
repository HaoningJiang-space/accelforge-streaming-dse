import numpy as np
import pandas as pd
import sympy

from research.diagnostics.counterfactual_trace import frozen_frame
from research.diagnostics.classify_counterfactuals import restore,strict_front,separated_costs


def test_counterfactual_front_preserves_equal_sources_and_all_resource_coordinates():
    vectors=np.array([[1.,1.,10.,8.],[1.,1.,10.,8.],[2.,2.,9.,8.],[2.,2.,10.,8.]])
    assert strict_front(vectors).tolist()==[True,True,True,False]


def test_restricted_context_winner_does_not_prove_universal_context_dominance():
    # A singleton restricted context is efficient by construction, while a
    # different recorded continuation dominates it globally.
    q=np.array([[5.,5.,10.,8.]])
    p=np.array([[4.,4.,9.,8.]])
    assert strict_front(q).tolist()==[True]
    assert strict_front(np.concatenate([q,p])).tolist()==[False,True]


def test_same_producers_and_additive_costs_can_change_dominance_when_future_peak_masks_resource_difference():
    # The competing producer set is fixed. Only the future resource changes.
    p,q=(1.,1.,10.,8.),(2.,2.,5.,8.)
    small=np.array([p,q])
    large=np.array([[p[0],p[1],max(p[2],12),8.],[q[0],q[1],max(q[2],12),8.]])
    assert strict_front(small).tolist()==[True,True]
    assert strict_front(large).tolist()==[True,False]


def test_trace_normalizes_exact_object_metadata_without_losing_high_bits():
    frame=pd.DataFrame({'capacity':pd.Series([sympy.Integer(2**63+7)],dtype=object),
        'energy':np.array([.25],dtype=np.float32)})
    record=frozen_frame(frame);back=restore(record)
    assert int(back['capacity'].iloc[0])==2**63+7
    assert back['energy'].dtype==np.dtype('float32')
    assert record['native_dtypes']['capacity']=='object'


def test_margin_filter_does_not_label_one_ulp_cost_tie_as_separated():
    q=[float(np.nextafter(np.float32(1),np.float32(2))),1.,5.,8.]
    p=[1.,1.,10.,8.]
    assert not separated_costs(q,p,q,p)
    q[0]=1.01
    assert separated_costs(q,p,q,p)
