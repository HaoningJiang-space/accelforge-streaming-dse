"""Lazy, unpruned derivations of the curve grammar for tiny-graph audits.

No subplan collection or Cartesian product is materialized. Memory follows the
active recursion and witness, not the number of derivations. This trades cache
reuse for bounded memory; exhaustive running time is still exponential.
The API intentionally covers the audit's unconstrained, exact grammar only.
"""
from dataclasses import dataclass
from itertools import product
from math import prod
from time import monotonic

from .curve import cat, flatten


class BudgetExceeded(Exception):
    pass


@dataclass
class Budget:
    max_nodes: int = 2_000_000
    deadline: float = float('inf')
    expanded: int = 0

    def tick(self):
        if monotonic() >= self.deadline:
            raise BudgetExceeded('timeout')
        if self.expanded >= self.max_nodes:
            raise BudgetExceeded('node_limit')
        self.expanded += 1


def iter_plans(graph, *, legacy_nested_writes=False, max_capacity=float('inf'), budget=None):
    """Yield (capacity, traffic, flat witness), counting derivations, not uniques.

    Pricing duplicates the enumerating recurrence, deliberately without Pareto
    pruning. Differential tests compare its entire multiset with that recurrence
    on tiny graphs; simulate_nest independently checks execution.
    """
    budget = budget if budget is not None else Budget()
    names = sorted(graph.sizes)
    dims = {t: graph.dims(t) for t in graph.tensors(graph.ops)}
    axes = {t: tuple(names.index(v) for v in d) for t, d in dims.items()}
    output = graph.output
    consumed, produced = graph.consumed(), graph.produced()

    def size(t, ext):
        return prod(ext[i] for i in axes[t])

    def solve(ops, ext, external, owned):
        budget.tick()
        live = graph.tensors(ops) - external
        if all(size(t, ext) == 1 for t in live):
            if len(live) <= max_capacity:
                yield len(live), 0, ()
            return
        for mask in range(1 << (len(ops) - 1)):
            budget.tick()
            groups, start = [], 0
            for i in range(len(ops) - 1):
                if mask >> i & 1:
                    groups.append(ops[start:i + 1])
                    start = i + 1
            groups.append(ops[start:])
            users = {}
            for i, group in enumerate(groups):
                for t in graph.tensors(group) - external:
                    users.setdefault(t, []).append(i)
            shared = sorted(t for t, gs in users.items() if len(gs) > 1)
            for bits in product((True, False), repeat=len(shared)):
                budget.tick()
                kept = frozenset(t for t, k in zip(shared, bits) if k)
                dropped = tuple(t for t, k in zip(shared, bits) if not k)
                extra, written = 0, set()
                for t in dropped:
                    gs = users[t]
                    writers = [i for i in gs if any(output(op) == t for op in groups[i])]
                    if writers and t in consumed:
                        extra += size(t, ext) * ((t not in owned) + len(gs) - len(writers))
                        written.add(t)
                    elif writers:
                        extra += 2 * size(t, ext) * (len(writers) - 1)
                    else:
                        extra += size(t, ext) * (len(gs) - 1)
                child_owned = owned if legacy_nested_writes else owned | written
                note = (('groups', tuple(groups), 'kept', tuple(sorted(kept)), 'via DRAM', dropped),)

                def siblings(i, cap, traffic, witness):
                    budget.tick()
                    if i == len(groups):
                        yield cap, traffic, witness
                        return
                    across = sum(size(t, ext) for t in kept if min(users[t]) <= i <= max(users[t]))
                    for c, q, w in group_curve(groups[i], ext, external | kept, child_owned):
                        peak = max(cap, across + c)
                        if peak <= max_capacity:
                            yield from siblings(i + 1, peak, traffic + q, cat(witness, w))

                yield from siblings(0, 0, extra, note)

    def group_curve(ops, ext, external, owned):
        budget.tick()
        live = graph.tensors(ops) - external
        if all(size(t, ext) == 1 for t in live):
            if len(live) <= max_capacity:
                yield len(live), 0, ()
            return
        common = set.intersection(*(graph.rank_vars((op,)) for op in ops))
        made = {output(op) for op in ops}
        inside_made = made & {t for op in ops for t in list(graph.access[op])[:-1]}
        for v in common:
            i = names.index(v)
            extent = ext[i]
            if extent == 1 or any(v not in dims[t] for t in inside_made - external):
                continue
            lacking = sorted(t for t in live if v not in dims[t])
            b = extent // 2
            while b >= 1:
                if extent % b == 0:
                    trips = extent // b
                    inner_ext = ext[:i] + (b,) + ext[i + 1:]
                    for bits in product((True, False), repeat=len(lacking)):
                        budget.tick()
                        kept = frozenset(t for t, k in zip(lacking, bits) if k)
                        cap = sum(size(t, ext) for t in kept)
                        extra = sum((2 if t in made else 1) * (trips - 1) * size(t, ext)
                                    for t, k in zip(lacking, bits) if not k)
                        note = (('loop', ops, v, f'tile {b} x{trips}', 'kept', tuple(sorted(kept)),
                                 'refetched', tuple(t for t, k in zip(lacking, bits) if not k)),)
                        for c, q, w in solve(ops, inner_ext, external | kept, owned):
                            if cap + c <= max_capacity:
                                yield cap + c, extra + trips * q, cat(note, w)
                b //= 2

    ext = tuple(graph.sizes[v] for v in names)
    compulsory = sum(size(t, ext) for t in (consumed - produced) | (produced - consumed))
    for c, q, w in solve(graph.ops, ext, frozenset(), frozenset()):
        budget.tick()
        yield c, q + compulsory, flatten(w)
