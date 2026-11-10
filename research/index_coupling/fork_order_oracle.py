"""Independent reference: Pareto union of unchanged fixed-order curve calls."""
from collections import defaultdict
from itertools import permutations
from math import prod
from time import perf_counter

from .graph.curve import curve, pareto
from .graph.fork_quotient import Plan, reordered
from .graph.model import Graph
from .simulate_nest import simulate


def orders(graph, external=frozenset(), *, quotient=True):
    """Distinct decorated-profile words, or every literal permutation.

This removes only permutations preserving the complete boundary decoration;
it does not sort different residency profiles into a single fixed order.
    """
    if not quotient:
        yield from (('EX',) + p for p in permutations(graph.ops[1:]))
        return
    pools = defaultdict(list)
    for op in graph.ops[1:]:
        out = graph.output(op)
        inp = next(t for t in graph.access[op] if t not in ('X', out))
        key = (tuple(graph.dims(inp)), tuple(graph.dims(out)), inp in external, out in external)
        pools[key].append(op)
    pools = [pools[k] for k in sorted(pools)]
    used = [0] * len(pools)

    def visit(prefix):
        if len(prefix) == len(graph.ops):
            yield tuple(prefix)
        for i, pool in enumerate(pools):
            if used[i] < len(pool):
                op = pool[used[i]]; used[i] += 1
                yield from visit(prefix + [op])
                used[i] -= 1

    yield from visit(['EX'])


def envelope(graph, *, external=frozenset(), entry='solve', written=False,
             tile_domain='halving', quotient=True, ledger=None, order_callback=None):
    ledger = {} if ledger is None else ledger
    ledger.update(orders=0, solve_entries=0, group_entries=0, dp_transitions=0, loop_choices=0)
    result, start = [], perf_counter()
    for order in orders(graph, external, quotient=quotient):
        stats = {}
        points = curve(reordered(graph, order), partitions='dp', witness=True, stats=stats,
                       external=external, entry=entry, written={'X'} if written else (),
                       tile_domain=tile_domain)
        result.extend((c, q, Plan(order, w)) for c, q, w in points)
        ledger['orders'] += 1
        ledger['solve_entries'] += stats['solve_cache']['currsize']
        ledger['group_entries'] += stats['group_cache']['currsize']
        ledger['dp_transitions'] += stats['dp_transitions']
        ledger['loop_choices'] += stats['loop_choices']
        if order_callback:
            order_callback(order, points, stats)
    ledger['seconds'] = perf_counter() - start
    return pareto(result)


def replay_private_boundary(graph, external, capacity, traffic, plan):
    """Execute a conditional solve witness inside a genuine retaining loop.

Only graph inputs/terminal outputs may be pinned. Add a rank Z of extent two
to every NONexternal tensor, retain the external cells across two Z iterations.
The original recurrence/executor are unchanged. The wrapper pays the excluded
reservations and compulsory reads/final writes explicitly.
    """
    external = frozenset(external)
    if external & (graph.produced() & graph.consumed()):
        raise ValueError('wrapper cannot pin an internal producer/consumer tensor')
    if not external:
        actual = simulate(reordered(graph, plan.order), plan.notes)
        expected = capacity, traffic
    else:
        rank = '_boundary_iteration'
        wrapped = Graph(dict(graph.sizes, **{rank: 2}), [
            (op, {t: tuple(ds) if t in external else tuple(ds) + (rank,)
                  for t, ds in graph.access[op].items()}) for op in plan.order])
        reservation = sum(prod(graph.sizes[v] for v in graph.dims(t)) for t in external)
        wrapper = (('groups', (plan.order,), 'kept', (), 'via DRAM', ()),
                   ('loop', plan.order, rank, 'tile 1 x2', 'kept', tuple(sorted(external)), 'refetched', ()))
        actual = simulate(wrapped, wrapper + plan.notes)
        expected = capacity + reservation, 2 * traffic + reservation
    return dict(exact=actual['valid'] and (actual['peak'], actual['traffic']) == expected,
                expected=list(expected), actual=actual)
