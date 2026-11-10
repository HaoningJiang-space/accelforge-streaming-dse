"""Score complete matched-grammar searches; keep missing/timeout/unreplayed distinct."""
import argparse
from collections import Counter
import json
from pathlib import Path

from .run_islands import ARMS,write


def cost(points,c):
    return min((q for p,q in points if p<=c),default=float('inf'))


def score(manifest,root):
    cases={};all_rows=[];errors=[]
    for case,ir in manifest['cases'].items():
        rows={}
        expected=[a for a in ARMS if a!='v2_oracle' or (ir['extent_cap'] is not None and len(ir['ops'])<=6)]
        for arm in expected:
            path=root/f'{case}__{arm}.json'
            if not path.exists():rows[arm]=dict(status='missing');continue
            d=json.loads(path.read_text());rows[arm]=d;all_rows.append(d)
            if (d['case']!=case or d['arm']!=arm or d['source_sha256']!=manifest['source_sha256']):
                errors.append(f'{case}/{arm}: identity mismatch')
            if d['status'] in ('complete','search_complete_unreplayed'):
                if d['byte_points']!=[[4*c,4*q] for c,q in d['points']]:errors.append(f'{case}/{arm}: byte conversion mismatch')
                if len(d['witnesses'])!=len(d['points']):errors.append(f'{case}/{arm}: missing witness')
            if d['status']=='complete':
                if len(d['replays'])!=len(d['points']) or not all(r['exact'] for r in d['replays']):
                    errors.append(f'{case}/{arm}: incomplete or inexact replay')
        complete={a:d for a,d in rows.items() if d['status'] in ('complete','search_complete_unreplayed')}
        equality={}
        for grammar in ('v1','v2'):
            wanted=[a for a in expected if a.startswith(grammar)]
            found=[complete[a] for a in wanted if a in complete]
            equality[grammar]=dict(requested=len(wanted),search_complete=len(found),
                equal=(all(d['points']==found[0]['points'] for d in found) if len(found)==len(wanted) else None),
                all_replayed=all(rows[a]['status']=='complete' for a in wanted))
            if equality[grammar]['equal'] is False:errors.append(f'{case}/{grammar}: frontier mismatch')
        dominance=None
        if 'v1_dp' in complete and 'v2_dp' in complete:
            a,b=complete['v1_dp']['points'],complete['v2_dp']['points']
            capacities={p for p,q in a+b}
            dominance=all(cost(b,c)<=cost(a,c) for c in capacities)
            if not dominance:errors.append(f'{case}: v2 fails to dominate v1')
        cases[case]=dict(statuses={a:d['status'] for a,d in rows.items()},equality=equality,
            v2_dominates_v1=dominance,scope='reduced' if ir['extent_cap'] else 'original extents',
            fx_ops=len(ir['fx_nodes']),ir_ops=len(ir['ops']),scalar_steps=ir['scalar_steps'],
            complete_rows={a:dict(seconds=d['search_seconds'],peak_rss_bytes=d['peak_rss_bytes'],
                response_entries=sum(d['stats'][s+'_cache']['currsize'] for s in ('solve','group')),
                points=len(d['points']),c2=d['c2_stats']) for a,d in complete.items()})
    return dict(cases=cases,status_counts=dict(Counter(d['status'] for d in all_rows)),
        exact_replays=sum(len(d.get('replays',[])) for d in all_rows if d['status']=='complete'),
        errors=errors,all_requested_execution_validated=all(c['equality'][g]['all_replayed'] for c in cases.values() for g in ('v1','v2')))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--results',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    out=score(json.loads(args.manifest.read_text()),args.results);write(args.out,out)
    print(json.dumps({k:out[k] for k in ('status_counts','exact_replays','errors','all_requested_execution_validated')}))
    if out['errors']:raise SystemExit(1)


if __name__=='__main__':main()
