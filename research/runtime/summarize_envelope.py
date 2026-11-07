"""Summarize completed independent-process envelope trials, without rerunning them."""
import argparse
import json
from pathlib import Path
import statistics


def summarize(directory):
    methods = {}
    for path in sorted(directory.glob('*_r*.json')):
        if path.stem.endswith('_check'):
            continue
        report = json.loads(path.read_text(encoding='utf-8'))
        if report['status']!='complete':
            raise ValueError(f'incomplete trial: {path}')
        check_path = path.with_name(path.stem+'_check.json')
        if not check_path.exists() or json.loads(check_path.read_text())['status']!='verified':
            raise ValueError(f'unverified trial: {path}')
        methods.setdefault(report['method'],[]).append(report)
    result = dict(external_sota_acceptance=False,methods={})
    for method,reports in methods.items():
        times = [r['search_s'] for r in reports]
        work = [{k:sum(d['work'][k] for d in r['oracle_details'])
                 for k in r['oracle_details'][0]['work']} for r in reports]
        selections = [[s['edp'] for s in r['budget_selections']] for r in reports]
        if any(values!=selections[0] for values in selections):
            raise AssertionError('quality changed across repetitions')
        result['methods'][method] = dict(n=len(times),search_s=times,
            median_s=statistics.median(times),min_s=min(times),max_s=max(times),
            native_solves=[r['native_solves'] for r in reports],
            pruned_hardware=[r['pruned_hardware'] for r in reports],
            work=work,global_edp=selections[0],
            peak_rss_gib=[r['peak_rss_gib_before_validation']['main'] for r in reports],
            same_frozen_sources=len({r['source_before'] for r in reports})==1)
    if 'events' in result['methods']:
        baseline = result['methods']['events']['median_s']
        for method,row in result['methods'].items():
            row['median_speedup_vs_events'] = baseline/row['median_s']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    report = summarize(args.directory)
    if args.output:
        args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:{name:row[name] for name in ('n','median_s','min_s','max_s','median_speedup_vs_events')}
                      for k,row in report['methods'].items()}))


if __name__=='__main__':
    main()
