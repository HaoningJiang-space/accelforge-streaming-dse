"""Post-hoc ledger diagnostics from saved P21d witnesses; no curve search.

The symbolic witness ledger is compared with the independently executed cell
transactions saved by the frozen run. It does not repair or re-score that run.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from research.index_coupling.graph.model import residual
from research.index_coupling.score_p21d import score
from research.index_coupling.simulate_nest import Specification, parse_witness


def tuples(value):
    return tuple(tuples(x) for x in value) if isinstance(value,list) else value


def ledger(graph,witness,inherit_final_writes=False):
    spec=Specification(graph)
    root=parse_witness(spec,tuples(witness))
    reads=Counter({t:len(spec.cells({t},spec.bounds)) for t in spec.inputs})
    writes=Counter({t:len(spec.cells({t},spec.bounds)) for t in spec.outputs})
    consumed={t for op in spec.ops for t in spec.inputs_of[op]}
    writes_at=[]
    def walk(node,bounds,multiplier,depth,owned):
        if node.kind=='groups':
            child_owned=set(owned)
            for t in node.dropped:
                users=[c for c in node.children if t in spec.tensors(c.ops)]
                writers=[c for c in users if any(spec.output_of[op]==t for op in c.ops)]
                size=len(spec.cells({t},bounds))*multiplier
                if writers and t in consumed:
                    charge=0 if inherit_final_writes and t in owned else size
                    writes[t]+=charge;reads[t]+=size*(len(users)-len(writers))
                    child_owned.add(t)
                    writes_at.append(dict(tensor=t,charged_write=charge,
                                          inherited_final_write=bool(inherit_final_writes and t in owned),depth=depth,
                                          span=node.ops,groups=[c.ops for c in node.children],
                                          extents={v:len(b) for v,b in bounds.items()},repeat=multiplier))
                elif writers:
                    reads[t]+=size*(len(writers)-1);writes[t]+=size*(len(writers)-1)
                else:
                    reads[t]+=size*(len(users)-1)
            for child in node.children:
                walk(child,bounds,multiplier,depth+1,frozenset(child_owned))
        elif node.kind=='loop':
            trips=len(bounds[node.variable])//node.tile
            for t in node.dropped:
                extra=(trips-1)*len(spec.cells({t},bounds))*multiplier
                reads[t]+=extra
                if any(spec.output_of[op]==t for op in node.ops):
                    writes[t]+=extra
            inner=dict(bounds,**{node.variable:range(node.tile)})
            walk(node.children[0],inner,multiplier*trips,depth+1,owned)
    walk(root,spec.bounds,1,0,frozenset())
    return dict(reads=dict(sorted(reads.items())),writes=dict(sorted(writes.items())),
                traffic=sum(reads.values())+sum(writes.values()),group_write_charges=writes_at)


def diagnose(directory):
    scored=score(directory)
    mismatches=[]
    for bad in scored['replay_mismatches']:
        r=json.loads((directory/f"{bad['case']:02d}_{bad['arm']}.json").read_text())
        p=next(p for p in r['points'] if p[:2]==bad['predicted'])
        e=next(e for e in r['replays'] if [e['capacity'],e['traffic']]==bad['predicted'])
        graph=residual(*r['shape'],r['depth'],r['reads_x'])
        counted=ledger(graph,p[2]);assert counted['traffic']==p[1]
        diffs={direction:{t:counted[direction].get(t,0)-e['actual'][direction].get(t,0)
                          for t in set(counted[direction])|set(e['actual'][direction])
                          if counted[direction].get(t,0)!=e['actual'][direction].get(t,0)}
               for direction in ('reads','writes')}
        mismatches.append(dict(**bad,model_ledger=counted,execution=e['actual'],model_minus_execution=diffs))
    first=scored['counterexamples'][0] if scored['counterexamples'] else None
    if first:
        traces={}
        for arm in ('structural','unrestricted'):
            r=json.loads((directory/f"{first['case']:02d}_{arm}.json").read_text())
            p=min((p for p in r['points'] if p[0]<=first['capacity']),key=lambda p:(p[1],p[0]))
            e=next(e for e in r['replays'] if (e['capacity'],e['traffic'])==tuple(p[:2]))
            traces[arm]=dict(point=p[:2],actual=e['actual'],witness=p[2])
        first=dict(counterexample=first,arms=traces)
    checked=0;default_bad=[];inherited_bad=[]
    for path in sorted(directory.glob('[0-9][0-9]_*.json')):
        record=json.loads(path.read_text())
        graph=residual(*record['shape'],record['depth'],record['reads_x'])
        for p,e in zip(record.get('points',[]),record.get('replays',[])):
            checked+=1
            current=ledger(graph,p[2])
            proposed=ledger(graph,p[2],inherit_final_writes=True)
            if current['traffic']!=p[1]:
                default_bad.append([record['case'],record['arm'],p[:2],current['traffic']])
            if any(proposed[k]!=e['actual'][k] for k in ('reads','writes','traffic')):
                inherited_bad.append([record['case'],record['arm'],p[:2],proposed['traffic'],e['actual']['traffic']])
    return dict(kind='post-hoc analysis of unchanged frozen records',first_clean_counterexample=first,
                accounting_mismatches=mismatches,
                final_write_ownership_probe=dict(checked=checked,default_ledger_mismatches=default_bad,
                    proposed_ledger_mismatches=inherited_bad,
                    scope='Reprices saved witnesses only. No solver or frozen result changed; no reoptimization.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    print(json.dumps(diagnose(parser.parse_args().directory),indent=2,allow_nan=False))
