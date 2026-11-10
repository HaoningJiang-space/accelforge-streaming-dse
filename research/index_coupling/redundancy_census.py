"""Intrinsic redundancy of the exact solver's conditional states.

For every completed solve/group cache miss, records its key and numeric
frontier (via audit_residency_states.instrumented_curve; no solver source is
edited) and reports, per graph:

- keys: completed cache entries (solve + group);
- tensor_alpha: classes under tensor renaming only (the existing
  canonical_spans rule: literal ranks kept);
- alpha: classes under joint tensor AND rank renaming, with each rank's full
  size and current extent carried in the signature. Ranks are bound index
  variables, so equal structure at different layers falls into one class;
- distinct: distinct (stage, frontier) values. No exact cache keyed on states
  can need fewer solves than this, so keys/distinct is an oracle upper bound
  on exact reuse, and alpha/distinct is what renaming leaves unexplained;
- local: per (stage, span, extents, constrained), how many residency/ownership
  decorations exist vs how many distinct frontiers they induce.

alpha_violations counts classes whose members have different frontiers; it
must be 0, otherwise the signature is unsound.

Usage: python -m research.index_coupling.redundancy_census --case NAME --out DIR
       python -m research.index_coupling.redundancy_census --archived FILE.jsonl.gz --name NAME --out DIR
"""
import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path
import platform
import resource
import signal
import subprocess
import time

from research.index_coupling.audit_residency_states import instrumented_curve
from research.index_coupling.graph.model import fork, residual
from research.index_coupling.graph.stacks import attention_stack, ffn_stack
from research.index_coupling.run_ancestor_width import control

CASES = {
    **{f'residual_d{d}_x{x}': (residual, (2, 2, 2, d, bool(x))) for d in (4, 6, 8, 12, 16, 24) for x in (0, 1)},
    **{f'ffn_forward_l{n}': (ffn_stack, (n,)) for n in (1, 2, 3, 4)},
    **{f'attention_forward_l{n}': (attention_stack, (n,)) for n in (1, 2, 3, 4)},
    'ffn_training_l1': (lambda: ffn_stack(1, training=True), ()),
    **{f'ancestor_k{k}': (control, (k,)) for k in range(1, 9)},
    **{f'fork_{r}': (fork, (2, 2, 2, 2, r)) for r in ('kk', 'kkk', 'kkkk', 'kki', 'kkii')},
    # Larger extents: equal small frontiers at extent two may be numerical coincidences.
    **{f'residual448_d{d}_x{x}': (residual, (4, 4, 8, d, bool(x))) for d in (4, 6, 8) for x in (0, 1)},
    **{f'fork4_{r}': (fork, (4, 4, 4, 4, r)) for r in ('kk', 'ki', 'kkk')},
    **{f'ffn_forward_l{n}_m8': (lambda n: ffn_stack(n, m=8, d=4, f=8), (n,)) for n in (1, 2)},
}


def signature(graph, state, rename_ranks):
    names = sorted(graph.sizes)
    produced, consumed = graph.produced(), graph.consumed()
    tensors, ranks, incidence = {}, {}, []
    for op in state['ops']:
        row = []
        for t, dims in graph.access[op].items():
            tensors.setdefault(t, len(tensors))
            for v in dims:
                ranks.setdefault(v, len(ranks))
            row.append((tensors[t], tuple(ranks[v] if rename_ranks else v for v in dims)))
        incidence.append((tuple(row), tensors[graph.output(op)]))
    roles = tuple((t in produced, t in consumed, len(graph.consumers(t))) for t in tensors)
    ext = dict(zip(names, state['ext']))
    # Ranks not touched by the span cannot influence it; touched ones carry size and extent.
    extents = tuple((r if not rename_ranks else i, graph.sizes[r], ext[r]) for r, i in ranks.items())
    return (state['stage'], state['constrained'], tuple(incidence), roles, extents,
            tuple(sorted(tensors[t] for t in state['external'])),
            tuple(sorted(tensors[t] for t in state['owned'])))


def summarize(graph, states):
    frontier = lambda s: (s['stage'], tuple(map(tuple, s['points'])))
    out = dict(keys=len(states), by_stage={})
    for stage in ('solve', 'group'):
        out['by_stage'][stage] = sum(s['stage'] == stage for s in states)
    out['distinct'] = len({frontier(s) for s in states})
    for label, rename in (('tensor_alpha', False), ('alpha', True)):
        classes = defaultdict(set)
        for s in states:
            classes[signature(graph, s, rename)].add(frontier(s))
        out[label] = len(classes)
        out[f'{label}_violations'] = sum(len(v) > 1 for v in classes.values())
    local = defaultdict(lambda: [0, set()])
    for s in states:
        entry = local[(s['stage'], tuple(s['ops']), tuple(s['ext']), s['constrained'])]
        entry[0] += 1
        entry[1].add(frontier(s))
    out['local_contexts'] = len(local)
    out['local_decorations'] = sum(n for n, _ in local.values())
    out['local_distinct'] = sum(len(f) for _, f in local.values())
    out['spans'] = len({tuple(s['ops']) for s in states})
    out['max_frontier'] = max((len(s['points']) for s in states), default=0)
    return out


def timeout(*_):
    raise TimeoutError('redundancy census wall-time limit')


def run_case(name, seconds, mem_gib):
    builder, args = CASES[name]
    graph = builder(*args)
    if platform.system() == 'Linux':
        cap = int(mem_gib * 2**30)
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    states = []
    record = dict(case=name, revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  python=platform.python_version(), budgets=dict(seconds=seconds, mem_gib=mem_gib),
                  options=dict(partitions='dp', canonical_spans=False, independent_ops=False,
                               tile_domain='halving'))
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    start = time.monotonic()
    try:
        compute = instrumented_curve(lambda s: states.append(
            dict(s, ops=list(s['ops']), ext=list(s['ext']), points=[list(p) for p in s['points']])))
        points = compute(graph, **record['options'])
        record.update(status='complete', points=[list(p[:2]) for p in points])
    except TimeoutError:
        record.update(status='timeout')
    except MemoryError:
        record.update(status='memory')
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    record.update(search_seconds=time.monotonic() - start)
    if record['status'] == 'complete':
        record.update(summarize(graph, states))
    else:
        record.update(partial_keys=len(states))
    return record, states


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', choices=CASES)
    p.add_argument('--archived', type=Path, help='existing states.jsonl.gz from audit_residency_states')
    p.add_argument('--name', help='name for --archived; one of audit_residency_states.CASES')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--seconds', type=float, default=60)
    p.add_argument('--mem-gib', type=float, default=4)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.archived:
        from research.index_coupling.audit_residency_states import CASES as FORKS
        with gzip.open(a.archived, 'rt') as stream:
            states = [json.loads(line) for line in stream]
        record = dict(case=a.name, source=str(a.archived), status='complete',
                      **summarize(fork(*FORKS[a.name]), states))
        name = a.name
    else:
        record, states = run_case(a.case, a.seconds, a.mem_gib)
        name = a.case
        with gzip.open(a.out / f'{name}.states.jsonl.gz', 'wt') as stream:
            for s in states:
                stream.write(json.dumps(s, separators=(',', ':')) + '\n')
    (a.out / f'{name}.json').write_text(json.dumps(record, indent=1) + '\n')
    print(json.dumps({k: record.get(k) for k in ('case', 'status', 'keys', 'tensor_alpha', 'alpha', 'distinct',
                                                  'alpha_violations', 'tensor_alpha_violations',
                                                  'search_seconds')}))


if __name__ == '__main__':
    main()
