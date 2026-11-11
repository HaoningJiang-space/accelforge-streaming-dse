"""Opt-in exact-response substitution for unit-M chain states (CONTRACTION_ORACLE.md §16).

`make_exact_kernel()` returns a curve() variant, adapted in memory as in
unified_search.make_kernel: right after the scalar-leaf rule of _solve, a
state recognised as a unit-M chain with at least one contraction returns its
closed-form frontier (forms.predict) instead of recursing. graph/curve.py
itself is not modified.

Witnesses: a closed-form point carries the placeholder ('exact', key, c, q).
`expand()` replaces each placeholder in a root witness by the native witness
of that state, obtained from the plain solver on the state's sub-graph and
matched by (capacity, traffic). A failed match raises, which would refute
the closed form. Expanded witnesses contain only grammar notes.
"""
import ast
from functools import lru_cache
from pathlib import Path
import time

from research.index_coupling.graph.curve import curve, pareto
from research.index_coupling.graph.model import Graph
from research.index_coupling.response.chains import recognise
from research.index_coupling.response.forms import predict

OPTIONS = dict(partitions='dp', scalar_leaf='v2')
CURVE_SOURCE = Path(__file__).resolve().parent.parent / 'graph/curve.py'


@lru_cache(maxsize=None)
def frontier_of(kinds, sizes, first, last, streamed, tile_domain):
    """Closed-form frontier, scanned upward to the first zero-traffic point."""
    top = sum(sizes) * 2 + len(kinds) + 4
    points = []
    for c in range(top + 1):
        q = predict(kinds, sizes, c, tile_domain, first, last, streamed)
        if q != float('inf'):
            points.append((c, q))
            if q == 0:
                return pareto(points)
    raise AssertionError(f'no zero-traffic point below {top} for {kinds} {sizes}')


def make_exact_kernel(registry=None, transform=None):
    """(curve variant, registry of substituted states)."""
    registry = {} if registry is None else registry
    tree = ast.parse(CURVE_SOURCE.read_text(), filename=str(CURVE_SOURCE))
    outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'curve')
    solver = next(n for n in ast.walk(outer) if isinstance(n, ast.FunctionDef) and n.name == '_solve')

    def exact(graph, ops, ext, external, owned, names, witness, max_capacity, stats, tile_domain):
        start = time.perf_counter()
        chain = recognise(graph, ops, ext, external, owned, names, unit_rows=True)
        if chain is not None and 'c' not in chain.kinds:
            chain = None  # elementwise-only spans are trivial for the search
        points = None if chain is None else frontier_of(chain.kinds, chain.sizes, chain.first, chain.last,
                                                        chain.streamed, tile_domain)
        if stats is not None:
            stats['exact_checks'] = stats.get('exact_checks', 0) + 1
            stats['exact_hits'] = stats.get('exact_hits', 0) + (chain is not None)
            stats['exact_seconds'] = stats.get('exact_seconds', 0.) + time.perf_counter() - start
        if chain is None:
            return None
        key = len(registry)
        registry[key] = (ops, tuple(names), ext, external, owned, tile_domain)
        return tuple((c, q, (('exact', key, c, q),) if witness else ()) for c, q in points if c <= max_capacity)

    outer.body[1:1] = ast.parse('''
_exact_enabled = (grid is None and spill_cost == 2 and write_through and split_shared
    and not legacy_nested_writes and not canonical_spans and not canonical_remainders
    and not independent_ops and ownership_projection and scalar_leaf == 'v2' and partitions == 'dp')
''').body
    leaf = ast.dump(ast.parse('not constrained and all(size(t, ext) == 1 for t in live)', mode='eval').body)
    positions = [i for i, n in enumerate(solver.body) if isinstance(n, ast.If) and ast.dump(n.test) == leaf]
    if len(positions) != 1:
        raise ValueError('source scalar-leaf rule changed')
    hook = ast.parse('''
if _exact_enabled and not constrained and (allowed_mask is None or ops != graph.ops):
    _pts = _exact(graph, ops, ext, external, owned, names, witness, max_capacity, stats, tile_domain)
    if _pts is not None:
        return _pts
''').body
    solver.body[positions[0] + 1:positions[0] + 1] = hook
    if transform is not None:
        transform(tree)  # optional audit restriction; no default behaviour change
    namespace = dict(__name__='research.index_coupling.graph._exact_experiment',
                     __package__='research.index_coupling.graph', _exact=exact)
    exec(compile(ast.fix_missing_locations(tree), str(CURVE_SOURCE), 'exec'), namespace)
    return namespace['curve'], registry


def native(graph, state, c, q, cache):
    """Native flattened witness of a registered state at point (c, q)."""
    ops, names, ext, external, owned, tile_domain = state
    key = (ops, ext, external, owned, tile_domain)
    if key not in cache:
        sizes = dict(zip(names, ext))
        used = {v for op in ops for d in graph.access[op].values() for v in d}
        sub = Graph({v: sizes[v] for v in used}, [(op, graph.access[op]) for op in ops])
        made = {sub.output(op) for op in ops}
        compulsory = sum(sub.size(t, ()) for t in (sub.consumed() - made) | (made - sub.consumed())
                         if t not in external)
        points = curve(sub, witness=True, external=external, written=owned, tile_domain=tile_domain, **OPTIONS)
        cache[key] = [(pc, pq - compulsory, w) for pc, pq, w in points]
    match = [w for pc, pq, w in cache[key] if pc <= c and pq == q]
    if not match:
        raise AssertionError(f'closed form point {(c, q)} not attained by {ops} at {ext}')
    return match[0]


def expand(graph, witness, registry, cache):
    """Flattened root witness with every placeholder replaced by native notes."""
    out = []
    for note in witness:
        if note[0] == 'exact':
            _, key, c, q = note
            out.extend(native(graph, registry[key], c, q, cache))
        else:
            out.append(note)
    return tuple(out)
