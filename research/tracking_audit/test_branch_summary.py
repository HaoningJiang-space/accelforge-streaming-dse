from dataclasses import FrozenInstanceError
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

from accelforge.mapper.FFM._join_pmappings.branch_summary import BranchSummary, ENERGY, LATENCY
from research.tracking_audit.audit_real_join_bound import group_bound


@pytest.mark.parametrize('left_dtype,right_dtype',[(a,b) for a in ('float32','float64') for b in ('float32','float64')])
def test_summary_matches_original_cost_bound_and_is_immutable(left_dtype,right_dtype):
    left=pd.DataFrame({ENERGY:np.array([1e-12,2e-12],dtype=left_dtype),
                       LATENCY:np.array([2e-9,1e-9],dtype=left_dtype)})
    right=pd.DataFrame({ENERGY:np.array([3e-12,1e-12],dtype=right_dtype),
                        LATENCY:np.array([1e-9,4e-9],dtype=right_dtype)})
    summary=BranchSummary.from_frames(left,right,{'T1'})
    assert summary.edp_lower == group_bound(left,right)
    assert isinstance(summary.edp_lower,Fraction) and summary.shared_tensors==('T1',)
    assert summary.matched_pairs is None
    assert summary.working_set_lower_bits is None and summary.unsupported_reason is None
    with pytest.raises(FrozenInstanceError):
        summary.left_rows=99


@pytest.mark.parametrize('bad',[np.nan,np.inf,-1.])
def test_unsupported_objectives_yield_unknown_bound(bad):
    good=pd.DataFrame({ENERGY:[1.],LATENCY:[1.]})
    other=pd.DataFrame({ENERGY:[bad],LATENCY:[1.]})
    result=BranchSummary.from_frames(good,other,{'T1'})
    assert result.edp_lower is None and result.working_set_lower_bits is None
    assert result.unsupported_reason


def test_missing_empty_and_unsupported_columns_are_unknown():
    good=pd.DataFrame({ENERGY:[1.],LATENCY:[1.]})
    for bad in (good.iloc[:0],pd.DataFrame({ENERGY:[1.]}),pd.DataFrame({ENERGY:[1],LATENCY:[1]})):
        result=BranchSummary.from_frames(good,bad)
        assert result.edp_lower is None and result.unsupported_reason


def test_real_ffm_observer_is_read_only_and_final_two_einsum_only():
    from research.tracking_audit import common
    from research.tracking_audit.shape_capacity_audit import build
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    case=common.Case('matmuls','nvdla',(2,2,4))
    spec=build(case,(4,8),128,common.RU)
    groups=common.make_pmappings(spec,print_number_of_pmappings=False)
    summaries=[]
    observed=common.join_pmappings(groups,_terminal_branch_observer=summaries.append)
    spec2=build(case,(4,8),128,common.RU)
    reference=common.join_pmappings(common.make_pmappings(spec2,print_number_of_pmappings=False))
    assert summaries and all(isinstance(s,BranchSummary) for s in summaries)
    assert all(s.working_set_lower_bits is None for s in summaries)
    def frontier(data):
        cols=['Total<SEP>energy',common.LATENCY,'reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right']
        return sorted(map(tuple,data[cols].to_numpy().tolist()))
    assert frontier(observed.data)==frontier(reference.data)
