"""Score all frozen P19 timing attempts, separately from profile attempts."""
import argparse
from collections import Counter
import json
from pathlib import Path
import statistics


def score(root):
    manifest=json.loads((root/'manifest.json').read_text());rows=[];errors=[];comparisons={}
    for case in manifest['cases']:
        complete=[];arms={}
        for arm in manifest['arms']:
            group=[]
            for repeat in range(manifest['repeats']):
                row=json.loads((root/f'{case}__{arm}__r{repeat}.json').read_text())
                if row['case']!=case or row['arm']!=arm or row['profile'] or row['source_sha256']!=manifest['source_sha256']:
                    errors.append(f'{case}/{arm}/{repeat}: identity mismatch')
                if row['status']=='complete':
                    if len(row['replays'])!=len(row['points']) or not all(x['exact'] for x in row['replays']):
                        errors.append(f'{case}/{arm}/{repeat}: replay mismatch')
                    complete.append(row)
                group.append(row);rows.append(row)
            done=[r for r in group if r['status']=='complete']
            arms[arm]=dict(statuses=dict(Counter(r['status'] for r in group)),
                median_search_seconds=statistics.median(r['search_seconds'] for r in done) if len(done)==len(group) else None,
                memory_evidenced_failures=sum(r['status']=='memory' or (r['status']=='crashed' and 'MemoryError' in r.get('stderr','')) for r in group),
                peak_rss_bytes_max=max((r.get('peak_rss_bytes',r.get('sampled_peak_rss_bytes',0)) for r in group),default=0))
        equal=all(r['points']==complete[0]['points'] for r in complete) if complete else None
        if equal is False:errors.append(case+': completed frontier mismatch')
        baseline=arms['baseline']['median_search_seconds'];precheck=arms['precheck']['median_search_seconds']
        comparisons[case]=dict(arms=arms,completed_frontiers_equal=equal,
            full_four_arm_quality_validated=len(complete)==len(manifest['arms'])*manifest['repeats'],
            precheck_time_over_baseline=precheck/baseline if baseline and precheck else None)
    return dict(source_revision=manifest['revision'],attempts=len(rows),statuses=dict(Counter(r['status'] for r in rows)),
        exact_replays=sum(len(r.get('replays',[])) for r in rows if r['status']=='complete'),comparisons=comparisons,errors=errors)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();result=score(a.results);a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    if result['errors']:raise SystemExit(1)


if __name__=='__main__':main()
