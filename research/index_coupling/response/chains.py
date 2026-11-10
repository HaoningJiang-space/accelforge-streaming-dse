"""Recognition of chain states, shared by the closed forms, bounds and substitution.

A state (ops, ext, external, owned) is a *chain* when its ops form
V_0 -> V_1 -> ... -> V_m, each op a dense contraction (one activation input,
one weight) or an elementwise op. Recognition is structural, not by operator
names:
- row ranks are those shared by every produced tensor of the graph (M for
  FFN and attention); activations carry them, weights carry none;
- each vector has exactly one non-row rank; elementwise keeps it, a
  contraction changes it, and no rank recurs along the chain;
- every weight is used only by its op; every interior vector is produced by
  its predecessor, consumed only by its successor, and is neither external
  nor owned.
Ambiguous states are rejected.
"""
from collections import namedtuple
from functools import lru_cache
from math import prod

Chain = namedtuple('Chain', 'kinds sizes rows first last streamed contractions')
Chain.__doc__ = """kinds: 'c'/'e' per op; sizes: per-vector size without row ranks;
rows: product of the row extents; first/last: whether the span ends are
resident; streamed: per op, 1 if its weight is not resident; contractions:
per contraction, ((rows, d_in, d_out), live tensors among 'W', 'X', 'Y')."""


@lru_cache(maxsize=None)
def _dims(graph, tensor):
    return frozenset(graph.dims(tensor))


@lru_cache(maxsize=None)
def _produced(graph):
    return frozenset(graph.produced())


@lru_cache(maxsize=None)
def _consumers(graph, tensor):
    return tuple(graph.consumers(tensor))


def recognise(graph, ops, ext, external, owned, names, unit_rows=False):
    """Chain of a state, or None. unit_rows requires every row extent to be 1."""
    ext = dict(zip(names, ext))
    dims = lambda t: _dims(graph, t)
    rows = frozenset.intersection(*(dims(t) for t in _produced(graph)))
    if not rows:
        return None
    vectors, kinds, weights = [], [], []
    for i, op in enumerate(ops):
        out = graph.output(op)
        ins = [t for t in graph.access[op] if t != out]
        acts = [t for t in ins if rows <= dims(t)]
        rest = [t for t in ins if not dims(t) & rows]
        if len(acts) != 1 or len(acts) + len(rest) != len(ins) or len(rest) > 1:
            return None
        x = acts[0]
        if i and x != graph.output(ops[i - 1]):
            return None
        w = rest[0] if rest else None
        if w is None and dims(x) != dims(out):
            return None
        if i == 0:
            vectors.append(x)
        vectors.append(out)
        kinds.append('e' if w is None else 'c')
        weights.append(w)
    if any(not rows <= dims(v) for v in vectors) or (unit_rows and any(ext[r] != 1 for r in rows)):
        return None
    own = []
    for v in vectors:
        rest = dims(v) - rows
        if len(rest) != 1:
            return None
        own.append(next(iter(rest)))
    distinct = [own[0]]
    for k, r_in, r_out in zip(kinds, own, own[1:]):
        if (k == 'e') != (r_in == r_out):
            return None
        if k == 'c':
            distinct.append(r_out)
    if len(set(distinct)) != len(distinct):
        return None
    for op, w, r_in, r_out in zip(ops, weights, own, own[1:]):
        if w is not None and (dims(w) != {r_in, r_out} or _consumers(graph, w) != (op,)
                              or w in _produced(graph)):
            return None
    for j, v in enumerate(vectors[1:-1], 1):
        if v in external or v in owned or _consumers(graph, v) != (ops[j],):
            return None
    m = prod(ext[r] for r in rows)
    first, last = vectors[0] in external, vectors[-1] in external
    streamed = tuple(int(w is not None and w not in external) for w in weights)
    contractions = []
    for j, (k, w) in enumerate(zip(kinds, weights)):
        if k == 'c':
            live = [t for t, on in (('W', w not in external), ('X', not (j == 0 and first)),
                                    ('Y', not (j == len(kinds) - 1 and last))) if on]
            contractions.append(((m, ext[own[j]], ext[own[j + 1]]), tuple(sorted(live))))
    return Chain(tuple(kinds), tuple(ext[r] for r in own), m, first, last, streamed, tuple(contractions))


def archived(graph, state, unit_rows=False):
    """Chain of an archived call-DAG node state (solve stage, unconstrained), or None."""
    if state['stage'] != 'solve' or state['constrained']:
        return None
    return recognise(graph, tuple(state['ops']), tuple(state['ext']), frozenset(state['external']),
                     frozenset(state['owned']), sorted(graph.sizes), unit_rows)
