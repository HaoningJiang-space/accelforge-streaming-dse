from fractions import Fraction
from itertools import product
from pathlib import Path
import ast
import pytest
from research.symbolic_fusion.model import Family, State, combine, dominates, frontier
from research.symbolic_fusion.oracle import execute
from research.symbolic_fusion.eliminate import eliminate, flat


def vectors(result):
    return {s.vector for s, _ in result}


@pytest.mark.parametrize('n,stripes,tiles', [(4,(2,4),(1,2)), (8,(4,8),(2,4))])
def test_scalar_all_plans(n, stripes, tiles):
    f = Family(n, stripes, tiles)
    for p in f.plans():
        out = execute(n, p.stripe, p.tiles, numeric=True)
        states = [f.factor(i,p.stripe,*t) for i,t in enumerate(p.tiles)]
        assert max(s.peak for s in states) == out['peak']
        assert sum(s.energy for s in states) == out['energy']
        assert sum((s.latency for s in states), Fraction(0)) == out['latency']


@pytest.mark.parametrize('capacity', [None, 128*1024, 132*1024, 102400-1, 102400])
def test_search_differential_and_order(capacity):
    f=Family(); a,_=flat(f,capacity); b,_=eliminate(f,capacity); c,_=eliminate(f,capacity,reverse=True)
    assert vectors(a)==vectors(b)==vectors(c)
    for state, plan in b:
        observed=execute(f.n,plan.stripe,plan.tiles)
        assert state.vector == (observed['peak'],observed['energy'],observed['latency'])


def test_all_local_dominance_continuations():
    f=Family()
    checked=0
    for stripe in f.stripes:
        factors=[[f.factor(i,stripe,*t) for t in f.legal_tiles(i,stripe)] for i in range(3)]
        for i, alternatives in enumerate(factors):
            kept=frontier(alternatives)
            for q in alternatives:
                if q in kept:
                    continue
                p=next(p for p in kept if dominates(p,q))
                for other in product(*(factors[j] for j in range(3) if j!=i)):
                    left=p; right=q
                    for r in other:
                        left=combine(left,r); right=combine(right,r)
                    assert dominates(left,right)
                    checked+=1
    assert checked>0


def test_constructor_and_search_have_no_native_dependency():
    # Both the search and independent oracle must remain free of native model
    # calls; validate imports as well as runtime module dependencies.
    root=Path(__file__).resolve().parents[1]
    for name in ('model.py','eliminate.py','oracle.py'):
        tree=ast.parse((root/name).read_text())
        imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        imports += [a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
        assert not any(m and (m.startswith('accelforge') or m.startswith('research.diagnostics') or m.startswith('research.tracking')) for m in imports)
    oracle=ast.parse((root/'oracle.py').read_text())
    assert not any(isinstance(n,ast.ImportFrom) and n.module in ('model','eliminate') for n in ast.walk(oracle))
    f=Family()
    assert f.factor_calls==0
    assert all(not ('Float' in str(type(expr))) for c in f.counts for expr in c)
    _,stats=eliminate(f)
    assert stats['factor_evaluations'] < len(list(f.plans()))


def test_native_thresholds_from_independent_events():
    f=Family(); tiles=((64,64),)*3
    for stripe,peak in ((128,116*1024),(256,132*1024)):
        out=execute(256,stripe,tiles)
        assert out['peak']==peak
    _,s=eliminate(f,128*1024)
    assert s['skipped_stripes']==[256]


@pytest.mark.parametrize('kwargs',[dict(n=3),dict(stripes=(0,)),dict(tiles=(128,)),dict(stripes=(64,64))])
def test_family_rejects_invalid_domain(kwargs):
    with pytest.raises(ValueError):
        Family(**kwargs)


def test_symbolic_external_effect_before_any_evaluation():
    f=Family(); N,s,k,j=f.symbols; x,y,z=f.obligations
    assert f.factor_calls==0
    assert int(f.effect.subs({N:256,s:128,k:64,j:64,x:65536,y:102400,z:86016}))==118784
    assert int(f.effect.subs({N:256,s:256,k:64,j:64,x:65536,y:135168,z:86016}))==135168
    a,_=flat(f,cache_factors=True);b,_=eliminate(f)
    assert vectors(a)==vectors(b)


def test_equal_bound_peak_does_not_imply_equal_future_effect():
    from research.symbolic_fusion.model import Effect
    # Both are 120 at x=64; the order reverses away from that single point.
    a=Effect(120,10); b=Effect(70,56)
    assert a.at(64)==b.at(64)==120
    assert a.at(0)>b.at(0) and a.at(200)<b.at(200)
    assert not a.no_larger_than(b) and not b.no_larger_than(a)


def test_effect_dominance_all_external_obligations():
    from research.symbolic_fusion.model import Effect
    effects=[Effect(p,r)for p in range(5)for r in [None,*range(p+1)]]
    for a,b in product(effects,repeat=2):
        # x=10 passes every breakpoint (<=4); the proof also checks slope.
        assert a.no_larger_than(b)==all(a.at(x)<=b.at(x)for x in range(11))


def test_family_elimination_keeps_correlated_resource_effect():
    f=Family()
    for s in f.stripes:
        factors=[[f.factor(i,s,*t)for t in f.legal_tiles(i,s)]for i in range(3)]
        for alternatives in factors:
            kept=frontier(alternatives)
            for q in alternatives:
                p=next(p for p in kept if dominates(p,q))
                for x in (0,1,64*1024,128*1024,2**40):
                    assert p.effect.at(x)<=q.effect.at(x)


def test_event_effect_matches_symbolic_summary():
    from dataclasses import asdict
    f=Family(4,(2,4),(1,2))
    for plan in f.plans():
        total=State(0,0,Fraction(0),())
        for i,t in enumerate(plan.tiles):
            total=combine(total,f.factor(i,plan.stripe,*t))
        actual=execute(f.n,plan.stripe,plan.tiles)
        assert asdict(total.effect)==actual['effect']
