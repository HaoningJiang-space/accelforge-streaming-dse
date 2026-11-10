"""Certified branch permutations and order-complete continuation references.

This is a small exhaustive oracle, not a scalable general-DAG optimizer.
Input ports are commutative in Graph's einsum/product semantics; outputs and
literal rank projections are preserved. No assumptions about arbitrary ops.
"""
from dataclasses import dataclass
from itertools import permutations, product

from .curve import curve, pareto
from .fork_quotient import Plan, renamed, reordered
from .model import Graph


def branch_graph(shape=(2, 2, 2, 2, 2), branches=2, *, join=False, tails=None):
    """X=AB; U_i=X C_i; optionally V_i=U_i D_i; optional product join."""
    if len(shape) != 5 or any(n < 1 for n in shape) or branches < 1:
        raise ValueError('positive I,J,K,L,N dimensions and branch count required')
    tails = (True,) * branches if tails is None else tuple(tails)
    if len(tails) != branches or (join and len(set(tails)) != 1):
        raise ValueError('join requires equal branch output projections')
    ops = [('EX', {'A': ('I', 'J'), 'B': ('J', 'K'), 'X': ('I', 'K')})]
    outputs = {}
    for i, tail in enumerate(tails):
        ops.append((f'E{i}', {'X': ('I', 'K'), f'C{i}': ('K', 'L'), f'U{i}': ('I', 'L')}))
        if tail:
            ops.append((f'H{i}', {f'U{i}': ('I', 'L'), f'D{i}': ('L', 'N'), f'V{i}': ('I', 'N')}))
        outputs[f'V{i}' if tail else f'U{i}'] = ('I', 'N') if tail else ('I', 'L')
    if join:
        ops.append(('Join', dict(outputs, Y=next(iter(outputs.values())))))
    return Graph(dict(zip(('I', 'J', 'K', 'L', 'N'), shape)), ops)


@dataclass
class Renaming:
    ops: dict
    tensors: dict


def is_automorphism(graph, mapping):
    """Check the entire typed incidence, not just the consumer's first op."""
    tensors = graph.tensors(graph.ops)
    if (set(mapping.ops) != set(graph.ops) or set(mapping.ops.values()) != set(graph.ops)
            or set(mapping.tensors) != tensors or set(mapping.tensors.values()) != tensors):
        return False
    if any(graph.dims(t) != graph.dims(mapping.tensors[t]) for t in tensors):
        return False
    for op in graph.ops:
        target = mapping.ops[op]
        if mapping.tensors[graph.output(op)] != graph.output(target):
            return False
        sources = set(graph.access[op]) - {graph.output(op)}
        targets = set(graph.access[target]) - {graph.output(target)}
        if {mapping.tensors[t] for t in sources} != targets:
            return False
    return True


def branch_permutation(graph, permutation):
    om, tm = {o: o for o in graph.ops}, {t: t for t in graph.tensors(graph.ops)}
    for i, j in enumerate(permutation):
        for prefix in ('E', 'H'):
            if f'{prefix}{i}' in om: om[f'{prefix}{i}'] = f'{prefix}{j}'
        for prefix in ('C', 'U', 'D', 'V'):
            if f'{prefix}{i}' in tm: tm[f'{prefix}{i}'] = f'{prefix}{j}'
    return Renaming(om, tm)


def branch_automorphisms(graph, branches):
    candidates = (branch_permutation(graph, p) for p in permutations(range(branches)))
    return tuple(p for p in candidates if is_automorphism(graph, p))


def topological_orders(graph, ops=None):
    ops = tuple(graph.ops if ops is None else ops)
    if not set(ops) <= set(graph.ops) or len(set(ops)) != len(ops):
        raise ValueError('invalid operator subset')
    writer = {}
    for op in graph.ops:
        out = graph.output(op)
        if out in writer: raise ValueError('single writer required')
        writer[out] = op
    selected = set(ops)
    pred = {o: {writer[t] for t in graph.access[o] if t != graph.output(o)
                and t in writer and writer[t] in selected} for o in ops}
    def visit(prefix, remaining):
        if not remaining:
            yield tuple(prefix); return
        ready = [o for o in ops if o in remaining and not pred[o] & remaining]
        if not ready: raise ValueError('cyclic dependencies')
        for op in ready:
            yield from visit(prefix + [op], remaining - {op})
    yield from visit([], selected)


def induced(graph, ops):
    selected = set(ops)
    return Graph(dict(graph.sizes), [(o, dict(graph.access[o])) for o in graph.ops if o in selected])


def continuation_ops(graph, progress):
    """EX is complete; each two-op branch has completed 0, 1 or 2 ops."""
    if any(p not in (0, 1, 2) for p in progress): raise ValueError('invalid progress')
    remaining = {'Join'} if 'Join' in graph.ops else set()
    for i, stage in enumerate(progress):
        if stage == 0: remaining.add(f'E{i}')
        if stage < 2: remaining.add(f'H{i}')
    if not remaining <= set(graph.ops): raise ValueError('continuation requires two-op branches')
    return tuple(o for o in graph.ops if o in remaining)


def continuation_states(graph, branches):
    """All reachable stage patterns and private ready-input residency masks.

X is DRAM-backed when still used. Completed prefix cost is outside this query.
No future intermediate is declared resident and no shared-write history is erased.
    """
    for progress in product(range(3), repeat=branches):
        ops = continuation_ops(graph, progress)
        g = induced(graph, ops)
        available = sorted((g.consumed() - g.produced()) - {'X'})
        for bits in product((False, True), repeat=len(available)):
            yield dict(progress=progress, ops=ops,
                       external=tuple(t for t, bit in zip(available, bits) if bit))


class BranchOrderOracle:
    def __init__(self, graph, branches, *, quotient=True):
        self.graph, self.quotient = graph, quotient
        self.automorphisms = branch_automorphisms(graph, branches)
        if not self.automorphisms: raise ValueError('identity automorphism missing')
        self.cache = {}
        self.stats = dict(queries=0, hits=0, misses=0, order_calls=0,
                          solve_entries=0, group_entries=0)

    def key(self, ops, external, owned, entry, mapping):
        tensors = self.graph.tensors(ops)
        made = {self.graph.output(o) for o in ops}
        return (tuple(sorted(mapping.ops[o] for o in ops)),
                tuple(sorted(mapping.tensors[t] for t in set(external) & tensors)),
                tuple(sorted(mapping.tensors[t] for t in set(owned) & made)), entry)

    def canonical(self, ops, external=(), owned=(), entry='solve'):
        images = [(self.key(ops, external, owned, entry, p), p) for p in self.automorphisms]
        return min(images, key=lambda item: item[0])

    def query(self, ops=None, *, external=(), owned=(), entry='solve'):
        ops = self.graph.ops if ops is None else tuple(ops)
        if entry not in ('solve', 'group'): raise ValueError('unknown entry')
        if not set(ops) <= set(self.graph.ops): raise ValueError('unknown operator')
        if not set(external) <= self.graph.tensors(self.graph.ops): raise ValueError('unknown tensor')
        self.stats['queries'] += 1
        identity = Renaming({o:o for o in self.graph.ops}, {t:t for t in self.graph.tensors(self.graph.ops)})
        key, mapping = (self.canonical(ops, external, owned, entry) if self.quotient else
                        (self.key(ops, external, owned, entry, identity), identity))
        if key in self.cache:
            self.stats['hits'] += 1
        else:
            self.stats['misses'] += 1
            selected, resident, written, entry = key
            stabilizer = [p for p in self.automorphisms if self.key(selected, resident, written, entry, p)==key]
            seen, points = set(), []
            for order in topological_orders(self.graph, selected):
                if self.quotient:
                    orbit = min(tuple(p.ops[o] for o in order) for p in stabilizer)
                    if orbit in seen: continue
                    seen.add(orbit)
                g = reordered(self.graph, order)
                stats = {}
                result = curve(g, partitions='dp', witness=True, stats=stats,
                               external=resident, written=written, entry=entry)
                self.stats['order_calls'] += 1
                self.stats['solve_entries'] += stats['solve_cache']['currsize']
                self.stats['group_entries'] += stats['group_cache']['currsize']
                points.extend((c, q, Plan(order, w)) for c, q, w in result)
            self.cache[key] = pareto(points)
        backward_op = {v:k for k,v in mapping.ops.items()}
        backward_tensor = {v:k for k,v in mapping.tensors.items()}
        return tuple((c,q,renamed(p,backward_op,backward_tensor)) for c,q,p in self.cache[key])
