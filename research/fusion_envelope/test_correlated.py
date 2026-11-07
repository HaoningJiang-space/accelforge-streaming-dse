from fractions import Fraction as F
from itertools import product

from .correlated import minimum_product


def test_support_line_preserves_joint_tradeoff_instead_of_multiplying_independent_minima():
    value,e,t = minimum_product(F(1),F(1),[(F(1),F(5))])
    assert value==4 and e+t==5


def test_multiple_lines_bound_every_feasible_grid_point():
    lines = [(F(1,2),F(4)),(F(2),F(6))]
    bound,_,_ = minimum_product(F(1),F(1),lines)
    for e,t in product(range(1,21),repeat=2):
        if all(e+w*t>=v for w,v in lines):
            assert e*t>=bound


def test_axes_and_zero_weight_do_not_create_a_false_positive_lower_bound():
    assert minimum_product(F(),F(),[(F(1),F(5))])[0]==0
    assert minimum_product(F(1),F(2),[(F(),F(3))])[0]==6
