from itertools import permutations
import random

from research.graph_structure.analyze import DAG, METRICS, exact, trace


def test_shared_input_and_fanout_are_not_edges():
    g = DAG({'X':10}, [('a',('X',),20,'op'), ('b',('a',),30,'op'),
                        ('c',('a','X'),40,'op'), ('d',('b','c'),5,'op')])
    assert g.live(1) == {'X','a'}
    assert g.cut(1) == (2,30,2)
    assert g.event_bytes(0,0) == 30
    assert g.live(g.full) == set()


def test_exact_against_independent_permutation_lifetime_oracle():
    rng = random.Random(73)
    for _ in range(12):
        ops=[]
        for i in range(6):
            args=tuple(x for x in ['X']+[f'n{j}' for j in range(i)] if rng.random()<.4) or ('X',)
            ops.append((f'n{i}', args, rng.randrange(1,100),'op'))
        g=DAG({'X':13},ops)
        best=[float('inf')]*4
        for order in permutations(range(6)):
            positions={g.ops[i][0]:p for p,i in enumerate(order)}
            if any(positions[x]>=positions[name] for name,args,_,_ in ops for x in args if x!='X'):
                continue
            intervals={}
            for x in g.sizes:
                uses=[positions[name] for name,args,_,_ in ops if x in args]
                birth=min(uses) if x=='X' else positions[x]
                intervals[x]=(birth,max(uses,default=birth))
            peak=[0]*4
            for p,i in enumerate(order):
                live={x for x,(start,end) in intervals.items() if start<=p<end}
                event={x for x,(start,end) in intervals.items() if start<=p<=end}
                edges=sum(positions[x]<=p<positions[name] for name,args,_,_ in ops for x in args if x!='X')
                values=(len(live),sum(g.sizes[x] for x in live),edges,sum(g.sizes[x] for x in event))
                peak=[max(a,b) for a,b in zip(peak,values)]
            best=[min(a,b) for a,b in zip(best,peak)]
        assert exact(g)['optimum']==dict(zip(METRICS,best))


def test_runtime_event_peak_agrees():
    from research.runtime.dag_cases import CASES
    from research.runtime.dag_model import lifetimes
    for factory in CASES.values():
        native=factory()
        g=DAG({x:native.rows*w*2 for x,w in native.inputs},
              [(o.name,o.inputs,native.rows*o.width*2,o.kind) for o in native.ops])
        peak,_=trace(g,list(range(len(g.ops))))
        expected=max(t.live_width for t in lifetimes(native,tuple(o.name for o in native.ops)))*native.rows*2
        assert peak['event_bytes']==expected


def test_limit_does_not_claim_optimum():
    g=DAG({'X':1},[('a',('X',),1,'op'),('b',('X',),1,'op')])
    assert exact(g,1)['optimum'] is None
