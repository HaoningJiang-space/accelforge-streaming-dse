"""Normalize empty-retention loop blocks; this is not a search algorithm.

Uses only the independent witness syntax, not curve_model's cost functions.
Fusion partitions and every nonempty reservation scope are barriers.
"""
from dataclasses import replace

from .simulate_nest import Node, Specification, parse_witness, require


def transparent(node):
    return (node.kind == 'groups' and len(node.children) == 1
            and not node.kept and not node.dropped)


def normalize(spec, node, bounds=None, external=frozenset()):
    if bounds is None:
        bounds = spec.bounds
    if node.kind == 'leaf':
        return node
    if node.kind == 'groups':
        return replace(node, children=tuple(
            normalize(spec, c, bounds, external | set(node.kept))
            for c in node.children))
    require(node.kind == 'loop', 'unknown node')
    if node.kept:
        inner = dict(bounds, **{node.variable: range(node.tile)})
        return replace(node, children=(normalize(
            spec, node.children[0], inner, external | set(node.kept)),))

    final, targets, cursor = dict(bounds), {}, node
    while True:
        targets[cursor.variable] = cursor.tile
        final[cursor.variable] = range(cursor.tile)
        tail = cursor.children[0]
        following = tail.children[0] if transparent(tail) else tail
        if following.kind != 'loop' or following.kept:
            break
        require(following.ops == node.ops, 'operation change inside free block')
        cursor = following

    live = spec.tensors(node.ops) - external
    order = sorted(targets)
    # The parser forces a leaf as soon as all local tensors are scalar. Keep
    # one shrinking, live-indexed rank last so canonicalization cannot trigger
    # that leaf before the remaining explicit loops have run.
    if all(len(final[v]) == 1 for t in live for v in spec.dims[t]):
        guards = [v for v in order if len(bounds[v]) > 1 and len(final[v]) == 1
                  and any(v in spec.dims[t] for t in live)]
        require(guards, 'non-scalar block needs a last live-rank guard')
        guard = guards[-1]
        order = [v for v in order if v != guard] + [guard]

    result = normalize(spec, tail, final, external)
    for v in reversed(order):
        dropped = tuple(sorted(t for t in live if v not in spec.dims[t]))
        result = Node('loop', node.ops, (), dropped, v, targets[v], (result,))
    return result


def flatten(spec, node):
    """Encode the normalized tree back into the existing flat witness grammar."""
    records = []

    def emit(current, bounds, mode):
        if current.kind == 'leaf':
            return
        if current.kind == 'groups':
            require(mode == 'groups', 'group partition needs a group scope')
            records.append(('groups', tuple(c.ops for c in current.children),
                            'kept', tuple(current.kept), 'via DRAM', tuple(current.dropped)))
            for child in current.children:
                emit(child, bounds, 'loop')
            return
        require(current.kind == 'loop', 'unknown node')
        if mode == 'groups':
            records.append(('groups', (current.ops,), 'kept', (), 'via DRAM', ()))
        extent = len(bounds[current.variable])
        require(0 < current.tile < extent and extent % current.tile == 0,
                'normalization created an illegal tile')
        records.append(('loop', current.ops, current.variable,
                        f'tile {current.tile} x{extent // current.tile}',
                        'kept', tuple(current.kept), 'refetched', tuple(current.dropped)))
        inner = dict(bounds, **{current.variable: range(current.tile)})
        emit(current.children[0], inner, 'groups')

    emit(node, spec.bounds, 'groups')
    return tuple(records)


def normalize_witness(graph, witness):
    spec = Specification(graph)
    result = flatten(spec, normalize(spec, parse_witness(spec, witness)))
    parse_witness(spec, result)  # Reject invalid scope/implicit-leaf boundaries.
    return result


def loop_counts(node):
    children = [loop_counts(c) for c in node.children]
    here = int(node.kind == 'loop')
    return (here + sum(c[0] for c in children),
            here + max((c[1] for c in children), default=0))


def depth_bound(spec):
    return len(spec.sizes) * (len(spec.dims) + len(spec.ops)) + len(spec.dims)


def refine_once(spec, node, bounds=None):
    """Inject a redundant dyadic split to test coalescing, not measure speedup."""
    if bounds is None:
        bounds = spec.bounds
    if node.kind == 'loop':
        ratio = len(bounds[node.variable]) // node.tile
        if not node.kept and ratio >= 4 and ratio & (ratio - 1) == 0:
            return replace(node, tile=2 * node.tile, children=(node,)), True
        inner = dict(bounds, **{node.variable: range(node.tile)})
        child, changed = refine_once(spec, node.children[0], inner)
        return replace(node, children=(child,)), changed
    if node.kind == 'groups':
        children = list(node.children)
        for i, child in enumerate(children):
            children[i], changed = refine_once(spec, child, bounds)
            if changed:
                return replace(node, children=tuple(children)), True
    return node, False
