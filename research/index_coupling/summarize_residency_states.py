"""Classify full recorded states; count-only candidates never alter the solver.

Only unconstrained, non-scalar solve states with all shared tensors external
are covered by the independent-operator proof. Other buckets are exploratory.
Ownership, entry, ordered span, extents and nonprivate residency stay exact.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import json
from math import prod
from pathlib import Path

from research.index_coupling.graph.model import fork


def classify(graph, state):
    ops, external = tuple(state['ops']), set(state['external'])
    ext = dict(zip(sorted(graph.sizes), state['ext']))
    incidence = Counter(t for op in ops for t in graph.access[op])
    shared = {t for t, count in incidence.items() if count > 1}
    private, profiles = set(), []
    for op in ops:
        if op == 'EX':
            continue
        access = graph.access[op]
        output = graph.output(op)
        inputs = [t for t in access if t not in ('X', output)]
        if len(inputs) != 1:
            raise ValueError('this audit classifier is scoped to fork consumers')
        tensor = inputs[0]
        private.update((tensor, output))
        profiles.append((tuple(access[tensor]), tuple(access[output]),
                         tensor in external, output in external))
    live = set(incidence) - external
    scalar = all(prod(ext[v] for v in graph.dims(t)) == 1 for t in live)
    separated = shared <= external
    eligible = (state['stage'] == 'solve' and len(ops) > 1 and not state['constrained']
                and not scalar and separated)
    key = (state['stage'], ops, tuple(state['ext']), tuple(state['owned']),
           state['constrained'], tuple(sorted(external - private)), tuple(sorted(profiles)))
    bucket = ('safe_independent' if eligible else 'scalar_leaf' if scalar and not state['constrained'] else
              'group_separated_unproved' if state['stage'] == 'group' and separated else
              'single_operator' if len(ops) == 1 else 'coupled_or_constrained')
    return dict(key=key, bucket=bucket, eligible=eligible, scalar=scalar,
                separated=separated, shared=sorted(shared))


def summarize(directory):
    directory = Path(directory)
    run = json.loads((directory / 'run.json').read_text())
    graph = fork(*run['graph_args'])
    classes, spans = {}, defaultdict(Counter)
    unique_states, count, duplicate_states = set(), 0, 0
    with gzip.open(directory / 'states.jsonl.gz', 'rt') as stream:
        for line in stream:
            state = json.loads(line)
            full_key = (state['stage'], tuple(state['ops']), tuple(state['ext']),
                        tuple(state['external']), tuple(state['owned']), state['constrained'])
            duplicate_states += full_key in unique_states
            unique_states.add(full_key)
            item = classify(graph, state)
            group = classes.setdefault(item['key'], dict(bucket=item['bucket'], count=0,
                responses={}, example=state, span=f"{state['stage']}:{','.join(state['ops'])}"))
            if group['bucket'] != item['bucket']:
                raise AssertionError('candidate signature failed to preserve proof preconditions')
            response = tuple(tuple(p) for p in state['points'])
            group['responses'].setdefault(response, state['external'])
            group['count'] += 1
            spans[group['span']]['states'] += 1
            spans[group['span']][item['bucket']] += 1
            spans[group['span']]['shared_resident'] += item['separated']
            count += 1
    totals, examples = defaultdict(Counter), []
    for group in classes.values():
        bucket = totals[group['bucket']]
        n, responses = group['count'], len(group['responses'])
        bucket.update(states=n, candidate_classes=1, duplicate_candidate_keys=n - 1,
                      response_classes=responses, unequal_classes=int(responses > 1))
        if group['bucket'] == 'safe_independent':
            spans[group['span']]['safe_duplicate_keys'] += n - 1
        if responses > 1 and len(examples) < 8:
            example = group['example']
            examples.append(dict(bucket=group['bucket'], span=group['span'],
                ext=example['ext'], owned=example['owned'], constrained=example['constrained'],
                comparisons=[dict(external=external, points=points)
                             for points, external in list(group['responses'].items())[:2]]))
    ordered = sorted(spans.items(), key=lambda pair: (-pair[1]['states'], pair[0]))
    safe = totals['safe_independent']
    primary_valid = (run['status'] == 'complete' and run.get('cache_count_matches') is True
                     and duplicate_states == 0 and count == run.get('completed_states') == run.get('cache_entries')
                     and all(r['exact'] for r in run.get('replays', [])))
    top4 = Counter()
    for _, values in ordered[:4]:
        top4.update(values)
    return dict(case=run['case'], status=run['status'], complete_census=primary_valid,
                source_sha256=run['source_sha256'], state_count=count, duplicate_states=duplicate_states,
                proof_applicable_states=safe['states'], proof_applicable_fraction=safe['states'] / count if count else None,
                safe_duplicate_keys=safe['duplicate_candidate_keys'],
                safe_duplicate_fraction=safe['duplicate_candidate_keys'] / count if count else None,
                safe_signature_failures=safe['unequal_classes'],
                buckets=dict(totals), dominant_four=dict(top4),
                spans=[dict(span=span, **values) for span, values in ordered],
                exploratory_counterexamples=examples,
                interpretation='Duplicate-key counts are retrospective coverage, not measured solver savings. '
                    'Only safe_independent has a proof contract; unequal unproved classes forbid that count-only merge.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path)
    args = p.parse_args()
    report = summarize(args.directory)
    (args.directory / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('case', 'complete_census', 'state_count',
        'proof_applicable_states', 'safe_duplicate_keys', 'safe_signature_failures', 'dominant_four')}))
    return int(not report['complete_census'] or report['safe_signature_failures'] != 0)


if __name__ == '__main__':
    raise SystemExit(main())
