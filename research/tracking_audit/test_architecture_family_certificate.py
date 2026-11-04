from fractions import Fraction
from itertools import product
import random

import pytest

from research.tracking_audit.architecture_family_certificate import ArchitectureBox, certify_family
from research.tracking_audit.graph_cut_bound import Architecture, Branch, Model, branch_bound, complete_cost


def points(box):
    return (Architecture(*p) for p in product(*(range(lo,hi+1) for lo,hi in box.ranges)))


def test_one_certificate_covers_all_four_architecture_axes_without_sampling():
    model = Model(128,192,1,4)
    box = ArchitectureBox(((2,3),(4,6),(32,36),(2,3)))
    seed = Branch('stream',4,2,0,False)
    branch = Branch('barrier',64,24,0,True)
    certificate = certify_family(model,box,branch,seed,0)
    assert certificate['status']=='certified' and certificate['architectures']==60
    assert certificate['corner_evaluations']==2
    for arch in points(box):
        assert box.contains(arch)
        upper = complete_cost(model,arch,seed,0)
        lower = branch_bound(model,arch,branch)
        assert upper <= lower <= complete_cost(model,arch,branch,0)
        for extra in (0,1,13,27):
            assert upper <= complete_cost(model,arch,branch,extra)


def test_family_proof_calls_only_two_corner_bounds():
    from unittest.mock import patch
    from research.tracking_audit import architecture_family_certificate as module
    box = ArchitectureBox(((2,3),(4,6),(32,36),(2,3)))
    model = Model(128,192,1,4)
    seed, branch = Branch('stream',4,2,0,False),Branch('barrier',64,24,0,True)
    with patch.object(module,'complete_cost',wraps=module.complete_cost) as upper, \
         patch.object(module,'branch_bound',wraps=module.branch_bound) as lower:
        result = certify_family(model,box,branch,seed,0)
    assert result['status']=='certified'
    assert upper.call_count==lower.call_count==1


def test_infeasible_seed_and_branch_are_not_mistaken_for_valid_incumbents():
    model = Model(128,192,1,4)
    box = ArchitectureBox(((2,3),(4,6),(4,6),(2,3)))
    seed = Branch('seed',4,2,0,False)
    branch = Branch('candidate',100,1,0,False)
    assert certify_family(model,box,branch,seed,0)['status']=='unproven'
    valid_seed = Branch('valid',1,1,0,False)
    assert certify_family(model,box,branch,valid_seed,0)['status']=='infeasible_branch'
    with pytest.raises(ValueError):
        certify_family(model,box,branch,valid_seed,0,Fraction(-1,10))


@pytest.mark.parametrize('ranges', [((1,2),),((1,2),(1,2),(1,2),(0,1)),
                                    ((2,1),(1,2),(1,2),(1,2)),
                                    ((1,2),(1,2),(1,2),(1,True))])
def test_invalid_boxes_are_rejected(ranges):
    with pytest.raises(ValueError):
        ArchitectureBox(ranges)


def test_randomized_exhaustive_checks_monotonic_certificate_and_epsilon():
    rng = random.Random(1867)
    for _ in range(300):
        ranges = []
        for _ in range(4):
            low = rng.randint(1,8)
            ranges.append((low,low+rng.randint(0,2)))
        box = ArchitectureBox(tuple(ranges))
        model = Model(*(rng.randint(1,100) for _ in range(4)))
        seed = Branch('seed',rng.randint(0,10),rng.randint(0,8),rng.randint(0,25),bool(rng.getrandbits(1)))
        branch = Branch('branch',rng.randint(0,20),rng.randint(0,8),rng.randint(0,25),bool(rng.getrandbits(1)))
        for epsilon in (Fraction(0),Fraction(1,20)):
            result = certify_family(model,box,branch,seed,0,epsilon)
            for arch in points(box):
                value = complete_cost(model,arch,seed,0)
                lower = branch_bound(model,arch,branch)
                if result['status']=='infeasible_branch':
                    assert lower is None
                elif result['status']=='certified':
                    assert value is not None
                    assert value <= Fraction(result['upper'])
                    if lower is not None:
                        assert lower >= Fraction(result['lower'])
                        for extra in (0,5):
                            assert value <= (1+epsilon)*complete_cost(model,arch,branch,extra)
