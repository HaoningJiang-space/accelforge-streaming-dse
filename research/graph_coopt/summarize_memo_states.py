"""Summarize an analysis archive without re-running or timing FFM."""
import argparse
import json
from pathlib import Path

from .memo_state_analysis import KINDS


def summarize(report):
    results = []
    for result in report['results']:
        runs = []
        for run in result['runs']:
            stats = list(run['einsums'].values())
            runs.append(dict(architecture=run['architecture'],
                candidate_rows=sum(s['candidate_rows'] for s in stats),
                analyzed_rows=sum(s['analyzed_rows'] for s in stats),
                unsupported_rows=sum(len(s['unsupported']) for s in stats),
                ffm_groups=sum(s['ffm_groups'] for s in stats),
                observed_unique={kind: sum(s['observations'][kind]['unique'] for s in stats) for kind in KINDS},
                boundary_groups_with_distinct_cost_or_resource=sum(
                    s['boundary_groups_with_distinct_cost_or_resource'] for s in stats)))
        overlaps = []
        for overlap in result['overlaps']:
            stats = overlap['einsums']
            overlaps.append(dict(source=overlap['source'], target=overlap['target'],
                target_rows=sum(s['full_local_mapping']['target_rows'] for s in stats.values()),
                covered_rows={kind: sum(s[kind]['covered_rows'] for s in stats.values())
                              for kind in (*KINDS, 'full_mapping_and_cost_resource')}))
        total = sum(r['analyzed_rows'] for r in runs)
        # Node identity is retained: rows from different Einsums never merge.
        unions = {kind: sum(s['observations'][kind]['unique'] for s in result['union'].values())
                  for kind in KINDS}
        results.append(dict(workload=result['workload'], runs=runs,
                            row_occurrences_across_architectures=total,
                            union_observed_unique=unions, overlaps=overlaps,
                            certified_semantic_merges=0, avoided_search_work=0))
    return dict(scope=report['scope'], results=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(json.loads(args.input.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    for case in result['results']:
        print(case['workload'])
        for run in case['runs']:
            print(run['architecture'], run['candidate_rows'], run['ffm_groups'], run['observed_unique'])


if __name__ == '__main__':
    main()
