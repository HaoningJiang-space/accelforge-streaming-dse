"""Invocation-local reuse of closed responses across legal global orders.

The local operator order is NEVER quotiented. One session fixes the graph,
numeric policy and witness namespace. Existing native per-order caches remain.
"""
import ast
from functools import wraps
import hashlib
import json
from time import perf_counter

from research.index_coupling.graph.model import Graph
from research.index_coupling.response import prefix
from research.index_coupling.response.substitution import make_exact_kernel, expand
from research.index_coupling.unified_search import scalar_separator_certificate
from .hierarchy import Model


class ResponsePool:
    def __init__(self, audit=False):
        self.audit = audit
        self.entries = {}
        self.order = None
        self.stack = []
        self.verifying = False
        self.counts = dict(requests=0, hits=0, misses=0, cross_order_hits=0,
                           verified=0, verified_empty=0, verified_multiop=0)
        self.digest = hashlib.sha256()
        self.examples = []

    def decorator(self, stage):
        def wrap(fn):
            @wraps(fn)
            def call(ops, ext, external, owned, *tail):
                if any(tail):
                    raise ValueError('constrained response cannot enter shared pool')
                key = (stage, ops, ext, external, owned)
                # An audit reference executes the unshared body. It may use
                # native local caches, but cannot get a new answer from this pool.
                if self.verifying:
                    return fn(ops, ext, external, owned, *tail)
                self.counts['requests'] += 1
                if key in self.entries:
                    points, origin, ancestry = self.entries[key]
                    self.counts['hits'] += 1
                    self.counts['cross_order_hits'] += origin != self.order
                    if self.audit:
                        self.verifying = True
                        try:
                            reference = fn(ops, ext, external, owned, *tail)
                        finally:
                            self.verifying = False
                        a, b = tuple(p[:2] for p in points), tuple(p[:2] for p in reference)
                        if a != b:
                            raise AssertionError('complete conditional frontier mismatch')
                        self.counts['verified'] += 1
                        self.counts['verified_empty'] += not points
                        self.counts['verified_multiop'] += len(ops) > 1
                        state = dict(entry=stage, ops=ops, ext=ext,
                                     external=sorted(external), owned=sorted(owned))
                        self.digest.update(json.dumps((state, origin, self.order, a), sort_keys=True).encode())
                        if len(self.examples) < 8 and len(ops) > 1 and origin != self.order:
                            self.examples.append(dict(state=state, origin=origin, destination=self.order,
                                                      origin_ancestors=ancestry,
                                                      destination_ancestors=list(self.stack), frontier=a))
                    return points
                self.counts['misses'] += 1
                ancestry = list(self.stack) if self.audit else None
                self.stack.append((stage, ops))
                try:
                    result = fn(ops, ext, external, owned, *tail)
                finally:
                    self.stack.pop()
                self.entries[key] = (result, self.order, ancestry)
                return result
            return call
        return wrap

    def summary(self):
        return dict(self.counts, entries=len(self.entries),
                    cached_points=sum(len(v[0]) for v in self.entries.values()),
                    audit_digest=self.digest.hexdigest() if self.audit else None,
                    examples=self.examples)


class RegionSession:
    """One fixed graph and policy; exact default v2, unlimited capacity.

    Share only identical ordered (entry, span, extents, R, W) responses.
    Scalar whole-part Hold stays in native part_curve, outside the pool.
    Every query still runs one globally consistent topological order.
    """
    def __init__(self, graph, *, shared=False, unit=False, certificate=False, audit=False, tile_domain='halving'):
        start = perf_counter()
        self.graph = Graph(dict(graph.sizes), [(o, {t: tuple(ds) for t, ds in graph.access[o].items()})
                                               for o in graph.ops])
        Model(self.graph, tile_domain)
        self.tile_domain, self.unit = tile_domain, unit
        self.pool = ResponsePool(audit=audit) if shared else None
        self.recovery_cache = {}

        def transform(tree):
            prefix.transform(tree, projection=True, frames=True, composition='numeric')
            outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'curve')
            if certificate:
                solver = next(n for n in outer.body if isinstance(n, ast.FunctionDef) and n.name == '_solve')
                leaf = ast.dump(ast.parse('not constrained and all(size(t, ext) == 1 for t in live)', mode='eval').body)
                anchors = [i for i, n in enumerate(solver.body) if isinstance(n, ast.If) and ast.dump(n.test) == leaf]
                if len(anchors) != 1:
                    raise ValueError('native scalar entry anchor changed')
                solver.body[anchors[0]+1:anchors[0]+1] = ast.parse('''
_cert = _closed_certificate(graph, ops, ext, external, owned, names)
if stats is not None:
    stats['separator_checks'] = stats.get('separator_checks', 0) + 1
    stats['separator_hits'] = stats.get('separator_hits', 0) + (_cert is not None)
if _cert is not None:
    return ((_cert['capacity'], 0, _cert['notes'] if witness else ()),)
''').body
            if self.pool is not None:
                found = set()
                for node in outer.body:
                    if not isinstance(node, ast.FunctionDef):
                        continue
                    stage = {'_solve': 'solve', '_group_curve': 'group'}.get(node.name)
                    if stage:
                        found.add(stage)
                        # Native lru_cache stays OUTSIDE the session lookup.
                        node.decorator_list.append(ast.Call(
                            ast.Attribute(ast.Name('_closed_pool', ast.Load()), 'decorator', ast.Load()),
                            [ast.Constant(stage)], []))
                if found != {'solve', 'group'}:
                    raise ValueError('native response anchors changed')

        if unit:
            self.kernel, self.registry = make_exact_kernel(transform=transform)
        else:
            tree = ast.parse(prefix.SOURCE.read_text(), filename=str(prefix.SOURCE))
            transform(tree)
            namespace = dict(__name__='research.index_coupling.graph._dag_region_session',
                             __package__='research.index_coupling.graph')
            exec(compile(ast.fix_missing_locations(tree), str(prefix.SOURCE), 'exec'), namespace)
            self.kernel, self.registry = namespace['curve'], {}
        self.kernel.__globals__['_closed_pool'] = self.pool
        self.kernel.__globals__['_closed_certificate'] = scalar_separator_certificate
        self.install_seconds = perf_counter() - start
        self.active = False

    def query(self, order=None, *, external=(), owned=(), entry='solve', stats=None):
        if self.active:
            raise ValueError('session queries are serial')
        order = self.graph.ops if order is None else tuple(order)
        if len(order) != len(self.graph.ops) or set(order) != set(self.graph.ops):
            raise ValueError('query must order the entire fixed graph')
        ordered = Graph(dict(self.graph.sizes), [(o, dict(self.graph.access[o])) for o in order])
        Model(ordered, self.tile_domain)  # also rejects non-topological permutations
        if not (set(external) | set(owned)) <= ordered.tensors(order):
            raise ValueError('unknown boundary tensor')
        self.active = True
        if self.pool is not None:
            self.pool.order = order
        try:
            return self.kernel(ordered, witness=True, partitions='dp', scalar_leaf='v2',
                               tile_domain=self.tile_domain, external=external, written=owned,
                               entry=entry, stats=stats)
        finally:
            self.active = False

    def recover(self, notes):
        # The registry and witness-concatenation namespace live for the same
        # session as the pooled responses. No cross-session pointers are used.
        return expand(self.graph, notes, self.registry, self.recovery_cache) if self.unit else notes
