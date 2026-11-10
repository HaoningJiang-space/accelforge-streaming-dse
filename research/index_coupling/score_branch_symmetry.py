"""Validate complete branch-orbit censuses; retain incomplete order searches."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import platform

from .fork_order_oracle import replay_private_boundary
from .graph.analysis import traffic_at
from .graph.branch_symmetry import branch_graph, continuation_ops, induced
from .graph.fork_quotient import Plan


# Independently counted stage/residency states and literal/stabilized orders.
EXPECTED = {
    'suffix_2_open': (81,45,2,121,241), 'suffix_2_join': (100,55,2,131,260),
    'root_2_open': (16,10,2,48,96), 'root_2_join': (16,10,2,48,96),
    'asymmetric_2': (8,8,1,24,24),
    'root_3_open': (1,1,6,15,0), 'root_3_join': (1,1,6,15,0),
}


def score(directory):
    directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text())
    errors,cases=[],[];replays=[];compared=0
    for spec in manifest['specs']:
        name=spec['name'];path=directory/f'{name}.json'
        if not path.exists():errors.append(dict(case=name,error='missing'));continue
        r=json.loads(path.read_text())
        if (r.get('spec')!=spec or r.get('source_sha256')!=manifest['source_sha256'] or
            r.get('revision')!=manifest['revision'] or r.get('hash_seed')!='0'):
            errors.append(dict(case=name,error='provenance mismatch'))
        if r['status']!='complete':errors.append(dict(case=name,error=r['status']))
        queries=r['queries'];coarse=defaultdict(set)
        for q in queries:
            replays.extend(q['replays'])
            if len(q['replays'])!=len(q['points']):errors.append(dict(case=name,error='incomplete replay'))
            if r['literal_reference']:
                compared+=1
                if q['equal'] is not True or q['reference_points']!=q['points']:
                    errors.append(dict(case=name,error='curve mismatch'))
            key=(tuple(sorted(q.get('progress',()))),
                 tuple(sum(t.startswith(role) for t in q['external']) for role in ('C','U','D','V')))
            coarse[key].add(tuple(map(tuple,q['points'])))
        counts=(len(queries),r['cache_entries'],r['automorphisms'],r['stats']['order_calls'],r['reference_stats']['order_calls'])
        if r['status']=='complete' and counts!=EXPECTED[name]:
            errors.append(dict(case=name,error='coverage/orbit count',actual=counts,expected=EXPECTED[name]))
        unique={(tuple(sorted(q['ops'])),tuple(sorted(q['external']))) for q in queries}
        if len(unique)!=len(queries):errors.append(dict(case=name,error='duplicate query'))
        cases.append(dict(case=name,status=r['status'],queries=len(queries),response_orbits=r['cache_entries'],
            automorphisms=r['automorphisms'],order_calls=r['stats']['order_calls'],
            literal_order_calls=r['reference_stats']['order_calls'],literal_reference=r['literal_reference'],
            distinct_numeric_curves=len({tuple(map(tuple,q['points'])) for q in queries}),
            coarse_classes=len(coarse),coarse_classes_with_unequal_curves=sum(len(v)>1 for v in coarse.values()),
            seconds=r['seconds'],replays=sum(len(q['replays']) for q in queries)))
    wrong=sum(not x['exact'] for x in replays)
    if wrong:errors.append(dict(error='replay mismatch',count=wrong))
    return dict(revision=manifest['revision'],statuses=dict(Counter(c['status'] for c in cases)),
                errors=errors,cases=cases,complete_literal_comparisons=compared,
                replays=len(replays),replay_failures=wrong)


def tuples(value):
    return tuple(tuples(x) for x in value) if isinstance(value,list) else value


def progress_certificate(directory):
    """Construct two new whole-suffix plans from already saved component plans.

This is attribution of a seen C=3 counterexample, not another prediction.
Only singleton root-group annotations may be stripped: child entry stays group.
    """
    rows=json.loads((Path(directory)/'suffix_2_open.json').read_text())['queries']
    def lookup(progress,external):
        return next(q for q in rows if tuple(q['progress'])==progress and set(q['external'])==set(external))
    graph=branch_graph();ops=continuation_ops(graph,(1,0));sub=induced(graph,ops)
    out=[]
    for resident in ('D0','D1'):
        components=[]
        for progress,ext in (((1,2),(resident,) if resident=='D0' else ()),
                             ((2,0),(resident,) if resident=='D1' else ())):
            row=lookup(progress,ext)
            i=min((i for i,p in enumerate(row['points']) if p[0]<=3),key=lambda i:row['points'][i][1])
            c,q=row['points'][i];saved=row['witnesses'][i]
            plan=Plan(tuples(saved['order']),tuples(saved['notes']))
            assert plan.notes[0]==('groups',(plan.order,),'kept',(),'via DRAM',())
            components.append((c,q,Plan(plan.order,plan.notes[1:])))
        order=tuple(o for _,_,p in components for o in p.order)
        note=('groups',tuple(p.order for _,_,p in components),'kept',(),'via DRAM',())
        plan=Plan(order,(note,)+tuple(n for _,_,p in components for n in p.notes))
        c=max(c for c,_,_ in components);q=sum(q for _,q,_ in components)
        actual=replay_private_boundary(sub,{resident},c,q,plan)
        optimal=traffic_at(3,lookup((1,0),(resident,))['points'])
        assert actual['exact'] and c==3 and q==optimal
        out.append(dict(external=[resident],component_costs=[[c,q] for c,q,_ in components],
                        capacity=c,traffic=q,equals_complete_oracle=True,
                        order=plan.order,witness=plan.notes,replay=actual))
    here=Path(__file__).parent
    return dict(scope='Post-hoc C=3 construction from saved component witnesses; no search.',
        python=platform.python_version(),execution_platform=platform.system(),
        input_sha256=hashlib.sha256((Path(directory)/'suffix_2_open.json').read_bytes()).hexdigest(),
        source_sha256={n:hashlib.sha256((here/n).read_bytes()).hexdigest() for n in (
            'score_branch_symmetry.py','graph/branch_symmetry.py','graph/fork_quotient.py',
            'fork_order_oracle.py','graph/model.py','simulate_nest.py')},certificates=out)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--certificate',action='store_true');args=p.parse_args()
    result=progress_certificate(args.directory) if args.certificate else score(args.directory)
    print(json.dumps(result,indent=2));return int(bool(result.get('errors')))


if __name__=='__main__':raise SystemExit(main())
