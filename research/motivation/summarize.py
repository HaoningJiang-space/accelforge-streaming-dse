"""Tie-aware architecture regret; stdlib only, no search or parameter fitting."""
import argparse
import json
import math
from pathlib import Path


def tied(rows):
    feasible=[r for r in rows if r.get('feasible')]
    if not feasible:
        return []
    value=min(r['edp'] for r in feasible)
    return [r for r in feasible if math.isclose(r['edp'],value,rel_tol=1e-9,abs_tol=0)]


def summarize(report):
    output=[]
    for cap in report['capacities']:
        points=[r for r in report['points'] if r['capacity_bytes']==cap]
        shapes=report.get('shapes',sorted({tuple(r['shape']) for r in points}))
        expected={(tuple(s),mode) for s in shapes for mode in ('graph','materialized')}
        actual={(tuple(r['shape']),r['mode']) for r in points}
        if not expected.issubset(actual):
            output.append(dict(capacity_bytes=cap,status='incomplete_grid'))
            continue
        graph={tuple(r['shape']):r for r in points if r['mode']=='graph' and r['feasible']}
        materialized=[r for r in points if r['mode']=='materialized' and r['feasible']]
        winners=tied(materialized)
        oracle=tied(list(graph.values()))
        if not winners or not oracle:
            output.append(dict(capacity_bytes=cap,status='no_feasible_selection'))
            continue
        missing=[r['shape'] for r in materialized if tuple(r['shape']) not in graph]
        violations=[r['shape'] for r in materialized if tuple(r['shape']) in graph
                    and graph[tuple(r['shape'])]['edp']>r['edp']*(1+1e-6)]
        if missing or violations:
            output.append(dict(capacity_bytes=cap,status='reference_inconsistency',missing=missing,violations=violations))
            continue
        best=oracle[0]['edp']
        regrets=[graph[tuple(r['shape'])]['edp']/best-1 for r in winners]
        near=[]
        for tolerance in (0.01,0.05):
            shortlist=[r for r in materialized if r['edp']<=winners[0]['edp']*(1+tolerance)]
            values=[graph[tuple(r['shape'])]['edp']/best-1 for r in shortlist]
            near.append(dict(relative_tolerance=tolerance,shapes=[r['shape'] for r in shortlist],
                             best_after_graph_remap=min(values),worst_selection_regret=max(values)))
        output.append(dict(capacity_bytes=cap,status='ok',
                           materialized_winners=[r['shape'] for r in winners],
                           graph_winners=[r['shape'] for r in oracle],
                           graph_reference_edp=best,
                           best_tie_regret=min(regrets),worst_tie_regret=max(regrets),
                           materialized_selection_edp=winners[0]['edp'],
                           near_tie_shortlists=near,
                           mode_search_seconds={mode:sum(r['seconds'] for r in points if r['mode']==mode)
                                                for mode in ('graph','materialized')}))
    return dict(case=report['case'],capacities=output,
                timing_scope='single pass; alternating mode order; shared process/JIT caches; not an amortization benchmark')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs',type=Path,nargs='+')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=[summarize(json.loads(p.read_text())) for p in args.inputs]
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
