"""Enumerate the asymmetric counterexample and audit the old strong baseline."""
import json
from pathlib import Path
from research.graph_structure.analyze import cases, trace, greedy, lookahead


def all_orders(g, done=0, order=()):
    if done == g.full:
        yield order
    for i in g.ready(done):
        yield from all_orders(g, done | (1 << i), order + (i,))


def run():
    g=next(g for name, _, g in cases() if name == 'native_asymmetric')
    def record(order):
        peaks, rows=trace(g,order)
        return dict(order=[g.ops[i][0] for i in order],peaks=peaks,trace=rows)
    schedules=[record(order) for order in all_orders(g)]
    done=(1 << 0) | (1 << 3)  # Stem, Narrow
    decisions=[]
    for i in g.ready(done):
        completions=[record((0,3,i)+tail) for tail in all_orders(g,done | (1<<i))]
        decisions.append(dict(next=g.ops[i][0],immediate_bytes=g.event_bytes(done,i),
                              best_completion_bytes=min(r['peaks']['event_bytes'] for r in completions)))
    old=json.loads(Path('research/graph_structure/results/local.json').read_text())['cases']
    solved=[c for c in old if c['solution']['status']=='exact']
    baseline=dict(exact_cases=len(solved),
                  original_optimal=sum(c['baseline']['event_bytes']==c['solution']['optimum']['event_bytes'] for c in solved),
                  event_greedy_optimal=sum(c['greedy'][3]['event_bytes']==c['solution']['optimum']['event_bytes'] for c in solved),
                  portfolio_optimal=sum(min(r['event_bytes'] for r in c['greedy'])==c['solution']['optimum']['event_bytes'] for c in solved))
    result=dict(graph=dict(inputs=g.inputs,ops=g.ops),all_schedules=schedules,
                greedy=[record(greedy(g,j)) for j in range(4)],
                lookahead_2=record(lookahead(g,2)),after_stem_narrow=decisions,
                previous_suite_event_baseline=baseline)
    path=Path('research/graph_structure/results/asymmetric_audit.json')
    path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(baseline=baseline,decisions=decisions,lookahead=result['lookahead_2']['peaks']),indent=2))


if __name__=='__main__':
    run()
