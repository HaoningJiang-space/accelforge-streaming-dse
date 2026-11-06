from fractions import Fraction
from itertools import product
import pytest
from research.symbolic_fusion.model import Plan
from research.symbolic_fusion.residency_search import Factors,compile_search,queries,CONTEXTS,Node,add,weak,covers,conditional_frontier
from research.symbolic_fusion.residency_oracle import execute


@pytest.mark.parametrize('n',[4,8])
def test_two_contexts_scalar_and_correlated_costs(n):
    f=Factors(n,(n//2,n),(n//4,n//2))
    for plan in f.base.plans():
        for ci,c in enumerate(CONTEXTS):
            r=execute(n,plan.stripe,plan.tiles,numeric=True,context=c)
            expected=(0,0,Fraction(0))
            for i,t in enumerate(plan.tiles):expected=add(expected,f.get(i,plan.stripe,t)[ci])
            assert expected==(r['peak'],r['energy'],r['latency'])
            expected_versions=(n//plan.tiles[1][0])*(n//plan.tiles[1][1])if c=='dram' else 0
            assert r['dram_version_writes']==expected_versions


def test_modes_preserve_each_environment_and_shared_queries():
    compiled={}
    for mode in ('cached_flat','grounded','conditional'):
        f=Factors();r,stats=compile_search(f,mode)
        assert f.tiles==(32,64) and f.stripes==(64,128,256)
        assert stats['factor_pairs']==28
        for i,(shape,c)in enumerate(f.envs):
            for v,p in r[i]:
                assert all(j<=shape[0]and k<=shape[1]for k,j in p.tiles)
        compiled[mode]=({i:{v for v,_ in rows}for i,rows in r.items()},
                        {k:{v for v,_ in rows}for k,rows in queries(r,f).items()})
    assert compiled['cached_flat']==compiled['grounded']==compiled['conditional']


def test_real_context_pruning_cannot_be_reused_as_one_grounded_frontier():
    f=Factors();s=64
    q=((32,32),(32,32),(32,32));p=((32,32),(64,32),(32,32))
    observations={}
    for c in CONTEXTS:
        observations[c]=[execute(256,s,t,context=c)for t in (p,q)]
    assert weak(observations['gb'][0]['prefix'],observations['gb'][1]['prefix'])
    assert not weak(observations['dram'][0]['prefix'],observations['dram'][1]['prefix'])
    # A legal, unchanged suffix exposes the tradeoff in the complete execution.
    assert observations['dram'][1]['peak']==25*1024
    assert observations['dram'][0]['peak']==26*1024
    assert observations['dram'][1]['energy']>observations['dram'][0]['energy']


def test_all_shared_prefix_prunes_have_every_legal_continuation():
    f=Factors();checked=0
    for s in f.stripes:
        nodes=[]
        for a,b in product(f.options(0,s),f.options(1,s)):
            left=f.local(0,s,a);right=dict(f.local(1,s,b).outcomes)
            nodes.append(Node(tuple((i,add(v,right[i]))for i,v in left.outcomes if i in right),(a,b)))
        kept=conditional_frontier(nodes)
        for q in nodes:
            p=next(p for p in kept if covers(p,q))
            for t in f.options(2,s):
                tail=dict(f.local(2,s,t).outcomes);pv=dict(p.outcomes)
                for i,qv in q.outcomes:
                    if i in tail:
                        assert i in pv and weak(add(pv[i],tail[i]),add(qv,tail[i]))
                        checked+=1
    assert checked>0


def test_oracle_rejects_unknown_context():
    with pytest.raises(ValueError):execute(4,2,((1,1),)*3,context='free_zero_x')


def test_no_native_or_posthoc_calls_in_context_compilation():
    import ast
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    for name in ('residency_search.py','residency_oracle.py'):
        tree=ast.parse((root/name).read_text())
        imports=[n.module for n in ast.walk(tree)if isinstance(n,ast.ImportFrom)]
        imports += [a.name for n in ast.walk(tree)if isinstance(n,ast.Import)for a in n.names]
        assert not any(m and m.startswith(('accelforge','research.diagnostics','research.tracking'))for m in imports)
    f=Factors()
    assert f.evaluations==f.base.factor_calls==0
