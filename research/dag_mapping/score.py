"""Summarize the frozen D1 archive without rerunning search."""
import argparse
import hashlib
import json
from pathlib import Path

from .study import ARMS, compare, value
from .workloads import D1_CASES as CASES
from .artifacts import frozen_bytes


def score(root):
    rows = []
    for name in CASES:
        record = json.loads((root / 'results' / (name + '.json')).read_text())
        if record['status'] != 'complete':
            rows.append(dict(case=name, status=record['status']))
            continue
        for source, expected in record['source_sha256'].items():
            if hashlib.sha256(frozen_bytes(record['revision'], source)).hexdigest() != expected:
                raise ValueError(f'source differs from frozen execution: {source}')
        arms = record['arms']
        reference = arms['native_all_orders']['frontier']
        comparisons = {arm: compare(reference, arms[arm]['frontier']) for arm in ARMS[1:]}
        for arm in ARMS[1:]:
            if comparisons[arm] != arms[arm]['comparison_to_complete']:
                raise ValueError(f'archived comparison differs: {name}/{arm}')
        if not all(r['exact'] for arm in ARMS for r in arms[arm]['replays']):
            raise ValueError(f'failed replay: {name}')
        rows.append(dict(case=name, status='complete', orders=len(record['orders']),
                         complete_frontier_points=len(reference),
                         native_boundary_checks=sum(a['work'].get('native_checks', 0) for a in arms.values()),
                         witness_replays=sum(len(a['replays']) for a in arms.values()),
                         full_curve_equal={arm: comparisons[arm]['equal'] for arm in ARMS[1:]},
                         traffic_at_4={arm: value(arms[arm]['frontier'], 4) for arm in ARMS},
                         traffic_at_5={arm: value(arms[arm]['frontier'], 5) for arm in ARMS},
                         plateau={arm: arms[arm]['frontier'][-1] for arm in ARMS}))
    return dict(cases=len(rows), completed=sum(r['status'] == 'complete' for r in rows),
                native_boundary_checks=sum(r.get('native_boundary_checks', 0) for r in rows),
                witness_replays=sum(r.get('witness_replays', 0) for r in rows), rows=rows,
                interpretation='correct restricted composition; no complete-DAG speedup claim',
                analyzer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('preserve prior analysis')
    result = score(args.archive)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('cases', 'completed', 'native_boundary_checks', 'witness_replays')}))
