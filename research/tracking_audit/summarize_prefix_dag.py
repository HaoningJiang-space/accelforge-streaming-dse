"""Reject any per-query mismatch before summarizing independent process runs."""
import argparse
import json
import statistics
from pathlib import Path


def run(directory):
    summary={}
    for index in (1,3):
        runs={mode:[json.loads((directory/f'{index}_{mode}_{i}.json').read_text()) for i in (1,2,3)]
              for mode in ('region','dag','cached')}
        reference=runs['region'][0]
        for mode,group in runs.items():
            for record in group:
                if record['template']!=index or record['mode']!=mode or record['source_sha256']!=reference['source_sha256']:
                    raise ValueError('different source code, template or mode')
                if not record.get('all_sampled_reconstructions_valid') or len(record['queries'])!=256:
                    raise ValueError('incomplete query or reconstruction validation')
                for sample in (0,1,2,3,63,127,191,255):
                    checked=record['queries'][sample].get('reconstruction',{})
                    if not checked.get('ok') or not checked.get('exact_gb_match'):
                        raise ValueError('a sampled Mapping failed reconstruction')
                if mode in ('region','dag') and record['compilation']!=group[0]['compilation']:
                    raise ValueError('region execution work changed between repeats')
                if mode=='cached' and record['cache_work']!=group[0]['cache_work']:
                    raise ValueError('cached execution work changed between repeats')
                for expected,actual in zip(reference['queries'],record['queries']):
                    if any(expected[k]!=actual[k] for k in ('point','choices','frontier')):
                        raise ValueError(f'{mode} candidate or complete frontier differs at {actual["point"]}')
        medians={mode:statistics.median(r['total_s'] for r in group) for mode,group in runs.items()}
        original, factorized = runs['region'][0]['compilation'],runs['dag'][0]['compilation']
        if (original['expanded_rows'] != factorized['requested_expanded_rows'] or
                original['peak_state_rows'] != factorized['peak_state_rows'] or
                original['pareto_calls'] != factorized['pareto_calls'] or
                original['peak_boxes'] != factorized['peak_boxes']):
            raise ValueError('region workload counters do not match')
        checkpoints={n:{mode:statistics.median(r['queries'][n-1]['cumulative_s'] for r in group)
                        for mode,group in runs.items()} for n in (1,16,64,128,256)}
        summary[index]=dict(all_query_candidates_and_frontiers_equal=True,queries=256,
            medians_s=medians,checkpoints_s=checkpoints,
            totals_s={mode:[r['total_s'] for r in group] for mode,group in runs.items()},
            preprocess_s={mode:[r['preprocess_s'] for r in group] for mode,group in runs.items()},
            peak_rss_gib={mode:[r['search_peak_rss_gib'] for r in group] for mode,group in runs.items()},
            region_stats=runs['region'][0]['compilation'],dag_stats=runs['dag'][0]['compilation'],
            cached_work=runs['cached'][0]['cache_work'],source_sha256=reference['source_sha256'])
    output=directory/'summary.json';output.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:dict(medians_s=v['medians_s'],checkpoints_s=v['checkpoints_s']) for k,v in summary.items()},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    run(p.parse_args().directory)
