from fractions import Fraction as F
from itertools import product
from types import SimpleNamespace

import sympy as sp
import pytest

from .linear_relaxation import Relaxation, Affine, power_two


def test_discrete_cost_and_capacity_dual_bound_covers_every_native_integer_tile():
    x,y = sp.symbols('x y',positive=True)
    model = Relaxation((x,y),{x:16,y:16})
    model.constrain(model.lower(x*y),4,parameter=('memory','GlobalBuffer'))
    objective = model.lower(128/x + 64/y - 2*x + 3)
    point = SimpleNamespace(px=4,py=4,capacity_bytes=4)
    cert = model.solve(objective,point)
    assert not cert['infeasible']
    exact = min(F(128,a)+F(64,b)-2*a+3 for a,b in product((1,2,4,8,16),repeat=2) if a*b<=36)
    checked,residual = model.check_dual(objective,cert['dual'],point)
    assert checked == cert['bound'] <= exact
    # Reusing the same dual at another SRAM size remains a valid lower bound.
    other = SimpleNamespace(px=4,py=4,capacity_bytes=8)
    exact_other = min(F(128,a)+F(64,b)-2*a+3 for a,b in product((1,2,4,8,16),repeat=2) if a*b<=68)
    assert model.check_dual(objective,cert['dual'],other)[0] <= exact_other


def test_integer_secants_bound_powers_outside_their_adjacent_interval():
    for k,z in product(range(-5,6),repeat=2):
        assert power_two(k)*(z-k+1) <= power_two(z)


def test_residual_correction_repairs_an_inexact_solver_dual():
    x = sp.Symbol('x',positive=True)
    model = Relaxation((x,),{x:16})
    objective = Affine(F(),{0:F(-1)})
    model.finalize()
    point = SimpleNamespace(px=1,py=1,capacity_bytes=1)
    # Zero dual violates c_x=-1, but subtracting residual*U gives exact -4.
    bound,residual = model.check_dual(objective,(F(),),point)
    assert bound == -4 and residual == 4


def test_infeasibility_needs_an_exact_positive_contradiction():
    x = sp.Symbol('x',positive=True)
    model = Relaxation((x,),{x:4})
    model.constrain(Affine(F(),{0:F(-1)}),-3)
    point = SimpleNamespace(px=1,py=1,capacity_bytes=1)
    cert = model.solve(Affine(F(),{0:F(1)}),point)
    assert cert['infeasible'] and cert['contradiction'] > 0


def test_constant_cost_proxy_has_no_symbolic_decisions():
    model = Relaxation((),{})
    point = SimpleNamespace(px=1,py=1,capacity_bytes=1)
    cert = model.solve(Affine(F(5),{}),point)
    assert cert['bound'] == 5 and not cert['infeasible']


def test_negative_max_cannot_use_a_nonnegative_auxiliary():
    x = sp.Symbol('x',positive=True)
    model = Relaxation((x,),{x:16})
    with pytest.raises(ValueError,match='nonnegative Max'):
        model.lower(sp.Max(-x,-2*x,evaluate=False))
