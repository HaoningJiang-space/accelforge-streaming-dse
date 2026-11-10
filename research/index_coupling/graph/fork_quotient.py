"""Exact all-consumer-order quotient for model.fork, ordinary serial costs.

Separate grammar/API from curve.py. Only homogeneous private pairs within a
literal k/i role are interchangeable. A state retains their JOINT input/output
residency profiles, shared residency, extents, producer presence and X ownership.
Every returned plan carries one consistent global operator order.
"""
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from math import prod
from time import perf_counter

from .curve import merge_staircases, pareto, tile_sizes
from .model import Graph, fork


@dataclass(frozen=True)
class Plan:
    order: tuple
    notes: tuple = ()


def reordered(graph, order):
    return Graph(dict(graph.sizes), [(op, dict(graph.access[op])) for op in order])


def renamed(plan, op_map, tensor_map):
    notes = []
    for note in plan.notes:
        if note[0] == 'groups':
            notes.append(('groups', tuple(tuple(op_map[o] for o in g) for g in note[1]),
                          'kept', tuple(sorted(tensor_map[t] for t in note[3])),
                          'via DRAM', tuple(sorted(tensor_map[t] for t in note[5]))))
        else:
            notes.append(('loop', tuple(op_map[o] for o in note[1]), note[2], note[3],
                          'kept', tuple(sorted(tensor_map[t] for t in note[5])),
                          'refetched', tuple(sorted(tensor_map[t] for t in note[7]))))
    return Plan(tuple(op_map[o] for o in plan.order), tuple(notes))


class ForkQuotient:
    """One shape/role multiset; memoized all-order conditional responses.

Only exact historical-halving or all-divisor tiles, ordinary spill cost two,
unrestricted sharing/write-through, and no fixed-root/cut constraints. Input
identity remains visible in returned plans. Not a general DAG optimizer.
    """

    def __init__(self, shape, roles, *, tile_domain='halving', quotient=True):
        if not roles or set(roles) - {'k', 'i'} or len(shape) != 4 or any(n < 1 for n in shape):
            raise ValueError('positive fork dimensions and nonempty k/i roles required')
        if tile_domain not in ('halving', 'divisors'):
            raise ValueError('unknown tile domain')
        self.graph = fork(*shape, roles)
        self.tile_domain = tile_domain
        self.quotient = quotient  # False is the labeled ALL-order recurrence, not fixed-order curve.py.
        self.ranks = tuple(sorted(self.graph.sizes))
        self.info = {}
        self.slots = {r: [] for r in ('k', 'i')}
        for op, role in zip(self.graph.ops[1:], roles):
            acc = self.graph.access[op]
            inp = next(t for t in acc if t != 'X' and t != self.graph.output(op))
            self.info[op] = role, inp, self.graph.output(op)
            self.slots[role].append(op)
        self.stats = dict(partition_choices=0, sequence_choices=0, loop_choices=0,
                          max_frontier=0, canonical_calls=0, renamed_responses=0)
        # Instance-local memoization: completed studies do not leak graph objects.
        self.solve = lru_cache(None)(self._solve)
        self.group = lru_cache(None)(self._group)
        self.sequence = lru_cache(None)(self._sequence)
        self.metadata = lru_cache(None)(self._metadata)

    def _metadata(self, ops):
        g = self.graph
        tensors = frozenset(g.tensors(ops))
        made = frozenset(g.output(o) for o in ops)
        read = frozenset(t for o in ops for t in g.access[o] if t != g.output(o))
        common = set.intersection(*(g.rank_vars((o,)) for o in ops)) if ops else set()
        used = g.rank_vars(ops)
        return tensors, made, made & read, tuple(sorted(common)), used

    def size(self, tensor, ext):
        return prod(ext[self.ranks.index(v)] for v in self.graph.dims(tensor))

    def profile(self, op, external):
        _, inp, out = self.info[op]
        return int(inp in external) + 2 * int(out in external)

    def canonical(self, ops, ext, external, owned):
        self.stats['canonical_calls'] += 1
        if not self.quotient:
            ops = tuple(o for o in self.graph.ops if o in ops)
            tensors, _, _, _, used = self.metadata(ops)
            ext = tuple(n if v in used else 1 for v, n in zip(self.ranks, ext))
            return ((ops, ext, frozenset(external) & tensors, bool(owned and 'EX' in ops)),
                    {o: o for o in ops}, {t: t for t in tensors})
        ordered, forward_op, forward_tensor = [], {}, {'A': 'A', 'B': 'B', 'X': 'X'}
        if 'EX' in ops:
            ordered.append('EX'); forward_op['EX'] = 'EX'
        for role in ('k', 'i'):
            members = sorted((o for o in ops if o != 'EX' and self.info[o][0] == role),
                             key=lambda o: (self.profile(o, external), self.slots[role].index(o)))
            for old, new in zip(members, self.slots[role]):
                ordered.append(new); forward_op[old] = new
                for a, b in zip(self.info[old][1:], self.info[new][1:]):
                    forward_tensor[a] = b
        ops = tuple(ordered)
        tensors, _, _, _, used = self.metadata(ops)
        ext = tuple(n if v in used else 1 for v, n in zip(self.ranks, ext))
        external = frozenset(forward_tensor[t] for t in external if t in forward_tensor) & tensors
        owned = bool(owned and 'EX' in ops)
        reverse_op = {v: k for k, v in forward_op.items()}
        reverse_tensor = {v: k for k, v in forward_tensor.items()}
        return (ops, ext, external, owned), reverse_op, reverse_tensor

    def call(self, fn, ops, ext, external, owned):
        key, om, tm = self.canonical(ops, ext, external, owned)
        points = fn(*key)
        if all(a == b for a, b in om.items()) and all(a == b for a, b in tm.items()):
            return points
        self.stats['renamed_responses'] += 1
        if fn is self.sequence:
            return tuple((c, q, tuple(renamed(p, om, tm) for p in plans)) for c, q, plans in points)
        return tuple((c, q, renamed(plan, om, tm)) for c, q, plan in points)

    def prune(self, points):
        result = pareto(points)
        self.stats['max_frontier'] = max(self.stats['max_frontier'], len(result))
        return result

    def selections(self, ops, external):
        """One consumer subset per orbit under the current state's stabilizer."""
        if not self.quotient:
            consumers = tuple(o for o in ops if o != 'EX')
            for bits in product((False, True), repeat=len(consumers)):
                yield tuple(o for o, take in zip(consumers, bits) if take)
            return
        buckets = defaultdict(list)
        for op in ops:
            if op != 'EX':
                buckets[self.info[op][0], self.profile(op, external)].append(op)
        classes = [buckets[k] for k in sorted(buckets)]
        for counts in product(*(range(len(cls) + 1) for cls in classes)):
            yield tuple(o for cls, n in zip(classes, counts) for o in cls[:n])

    def _solve(self, ops, ext, external, owned):
        live = self.metadata(ops)[0] - external
        if all(self.size(t, ext) == 1 for t in live):
            return ((len(live), 0, Plan(ops)),)
        results = [(c, q, Plan(p.order, (('groups', (p.order,), 'kept', (), 'via DRAM', ()),) + p.notes))
                   for c, q, p in self.call(self.group, ops, ext, external, owned)]
        if len(ops) == 1:
            return tuple(results)
        sx = self.size('X', ext)
        for keep in ((None,) if 'X' in external else (True, False)):
            child_ext = external | {'X'} if keep else external
            child_owned = owned or (keep is False and 'EX' in ops)
            allocation = sx if keep is True else 0
            for selected in self.selections(ops, external):
                first = (('EX',) if 'EX' in ops else ()) + selected
                if not first or len(first) == len(ops):
                    continue
                rest = tuple(o for o in ops if o not in first)
                self.stats['partition_choices'] += 1
                a = self.call(self.group, first, ext, child_ext, child_owned)
                b = self.call(self.sequence, rest, ext, child_ext, child_owned)
                # sequence charges each DRAM-backed X read. The first group
                # already has its baseline read; a producer's final store is
                # owned exactly once by this nontrivial partition instead.
                write = sx if keep is False and 'EX' in ops and not owned else 0
                for c, q, first_plan, tail in merge_staircases(a, b):
                    plans = (first_plan,) + tail
                    order = tuple(o for p in plans for o in p.order)
                    note = ('groups', tuple(p.order for p in plans), 'kept',
                            ('X',) if keep is True else (), 'via DRAM', ('X',) if keep is False else ())
                    results.append((allocation + c, write + q,
                                    Plan(order, (note,) + tuple(n for p in plans for n in p.notes))))
        return self.prune(results)

    def _sequence(self, ops, ext, external, owned):
        # Consumer-only suffix of a partition, not a solve-entry substitution.
        if not ops:
            return ((0, 0, ()),)
        assert 'EX' not in ops
        extra = 0 if 'X' in external else self.size('X', ext)
        results = []
        for first in self.selections(ops, external):
            if not first:
                continue
            self.stats['sequence_choices'] += 1
            rest = tuple(o for o in ops if o not in first)
            a = self.call(self.group, first, ext, external, owned)
            b = self.call(self.sequence, rest, ext, external, owned)
            for c, q, plan, tail in merge_staircases(a, b):
                results.append((c, extra + q, (plan,) + tail))
        return self.prune(results)

    def _group(self, ops, ext, external, owned):
        tensors, made, inside, common, _ = self.metadata(ops)
        live = tensors - external
        if all(self.size(t, ext) == 1 for t in live):
            return ((len(live), 0, Plan(ops)),)
        results = []
        for rank in common:
            pos = self.ranks.index(rank)
            if ext[pos] == 1 or any(rank not in self.graph.dims(t) for t in inside - external):
                continue
            lacking = {t for t in live if rank not in self.graph.dims(t)}
            classes = defaultdict(list)
            for t in sorted(lacking):
                if not self.quotient:
                    key = ('tensor', t)
                elif t in ('A', 'B', 'X'):
                    key = ('shared', t)
                else:
                    op = next(o for o in ops if o != 'EX' and t in self.info[o][1:])
                    key = (self.info[op][0], self.profile(op, external), t == self.info[op][2])
                classes[key].append(t)
            classes = list(classes.values())
            for tile in tile_sizes(ext[pos], self.tile_domain):
                trips = ext[pos] // tile
                inner_ext = ext[:pos] + (tile,) + ext[pos + 1:]
                for counts in product(*(range(len(cls) + 1) for cls in classes)):
                    self.stats['loop_choices'] += 1
                    kept = frozenset(t for cls, n in zip(classes, counts) for t in cls[:n])
                    dropped = lacking - kept
                    allocation = sum(self.size(t, ext) for t in kept)
                    extra = (trips - 1) * sum((2 if t in made else 1) * self.size(t, ext) for t in dropped)
                    for c, q, plan in self.call(self.solve, ops, inner_ext, external | kept, owned):
                        note = ('loop', plan.order, rank, f'tile {tile} x{trips}',
                                'kept', tuple(sorted(kept)), 'refetched', tuple(sorted(dropped)))
                        results.append((allocation + c, extra + trips * q, Plan(plan.order, (note,) + plan.notes)))
        return self.prune(results)

    def curve(self, *, external=frozenset(), entry='solve', written=False):
        if entry not in ('solve', 'group'):
            raise ValueError('entry must be solve or group')
        external = frozenset(external)
        if not external <= self.graph.tensors(self.graph.ops):
            raise ValueError('unknown resident tensor')
        start = perf_counter()
        ext = tuple(self.graph.sizes[v] for v in self.ranks)
        points = self.call(self.solve if entry == 'solve' else self.group,
                           self.graph.ops, ext, external, bool(written))
        inputs = self.graph.consumed() - self.graph.produced()
        outputs = self.graph.produced() - self.graph.consumed()
        compulsory = sum(self.size(t, ext) for t in (inputs | outputs) - external)
        self.stats.update(last_query_seconds=perf_counter() - start,
                          **{f'{name}_cache': getattr(self, name).cache_info()._asdict()
                             for name in ('solve', 'group', 'sequence')})
        return tuple((c, compulsory + q, plan) for c, q, plan in points)
