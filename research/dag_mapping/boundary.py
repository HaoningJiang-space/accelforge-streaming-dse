"""Exact composition for a fixed serial region partition in graph grammar v2.

This is a boundary diagnostic, not a new complete DAG search algorithm.
Regions can contain branches. A shared loop may surround all regions, so region
boundaries do not necessarily imply whole-tensor materialization. Numeric units
are the existing grammar's one-byte cells; layout is its fixed rank projection.
"""
from itertools import product
from math import prod
from time import perf_counter

from research.index_coupling.graph.curve import curve, pareto, tile_sizes
from research.index_coupling.graph.model import Graph, residual


def workload(kind, shape):
    if kind in ('chain', 'residual'):
        graph = residual(*shape, depth=2, reads_x=True)
        if kind == 'chain':
            # Structural control: same two contractions, no skip input at join.
            del graph.access['EAdd']['X']
        return graph, (('EX',), ('EH0', 'EH1'), ('EAdd',))
    if kind not in ('fork_join', 'gated_fork_join'):
        raise ValueError('unknown graph family')
    i, j, k, l = shape
    ops = [('EX', {'A': ('I', 'J'), 'B': ('J', 'K'), 'X': ('I', 'K')})]
    for n in (0, 1):
        ops.append((f'E{n}', {'X': ('I', 'K'), f'C{n}': ('K', 'L'),
                              f'U{n}': ('I', 'L')}))
    left = 'U0'
    middle = ['E0', 'E1']
    if kind == 'gated_fork_join':
        # An asymmetric elementwise product, not a model of SiLU/sigmoid.
        ops.append(('Gate', {'U0': ('I', 'L'), 'G': ('I', 'L'), 'V0': ('I', 'L')}))
        left = 'V0'
        middle.append('Gate')
    ops.append(('Join', {left: ('I', 'L'), 'U1': ('I', 'L'), 'Y': ('I', 'L')}))
    return Graph(dict(I=i, J=j, K=k, L=l), ops), (('EX',), tuple(middle), ('Join',))


def resized(graph, sizes, ops=None):
    return Graph(dict(sizes), [(o, dict(graph.access[o]))
                              for o in (graph.ops if ops is None else ops)])


def size(graph, tensor, sizes):
    return prod(sizes[v] for v in graph.dims(tensor))


def compulsory(graph, sizes, external=()):
    boundary = (graph.consumed() - graph.produced()) | (graph.produced() - graph.consumed())
    return sum(size(graph, t, sizes) for t in boundary - set(external))


def boundary_description(graph, regions):
    """Incidence and remaining uses, not just tensor counts at a linear cut."""
    writer = {graph.output(o): o for o in graph.ops}
    records = []
    completed = set()
    for region in regions:
        selected = set(region)
        tensors = graph.tensors(region)
        crossing = [t for t in tensors if t not in writer or not graph.consumers(t)
                    or (set(graph.consumers(t)) | {writer.get(t)}) - selected - {None}]
        records.append(dict(
            operators=list(region),
            iteration_domains={o: sorted(graph.rank_vars((o,))) for o in region},
            boundary=[dict(tensor=t, ranks=list(graph.dims(t)), producer=writer.get(t),
                           consumers=graph.consumers(t),
                           remaining_consumers=[o for o in graph.consumers(t)
                                                if o not in completed | selected])
                      for t in sorted(crossing)],
        ))
        completed.update(selected)
    return records


class RegionComposer:
    """Memoized conditional group responses with caller-owned boundary costs."""

    def __init__(self, graph, *, verify=False):
        self.graph = graph
        self.verify = verify
        self.cache = {}
        self.stats = dict(region_requests=0, region_misses=0, region_response_points=0,
                          child_dp_transitions=0, child_loop_choices=0,
                          join_candidates=0, boundary_masks=0, native_checks=0,
                          child_generation_seconds=0., native_check_seconds=0.)

    def response(self, ops, sizes, external, owned):
        graph = resized(self.graph, sizes, ops)
        external = frozenset(external) & graph.tensors(ops)
        owned = frozenset(owned) & graph.produced()
        key = (tuple(ops), tuple(sorted(sizes.items())), tuple(sorted(external)), tuple(sorted(owned)))
        self.stats['region_requests'] += 1
        if key not in self.cache:
            start = perf_counter()
            ledger = {}
            raw = curve(graph, witness=True, partitions='dp', scalar_leaf='v2',
                        entry='group', external=external, written=owned, stats=ledger)
            base = compulsory(graph, sizes, external)
            self.cache[key] = tuple((c, q - base, w) for c, q, w in raw)
            self.stats['child_generation_seconds'] += perf_counter() - start
            self.stats['region_misses'] += 1
            self.stats['region_response_points'] += len(raw)
            self.stats['child_dp_transitions'] += ledger['dp_transitions']
            self.stats['child_loop_choices'] += ledger['loop_choices']
        return self.cache[key]

    def compose(self, regions, sizes=None, *, external=(), owned=(), materialize=False):
        """Return EXTRA traffic, excluding caller reservations and root transfers.

Exact only for these ordered sibling regions, their keep/DRAM decisions, and
the native part entry within each child (including v2's whole-scalar Hold).
No loop spans the regions
unless the caller explicitly wraps this response with such a loop.
"""
        graph = self.graph
        sizes = dict(graph.sizes if sizes is None else sizes)
        regions = tuple(tuple(r) for r in regions)
        order = tuple(o for r in regions for o in r)
        if len(order) != len(graph.ops) or set(order) != set(graph.ops) or any(not r for r in regions):
            raise ValueError('regions must partition all operators exactly once')
        position = {o: i for i, o in enumerate(order)}
        writer = {graph.output(o): o for o in graph.ops}
        if any(position[writer[t]] >= position[o] for o in order
               for t in list(graph.access[o])[:-1] if t in writer):
            raise ValueError('region order violates producer-consumer dependencies')
        external, owned = frozenset(external), frozenset(owned)
        users = {t: [i for i, r in enumerate(regions) if t in graph.tensors(r)]
                 for t in graph.tensors(order) - external}
        shared = sorted(t for t, uses in users.items() if len(uses) > 1)
        choices = [(False,) * len(shared)] if materialize else product((False, True), repeat=len(shared))
        results = []
        for bits in choices:
            self.stats['boundary_masks'] += 1
            kept = frozenset(t for t, bit in zip(shared, bits) if bit)
            dropped = set(shared) - kept
            # One final write plus one read per consumer region; shared inputs
            # already have their first read in the root compulsory charge.
            extra = sum(size(graph, t, sizes) * (
                int(t not in owned) + len(users[t]) - 1 if t in writer
                else len(users[t]) - 1) for t in dropped)
            child_owned = owned | (dropped & graph.produced() & graph.consumed())
            note = ('groups', regions, 'kept', tuple(sorted(kept)), 'via DRAM', tuple(sorted(dropped)))
            frontier = ((0, extra, (note,)),)
            for i, region in enumerate(regions):
                across = sum(size(graph, t, sizes) for t in kept if users[t][0] <= i <= users[t][-1])
                live = graph.tensors(region) - external - kept
                if (len(regions) == 1 and len(region) > 1
                        and all(size(graph, t, sizes) == 1 for t in live)):
                    # Native part_curve does not delegate a scalar whole-parent
                    # part to group: doing so would silently allow repartition.
                    child = ((len(live), 0, (('hold', region),)),)
                else:
                    child = self.response(region, sizes, external | kept, child_owned)
                self.stats['join_candidates'] += len(frontier) * len(child)
                frontier = pareto((max(p, across + c), q + t, w + v)
                                  for p, q, w in frontier for c, t, v in child)
            if self.verify:
                start = perf_counter()
                ordered = resized(graph, sizes, order)
                raw = curve(ordered, partitions='dp', scalar_leaf='v2',
                            external=external, written=owned,
                            root_groups=regions, root_kept=kept)
                expected = tuple((c, q - compulsory(ordered, sizes, external)) for c, q in raw)
                actual = tuple(p[:2] for p in frontier)
                if actual != expected:
                    raise AssertionError(dict(regions=regions, sizes=sizes, external=sorted(external),
                                              owned=sorted(owned), kept=sorted(kept),
                                              expected=expected, actual=actual))
                self.stats['native_checks'] += 1
                self.stats['native_check_seconds'] += perf_counter() - start
            results.extend(frontier)
        return pareto(results)

    def shared_loop(self, regions, rank='I'):
        """Fixed whole-DAG loop rank, every proper halving tile and keep mask.

This preserves a common loop across region boundaries; its children are the
same closed region interfaces. It is a subset of complete native search.
"""
        graph, sizes = self.graph, self.graph.sizes
        common = set.intersection(*(graph.rank_vars((o,)) for o in graph.ops))
        inside = graph.produced() & graph.consumed()
        if rank not in common or any(rank not in graph.dims(t) for t in inside):
            raise ValueError('illegal common loop: absent rank or unfinished intermediate')
        lacking = sorted(t for t in graph.tensors(graph.ops) if rank not in graph.dims(t))
        order = tuple(o for r in regions for o in r)
        points = []
        for tile in tile_sizes(sizes[rank]):
            trips = sizes[rank] // tile
            for bits in product((False, True), repeat=len(lacking)):
                kept = frozenset(t for t, bit in zip(lacking, bits) if bit)
                dropped = set(lacking) - kept
                reservation = sum(size(graph, t, sizes) for t in kept)
                traffic = sum((2 if t in graph.produced() else 1) * (trips - 1)
                              * size(graph, t, sizes) for t in dropped)
                child = self.compose(regions, dict(sizes, **{rank: tile}), external=kept)
                notes = (('groups', (order,), 'kept', (), 'via DRAM', ()),
                         ('loop', order, rank, f'tile {tile} x{trips}',
                          'kept', tuple(sorted(kept)), 'refetched', tuple(sorted(dropped))))
                points.extend((reservation + c, traffic + trips * q, notes + w) for c, q, w in child)
        return pareto(points)
