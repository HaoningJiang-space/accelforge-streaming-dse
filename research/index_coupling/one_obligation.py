"""Exact two-live-tensor Fork normal form, not a general one-obligation rule.

Scope: vector X, one private tensor t lacking its active axis, all other
accessed tensors external, unrestricted multi-op solve. Three construction
families cover this restricted grammar. Extra traffic excludes caller costs.
No solver shortcut is enabled by this module.
"""
from math import prod

from research.index_coupling.graph.curve import pareto, tile_sizes


def two_live_response(graph, ops, ext, external, owned, names, witness=False,
                      max_capacity=float('inf'), tile_domain='halving'):
    """Caller establishes standard Fork and the default exact cost rules."""
    if len(ops) < 2 or set(owned) - {'X'}:
        return None
    sizes = dict(zip(names, ext))
    active = [v for v in ('I','K') if sizes[v] > 1]
    live = graph.tensors(ops) - set(external)
    if len(active) != 1 or 'X' not in live or len(live) != 2:
        return None
    axis = active[0]
    tensor = next(iter(live - {'X'}))
    if axis in graph.dims(tensor):
        return None
    owner = next(o for o in ops if tensor in graph.access[o])
    other = 'J' if owner == 'EX' else 'L'
    n, s = sizes[axis], prod(sizes[v] for v in graph.dims(tensor))
    if s != sizes[other]:
        return None
    alpha = 2 if graph.output(owner) == tensor else 1
    producer = 'EX' in ops
    beta = (2 - ('X' in owned)) if producer else 0
    alpha_x = 2 if owner == 'EX' else 1
    # Equal-point witnesses prefer whole-t retention, then X blocks.
    candidates = [(s+1, 0, ('keep_t', s))]
    candidates += [(b+1, alpha*s*(n//b-1), ('x_block', b))
                   for b in (n, *tile_sizes(n, tile_domain))]
    candidates += [(c+1, alpha_x*n*(s//c-1) + beta*n, ('t_block', c))
                   for c in (s, *tile_sizes(s, tile_domain))]

    def groups(parts, kept=(), dropped=()):
        return ('groups', tuple(tuple(p) for p in parts), 'kept', kept, 'via DRAM', dropped)

    def loop(span, rank, tile, trips, kept=(), dropped=()):
        return ('loop', tuple(span), rank, f'tile {tile} x{trips}', 'kept', kept, 'refetched', dropped)

    def hold_t_group(span, c):
        notes = []
        if c < s:
            notes += [loop(span, other, c, s//c, dropped=('X',)), groups((span,))]
        notes.append(loop(span, axis, 1, n, kept=(tensor,)))
        return notes

    out = []
    for capacity, traffic, (kind, tile) in pareto(candidates, max_capacity):
        notes = []
        if witness:
            if kind == 'keep_t':
                notes = [groups((ops,)), loop(ops, axis, 1, n, kept=(tensor,))]
            elif kind == 'x_block':
                if tile < n:
                    notes += [groups((ops,)), loop(ops, axis, tile, n//tile, dropped=(tensor,))]
                notes.append(groups(tuple((o,) for o in ops), kept=('X',)))
                if s > 1:
                    notes.append(loop((owner,), other, 1, s))
            elif not producer:
                notes = [groups((ops,))] + hold_t_group(ops, tile)
            else:
                consumers = tuple(o for o in ops if o != 'EX')
                notes.append(groups((('EX',), consumers), dropped=('X',)))
                if owner == 'EX':
                    notes += hold_t_group(('EX',), tile)
                    notes.append(loop(consumers, axis, 1, n))
                else:
                    notes.append(loop(('EX',), axis, 1, n))
                    notes += hold_t_group(consumers, tile)
        out.append((capacity, traffic, tuple(notes)))
    return tuple(out)
