"""Size-free multi-operator plan templates and their exact evaluation at any extents.

A witness from curve(witness=True) is parsed into its tree (simulate_nest.parse_witness)
and abstracted: tile sizes are dropped, and a loop whose child is a transparent
single group holding a same-axis loop that keeps nothing is merged into it. The
merge is exact: tensors kept by the outer level are external inside, so the inner
level refetches the same tensors, which lack the axis and have tile-independent
sizes, giving t1*t2*Q + (t1*t2 - 1)*R for both forms.

evaluate() re-applies curve.py's cost rules along a template with every loop tile
free (any halving tile, or the whole extent as a vacuous level):
- groups: the enumeration-grammar extra traffic and kept-tensor spans of _solve;
- loop: capacity of kept tensors, (spill or 1) * (trips - 1) * size per refetch;
- leaf: every live tensor scalar, one cell each (single op, or a v2 'hold').
Points are Pareto-pruned at every node (max/sum composition is monotone).
"""
from functools import lru_cache
from math import prod

from research.index_coupling.graph.curve import merge_staircases, pareto, tile_sizes
from research.index_coupling.simulate_nest import Specification, parse_witness

SPILL = 2


def combine(a, b):
    """max-capacity / sum-traffic composition of two (capacity, traffic) staircases."""
    return tuple((c, q) for c, q, _, _ in merge_staircases([(c, q, None) for c, q in a],
                                                            [(c, q, None) for c, q in b]))


def abstract(graph, witness):
    """Hashable size-free template of a v2 witness."""
    root = parse_witness(Specification(graph), witness, scalar_leaf='v2')

    def walk(node):
        if node.kind == 'leaf':
            return ('leaf', node.ops)
        if node.kind == 'groups':
            return ('groups', tuple(c.ops for c in node.children), tuple(sorted(node.kept)),
                    tuple(sorted(node.dropped)), tuple(walk(c) for c in node.children))
        child = node.children[0]
        while (child.kind == 'groups' and len(child.children) == 1 and not child.kept and not child.dropped
               and child.children[0].kind == 'loop' and child.children[0].variable == node.variable
               and not child.children[0].kept):
            child = child.children[0].children[0]
        return ('loop', node.ops, node.variable, tuple(sorted(node.kept)), tuple(sorted(node.dropped)),
                walk(child))

    return walk(root)


def evaluate(graph, template):
    """Exact Pareto frontier (capacity, traffic) of one template at graph.sizes."""
    names = sorted(graph.sizes)
    dims = {t: d for op in graph.ops for t, d in graph.access[op].items()}
    out = {op: graph.output(op) for op in graph.ops}
    produced, consumed = graph.produced(), graph.consumed()
    tensors = lambda ops: frozenset(t for op in ops for t in graph.access[op])

    def size(t, ext):
        e = dict(zip(names, ext))
        return prod(e[v] for v in dims[t])

    @lru_cache(None)
    def run(node, ext, external, owned):
        kind = node[0]
        if kind == 'leaf':
            live = tensors(node[1]) - external
            if any(size(t, ext) != 1 for t in live):
                return ()
            return ((len(live), 0),)
        if kind == 'groups':
            _, groups, kept, dropped, children = node
            kept = frozenset(kept)
            users = {}
            for g, group in enumerate(groups):
                for t in tensors(group) - external:
                    users.setdefault(t, []).append(g)
            extra = 0
            for t in dropped:
                gs = users[t]
                writers = [g for g in gs if any(out[op] == t for op in groups[g])]
                if writers and t in consumed:
                    extra += size(t, ext) * ((t not in owned) + len(gs) - len(writers))
                elif writers:
                    extra += 2 * size(t, ext) * (len(writers) - 1)
                else:
                    extra += size(t, ext) * (len(gs) - 1)
            child_owned = owned | frozenset(t for t in dropped if t in consumed and any(
                out[op] == t for g in users[t] for op in groups[g]))
            level = ((0, extra),)
            for g, child in enumerate(children):
                across = sum(size(t, ext) for t in kept if min(users[t]) <= g <= max(users[t]))
                inner = pareto((across + c, q) for c, q in run(child, ext, external | kept, child_owned))
                level = combine(level, inner)
                if not level:
                    return ()
            return pareto(level)
        _, ops, v, kept, dropped, child = node
        i = names.index(v)
        extent = ext[i]
        accumulated = {out[op] for op in ops}
        points = []
        for b in tile_sizes(extent) + (extent,):
            trips = extent // b
            inner_ext = ext[:i] + (b,) + ext[i + 1:]
            cap = sum(size(t, ext) for t in kept)
            extra = sum((SPILL if t in accumulated else 1) * (trips - 1) * size(t, ext) for t in dropped)
            points.extend((cap + c, extra + trips * q)
                          for c, q in run(child, inner_ext, external | frozenset(kept), owned))
        return pareto(points)

    ext0 = tuple(graph.sizes[v] for v in names)
    compulsory = sum(size(t, ext0) for t in (consumed - produced) | (produced - consumed))
    return tuple((c, q + compulsory) for c, q in run(template, ext0, frozenset(), frozenset()))


def frontier(graph, templates):
    return pareto(p for t in templates for p in evaluate(graph, t))
