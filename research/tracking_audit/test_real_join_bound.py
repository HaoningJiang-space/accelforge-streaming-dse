from fractions import Fraction
import numpy as np
import pandas as pd
import pytest

from research.tracking_audit.audit_real_join_bound import ENERGY, LATENCY, group_bound


@pytest.mark.parametrize('dtype_left,dtype_right',[(a,b) for a in ('float32','float64') for b in ('float32','float64')])
def test_real_join_group_bound_under_rounded_addition(dtype_left,dtype_right):
    left = pd.DataFrame({ENERGY:np.array([1e-12,2e-12],dtype=dtype_left),
                         LATENCY:np.array([2e-9,1e-9],dtype=dtype_left)})
    right = pd.DataFrame({ENERGY:np.array([3e-12,1e-12],dtype=dtype_right),
                          LATENCY:np.array([1e-9,4e-9],dtype=dtype_right)})
    bound = group_bound(left,right)
    for _,a in left.iterrows():
        for _,b in right.iterrows():
            dtype = np.float32 if dtype_left==dtype_right=='float32' else np.float64
            energy = dtype(dtype(a[ENERGY]) + dtype(b[ENERGY]))
            latency = dtype(dtype(a[LATENCY]) + dtype(b[LATENCY]))
            assert bound <= Fraction.from_float(float(energy))*Fraction.from_float(float(latency))


@pytest.mark.parametrize('bad',[np.nan,np.inf,-1.])
def test_unsupported_costs_fail_closed(bad):
    good = pd.DataFrame({ENERGY:[1.],LATENCY:[1.]})
    other = pd.DataFrame({ENERGY:[bad],LATENCY:[1.]})
    with pytest.raises(ValueError):
        group_bound(good,other)


def test_empty_and_unsupported_dtype_fail_closed():
    good = pd.DataFrame({ENERGY:[1.],LATENCY:[1.]})
    with pytest.raises(ValueError):
        group_bound(good,good.iloc[:0])
    with pytest.raises(ValueError):
        group_bound(good,pd.DataFrame({ENERGY:[1],LATENCY:[1]}))
