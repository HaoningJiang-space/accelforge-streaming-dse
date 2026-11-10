"""Shared helpers for the conditional-state census analyses.

A census is a gzip JSONL file of completed solve/group cache misses, as written
by audit_residency_states.py or redundancy_census.py. Each record has stage,
ops, ext (indexed by sorted rank name), external, owned, constrained and points
(the internal extra-traffic frontier).
"""
from collections import namedtuple
import gzip
import json
from math import prod

from research.index_coupling.graph.model import fork, residual
from research.index_coupling.graph.stacks import attention_stack, ffn_stack
from research.index_coupling.run_ancestor_width import control

# Small six-consumer forks of audit_residency_states.py, plus every census case.
CASES = {
    'kkk': (fork, (2, 2, 2, 2, 'kkk')),
    'same6': (fork, (2, 2, 2, 2, 'kkkkkk')),
    'mixed6': (fork, (2, 2, 2, 2, 'kkkiii')),
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

Key = namedtuple('Key', 'stage ops ext constrained owned external')


def graph_of(case):
    builder, args = CASES[case]
    return builder(*args)


def load_states(path):
    with gzip.open(path, 'rt') as stream:
        for line in stream:
            yield json.loads(line)


def key_of(state):
    return Key(state['stage'], tuple(state['ops']), tuple(state['ext']), state['constrained'],
               tuple(state['owned']), frozenset(state['external']))


def points_of(state):
    return tuple(map(tuple, state['points']))


def extents(graph, state):
    return dict(zip(sorted(graph.sizes), state['ext']))


def accesses(graph, state):
    """tensor -> rank tuple, over the state's span."""
    return {t: dims for op in state['ops'] for t, dims in graph.access[op].items()}


def size_at(dims, ext):
    return prod(ext[v] for v in dims)


def operand_bound(graph, state):
    """d = max over operators of nonresident operand/output cells."""
    ext, resident = extents(graph, state), set(state['external'])
    return max(sum(size_at(dims, ext) for t, dims in graph.access[op].items() if t not in resident)
               for op in state['ops'])


def stratum(graph, state, points=None):
    """empty / zero_at_d / zero_above_d / rest (WORK_ATTRIBUTION.md)."""
    points = points_of(state) if points is None else points
    if not points:
        return 'empty'
    if len(points) > 1 or points[0][1] != 0:
        return 'rest'
    return 'zero_at_d' if points[0][0] == operand_bound(graph, state) else 'zero_above_d'
