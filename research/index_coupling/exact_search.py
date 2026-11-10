"""Opt-in exact-response substitution for unit-M chain states (CONTRACTION_ORACLE.md §16).

`make_exact_kernel()` returns a curve() variant, adapted in memory as in
unified_search.make_kernel: right after the scalar-leaf rule of _solve, a
state recognised as a unit-M chain (structurally, not by operator names)
returns its closed-form response (elementwise_chain.predict) instead of
recursing. graph/curve.py itself is not modified.

Witnesses: a closed-form point carries the placeholder ('exact', key, c, q).
`expand()` replaces each placeholder in a root witness by the native witness
of that state, obtained from the plain solver on the state's sub-graph and
matched by (capacity, traffic). The expanded witness contains only grammar
notes and replays in the cell-level executor. A failed match raises, which
would refute the closed form.

Usage: python -m research.index_coupling.exact_search check CASE [CASE ...]
       python -m research.index_coupling.exact_search bench OUT.jsonl REPEATS CASE [CASE ...]
       python -m research.index_coupling.exact_search once MODE CASE   (one fresh-process measurement)
"""
import ast
from functools import lru_cache
import json
from pathlib import Path
import sys
import time

from research.index_coupling.elementwise_chain import predict
from research.index_coupling.graph.curve import curve, pareto
from research.index_coupling.graph.model import Graph

OPTIONS = dict(partitions='dp', scalar_leaf='v2')


@lru_cache(maxsize=None)
def _dims(graph, tensor):
    return frozenset(graph.dims(tensor))


@lru_cache(maxsize=None)
def _produced(graph):
    return frozenset(graph.produced())


@lru_cache(maxsize=None)
def _consumers(graph, tensor):
    return tuple(graph.consumers(tensor))


def chain_of(graph, ops, ext, external, owned, names):
    """(kinds, sizes, resident ends, streamed flags) of a unit-M chain state, else None."""
    ext = dict(zip(names, ext))
    dims = lambda t: _dims(graph, t)
    # Row ranks: shared by every produced tensor of the graph (M for FFN and
    # attention). An activation carries them, a weight carries none.
    rows = frozenset.intersection(*(dims(t) for t in _produced(graph)))
    if not rows:
        return None
    vectors, kinds, weights = [], [], []
    for i, op in enumerate(ops):
        out = graph.output(op)
        ins = [t for t in graph.access[op] if t != out]
        acts = [t for t in ins if rows <= dims(t)]
        rest = [t for t in ins if not dims(t) & rows]
        if len(acts) != 1 or len(acts) + len(rest) != len(ins) or len(rest) > 1:
            return None
        x = acts[0]
        if i and x != graph.output(ops[i - 1]):
            return None
        w = rest[0] if rest else None
        if w is None and dims(x) != dims(out):
            return None
        if i == 0:
            vectors.append(x)
        vectors.append(out)
        kinds.append('e' if w is None else 'c')
        weights.append(w)
    if 'c' not in kinds:
        return None
    if any(not rows <= dims(v) for v in vectors) or any(ext[r] != 1 for r in rows):
        return None
    own = []
    for v in vectors:
        rest = dims(v) - rows
        if len(rest) != 1:
            return None
        own.append(next(iter(rest)))
    # Elementwise keeps the rank, a contraction changes it, and no rank recurs.
    segments = [own[0]]
    for k, r_in, r_out in zip(kinds, own, own[1:]):
        if (k == 'e') != (r_in == r_out):
            return None
        if k == 'c':
            segments.append(r_out)
    if len(set(segments)) != len(segments):
        return None
    for op, w, r_in, r_out in zip(ops, weights, own, own[1:]):
        if w is not None and (dims(w) != {r_in, r_out} or _consumers(graph, w) != (op,)
                              or w in _produced(graph)):
            return None
    for j, v in enumerate(vectors[1:-1], 1):
        if v in external or v in owned or _consumers(graph, v) != (ops[j],):
            return None
    sizes = [ext[r] for r in own]
    streamed = [int(w is not None and w not in external) for w in weights]
    return kinds, sizes, vectors[0] in external, vectors[-1] in external, streamed


def response(chain, tile_domain):
    kinds, sizes, first, last, streamed = chain
    return _response(tuple(kinds), tuple(sizes), first, last, tuple(streamed), tile_domain)


@lru_cache(maxsize=None)
def _response(kinds, sizes, first, last, streamed, tile_domain):
    """Closed-form frontier; states that differ only in names share it.

    Scans capacity upward to the first zero-traffic point; the plateau is
    usually close to zero, so this is cheaper than bisecting a wide range.
    """
    top = sum(sizes) * 2 + len(kinds) + 4
    points = []
    for c in range(top + 1):
        q = predict(kinds, sizes, c, tile_domain, first, last, streamed)
        if q != float('inf'):
            points.append((c, q))
            if q == 0:
                return pareto(points)
    raise AssertionError(f'no zero-traffic point below {top} for {kinds} {sizes}')


def make_exact_kernel(registry=None):
    registry = {} if registry is None else registry
    path = Path(__file__).parent / 'graph/curve.py'
    tree = ast.parse(path.read_text(), filename=str(path))
    outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'curve')
    solver = next(n for n in ast.walk(outer) if isinstance(n, ast.FunctionDef) and n.name == '_solve')

    def exact(graph, ops, ext, external, owned, names, witness, max_capacity, stats, tile_domain):
        start = time.perf_counter()
        chain = chain_of(graph, ops, ext, external, owned, names)
        points = None if chain is None else response(chain, tile_domain)
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
    namespace = dict(__name__='research.index_coupling.graph._exact_experiment',
                     __package__='research.index_coupling.graph', _exact=exact)
    exec(compile(ast.fix_missing_locations(tree), str(path), 'exec'), namespace)
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


def run(case, replay=True):
    from research.index_coupling.census_tools import graph_of
    from research.index_coupling.graph.analysis import traffic_at
    from research.index_coupling.simulate_nest import simulate
    graph = graph_of(case)
    record = dict(case=case)
    start = time.perf_counter()
    base = curve(graph, **OPTIONS)
    record['baseline_seconds'] = time.perf_counter() - start
    kernel, registry = make_exact_kernel()
    stats = {}
    start = time.perf_counter()
    fast = kernel(graph, stats=stats, **OPTIONS)
    record['exact_seconds'] = time.perf_counter() - start
    record['same_curve'] = [p[:2] for p in base] == [p[:2] for p in fast]
    record.update({k: stats.get(k) for k in ('exact_checks', 'exact_hits', 'dp_transitions', 'loop_choices',
                                             'pareto_candidates', 'merge_inputs')})
    record['closed_form_seconds'] = stats.get('exact_seconds')
    if replay:
        kernel, registry = make_exact_kernel()
        points = kernel(graph, witness=True, **OPTIONS)
        cache, ok = {}, 0
        start = time.perf_counter()
        for c, q, w in points:
            run_ = simulate(graph, expand(graph, w, registry, cache), scalar_leaf='v2')
            ok += run_['valid'] and (run_['peak'], run_['traffic']) == (c, q)
        record.update(replay_exact=ok, replay_total=len(points), expand_seconds=time.perf_counter() - start,
                      expanded_states=len(cache))
    print(json.dumps(record), flush=True)
    return record


def once(mode, case):
    """One measurement in this (fresh) process: wall time, peak RSS, work ledger."""
    import platform
    import resource
    from research.index_coupling.census_tools import graph_of
    graph = graph_of(case)
    solver = curve if mode == 'baseline' else make_exact_kernel()[0]
    stats = {}
    start = time.perf_counter()
    points = solver(graph, stats=stats, **OPTIONS)
    seconds = time.perf_counter() - start
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_mib = rss / 2**20 if platform.system() == 'Darwin' else rss / 2**10
    keys = ('dp_transitions', 'loop_choices', 'pareto_candidates', 'merge_inputs', 'exact_checks', 'exact_hits',
            'exact_seconds')
    print(json.dumps(dict(mode=mode, case=case, seconds=seconds, peak_rss_mib=rss_mib,
                          curve=[p[:2] for p in points], misses=stats['solve_cache']['misses'] +
                          stats['group_cache']['misses'], **{k: stats.get(k) for k in keys})))


def bench(out, repeats, cases):
    import subprocess
    with open(out, 'a') as stream:
        for case in cases:
            for r in range(repeats):
                for mode in ('baseline', 'exact'):
                    line = subprocess.check_output([sys.executable, '-m', 'research.index_coupling.exact_search',
                                                    'once', mode, case], text=True).strip().splitlines()[-1]
                    record = dict(json.loads(line), repeat=r)
                    stream.write(json.dumps(record) + '\n')
                    stream.flush()
                    print(json.dumps({k: record[k] for k in ('case', 'mode', 'repeat', 'seconds', 'peak_rss_mib')}),
                          flush=True)


if __name__ == '__main__':
    command, args = sys.argv[1], sys.argv[2:]
    if command == 'check':
        for case in args:
            run(case)
    elif command == 'once':
        once(*args)
    elif command == 'bench':
        bench(args[0], int(args[1]), args[2:])
