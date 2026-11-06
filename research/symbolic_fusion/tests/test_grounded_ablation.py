import pytest
from research.symbolic_fusion.model import Family
from research.symbolic_fusion.eliminate import eliminate,flat


@pytest.mark.parametrize('capacity',[None,128*1024,132*1024,116*1024-1,116*1024])
def test_grounded_matches_cached_and_universal(capacity):
    f=Family();a,ast=eliminate(f,capacity,grounded=True)
    b,bst=eliminate(f,capacity);c,_=flat(f,capacity,cache_factors=True)
    assert {s.vector for s,_ in a}=={s.vector for s,_ in b}=={s.vector for s,_ in c}
    assert ast['root_materializations']<=bst['root_materializations']
    assert ast['factor_evaluations']==bst['factor_evaluations']


def test_grounded_does_not_claim_universal_reuse():
    with pytest.raises(ValueError):eliminate(Family(),conditional=True,grounded=True)
