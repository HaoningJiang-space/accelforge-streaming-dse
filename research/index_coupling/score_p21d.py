"""Score frozen P21d without merging model-invalid cases into equality failures."""
import argparse
import json
from pathlib import Path

from research.index_coupling.run_p21 import comparison, pts
from research.index_coupling.run_p21d import CASES


def first_partition(ops, witness):
    loops=[]
    for note in witness:
        if note[0]=='loop' and tuple(note[1])==tuple(ops):
            loops.append(note)
        if note[0]=='groups' and tuple(op for g in note[1] for op in g)==tuple(ops) and len(note[1])>1:
            k=0;cuts=[]
            for g in note[1][:-1]:
                k+=len(g);cuts.append(k)
            return dict(cuts=cuts,groups=note[1],outer_loops=loops,
                        kept=note[3],via_dram=note[5])
    return None


def score(directory):
    audit=json.loads((directory/'cuts_before_search.json').read_text())['cases']
    rows=[];pending=[];invalid=[];counterexamples=[];replayed=0;replay_bad=[]
    sources=set();protocols=set();seconds=0;peak=0
    for i,(shape,depth,reads_x) in enumerate(CASES):
        arms={};issues=[]
        for arm in ('structural','unrestricted'):
            path=directory/f'{i:02d}_{arm}.json'
            if not path.exists():
                pending.append(dict(case=i,arm=arm,status='missing'));continue
            r=json.loads(path.read_text());arms[arm]=r
            sources.add(r['source_revision']);protocols.add(r['protocol_sha256'])
            seconds+=r.get('seconds',0);peak=max(peak,r.get('peak_rss_kib',0))
            if (r['case']!=i or r['arm']!=arm or tuple(r['shape'])!=shape
                    or r['depth']!=depth or r['reads_x']!=reads_x or r['cut_rule']!=audit[i]['cut_rule']):
                issues.append(f'{arm}: identity/cut audit mismatch')
            if r['status'] not in ('complete','invalid'):
                pending.append(dict(case=i,arm=arm,status=r['status'],stage=r['stage'],error=r.get('error')))
                continue
            if len(r.get('points',[]))!=len(r.get('replays',[])):
                issues.append(f'{arm}: missing replay records')
            for p,e in zip(r.get('points',[]),r.get('replays',[])):
                replayed+=1
                a=e['actual'];exact=a['valid'] and (a['peak'],a['traffic'])==tuple(p[:2])
                if not exact:
                    replay_bad.append(dict(case=i,arm=arm,predicted=p[:2],
                                           actual=[a['peak'],a['traffic']],valid_execution=a['valid']))
                    issues.append(f'{arm}: witness differs at capacity {p[0]}')
            if r['status']=='invalid' and not any(x.startswith(arm+':') for x in issues):
                issues.append(f'{arm}: runner marked invalid')
        if issues:
            invalid.append(dict(case=i,issues=issues))
        complete=all(arm in arms and arms[arm]['status'] in ('complete','invalid') for arm in ('structural','unrestricted'))
        row=dict(case=i,shape=shape,depth=depth,reads_x=reads_x,
                 audit=audit[i]['cut_rule'],complete_pair=complete,valid=complete and not issues)
        if complete:
            candidate=arms['structural']['points'];reference=arms['unrestricted']['points']
            if not reference:
                row['valid']=False;invalid.append(dict(case=i,issues=['unrestricted curve empty']))
            comp=comparison(pts(candidate),pts(reference));row['nominal_comparison']=comp
            for interval in comp['errors']:
                p,a=interval['value']['predicted'],interval['value']['actual']
                if p is not None and (a is None or p<a):
                    row['valid']=False;invalid.append(dict(case=i,issues=['restricted below unrestricted']))
            if row['valid'] and not comp['exact']:
                c=comp['errors'][0]['lo']
                plan=min((p for p in reference if p[0]<=c),key=lambda p:(p[1],p[0]))
                feasible=[p for p in candidate if p[0]<=c]
                chosen=min(feasible,key=lambda p:(p[1],p[0])) if feasible else None
                cut=first_partition(audit[i]['cut_rule']['ops'],plan[2])
                counterexamples.append(dict(case=i,shape=shape,depth=depth,reads_x=reads_x,
                    capacity=c,restricted_traffic=chosen[1] if chosen else None,
                    unrestricted_traffic=plan[1],reference_point=plan,
                    restricted_point=chosen,reference_first_partition=cut,
                    excluded_reference_cuts=sorted(set(cut['cuts'])-set(audit[i]['cut_rule']['positions'])) if cut else []))
        rows.append(row)
    clean=[r for r in rows if r['valid']]
    equal=sum(r['nominal_comparison']['exact'] for r in clean)
    if counterexamples:
        verdict='falsified on valid cases'
    elif len(clean)==12 and equal==12:
        verdict='supported on all 12 cases'
    else:
        verdict='not established: incomplete or invalid coverage'
    return dict(verdict=verdict,expected_cases=12,complete_pairs=sum(r['complete_pair'] for r in rows),
                clean_pairs=len(clean),clean_equal_cases=equal,clean_unequal_cases=len(clean)-equal,
                pending=pending,invalid=invalid,replayed=replayed,replay_mismatches=replay_bad,
                counterexamples=counterexamples,source_revisions=sorted(sources),protocol_hashes=sorted(protocols),
                completed_arm_seconds=seconds,max_peak_rss_kib=peak,rows=rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    result=score(parser.parse_args().directory)
    print(json.dumps(result,indent=2,allow_nan=False))
    raise SystemExit(0 if result['verdict']=='supported on all 12 cases' else 1)
