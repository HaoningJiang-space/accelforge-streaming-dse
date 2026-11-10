"""Check the scalar-X theorem against complete, previously recorded joint states."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path

from research.index_coupling.graph.model import fork
from research.index_coupling.scalar_bridge import bridge_response, standard_fork


def audit(directory):
    directory = Path(directory)
    run = json.loads((directory / 'run.json').read_text())
    if run['status'] != 'complete' or not run['cache_count_matches']:
        raise ValueError('requires a complete census')
    graph = fork(*run['graph_args'])
    if not standard_fork(graph):
        raise ValueError('unsupported graph')
    counts, spans, failures = Counter(), defaultdict(Counter), []
    with gzip.open(directory / 'states.jsonl.gz', 'rt') as stream:
        for line in stream:
            state = json.loads(line)
            counts['all_states'] += 1
            span = f"{state['stage']}:{','.join(state['ops'])}"
            if not state['points']:
                counts['empty_frontiers'] += 1
                spans[span]['empty_frontiers'] += 1
            if state['stage'] != 'solve' or state['constrained']:
                continue
            predicted = bridge_response(graph, state['ops'], state['ext'], state['external'],
                                        state['owned'], run['rank_order'])
            if predicted is None:
                continue
            same = [list(p[:2]) for p in predicted] == state['points']
            counts['eligible'] += 1
            counts['wrong'] += not same
            spans[span]['eligible'] += 1
            spans[span]['wrong'] += not same
            spans[span][f'capacity_{predicted[0][0]}'] += 1
            if not same:
                failures.append(dict(state=state, predicted=predicted))
    if counts['all_states'] != run['completed_states']:
        raise ValueError('incomplete raw stream')
    return dict(case=run['case'], census_revision=run['revision'],
                census_source_sha256=run['source_sha256'],
                raw_sha256=hashlib.sha256((directory / 'states.jsonl.gz').read_bytes()).hexdigest(),
                counts=dict(counts), spans=dict(spans), failures=failures,
                scope='Retrospective theorem check on complete tiny-fork state records, not held-out prediction.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directories', nargs='+', type=Path)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if args.out.exists():
        p.error('refusing to overwrite an audit')
    report = [audit(d) for d in args.directories]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps([dict(case=r['case'], **r['counts']) for r in report]))
    return int(any(r['failures'] for r in report))


if __name__ == '__main__':
    raise SystemExit(main())
