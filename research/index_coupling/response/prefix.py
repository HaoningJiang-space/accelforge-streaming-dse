"""Opt-in conditional prefix sharing; WORK_ATTRIBUTION.md section 5.

The adapter changes the partition recurrence, not the loop grammar. Prefix
frontiers carry native witness references and never trigger recovery search.
The template functions below are installed inside curve() by AST transformation
so that their resource operations are the original solver's lexical bindings.
"""
import ast
import inspect
from heapq import merge as _merge_ordered
from pathlib import Path

from .substitution import make_exact_kernel

SOURCE = Path(__file__).resolve().parent.parent / 'graph/curve.py'


def cut_dp(ops, ext, external, owned):
    frontier = prefix_query(ops, len(ops), ext, external, owned, ())
    results = []
    for c, q, w in frontier:
        if witness:
            groups, decisions, inner = w
            note = ('groups', groups, 'kept', tuple(sorted(t for t, k in decisions if k)),
                    'via DRAM', tuple(sorted(t for t, k in decisions if not k)))
            w = join((note,), inner)
        results.append((c, q, w))
    return tuple(results)


def prefix_query(ops, q, ext, external, owned, bits_q):
    if q == 0:
        return ((0, 0, ((), frozenset(), ()) if witness else ()),)
    if _share_prefix:
        _, ext, external, owned = projected(ops[:q], ext, external, owned)
    if _share_frames and q < len(ops):
        # A complete parent is already uniquely identified by its prefix;
        # only proper prefixes can alias across different parent spans.
        ops, q = prefix_parent(ops, q)
    return prefix_cached(ops, q, ext, external, owned, bits_q)


def prefix_parent(ops, q):
    # Same prefix and exit incidence reconstruct every earlier cut. The
    # later-writer flag preserves even non-topological single-writer inputs;
    # whole-parent preserves the v2 scalar-hold entry distinction.
    _, writer, crossing, _, _ = cut_metadata(ops)
    prefix = ops[:q]
    later = frozenset(t for t in project(prefix)[0]
                      if writer[t] is not None and writer[t] >= q)
    frame = (prefix, crossing[q], later, q == len(ops))
    return _prefix_frames.setdefault(frame, (ops, q))


def prefix_cached(ops, q, ext, external, owned, bits_q):
    width, transitions = prefix_transitions(ops, q, external & shared_tensors(ops), bits_q)
    if stats is not None:
        stats['dp_states'] += 1
        stats['max_crossing'] = max(stats['max_crossing'], width)
    results = []
    for p, group, bits_p, kept, written_here, always, maybe_write, decisions in transitions:
        prefix = prefix_query(ops, p, ext, external, owned, bits_p)
        if not prefix:
            continue
        if stats is not None:
            stats['dp_transitions'] += 1
        across = sum(size(t, ext) for t in kept)
        extra = sum(size(t, ext) for t in always) + sum(size(t, ext) for t in maybe_write - owned)
        inner = prune(((across + c, t, w) for c, t, w in
                       part_curve(group, ops, ext, external | kept, owned | written_here)), max_capacity)
        results.extend((c, t + extra, w if not witness else
                        (w[0] + (group,), w[1] | decisions, join(w[2], wg)))
                       for c, t, w, wg in sweep(prefix, inner, max_capacity))
    return prune(results, max_capacity)


def ordered_union(streams, max_capacity=float('inf')):
    """Stable numeric union; stream order breaks equal-(C,Q) ties.

    Every input stream is sorted by (C,Q). heapq.merge retains input-stream
    order for equal keys, matching stable sort of their concatenation.
    Provenance is never compared or reconstructed here.
    """
    out, best = [], float('inf')
    for point in _merge_ordered(*streams, key=lambda p: (p[0], p[1])):
        if point[0] > max_capacity:
            break
        if point[1] < best:
            out.append(point)
            best = point[1]
    return tuple(out)


def prefix_numeric(ops, q, ext, external, owned, bits_q):
    # Installed as prefix_cached. The adapter replaces mode/profile names by
    # constants, so instrumentation branches disappear from timed workers.
    width, transitions = prefix_transitions(ops, q, external & shared_tensors(ops), bits_q)
    if stats is not None:
        stats['dp_states'] += 1
        stats['max_crossing'] = max(stats['max_crossing'], width)
    results = []
    for p, group, bits_p, kept, written_here, always, maybe_write, decisions in transitions:
        prefix = prefix_query(ops, p, ext, external, owned, bits_p)
        if not prefix:
            continue
        if stats is not None:
            stats['dp_transitions'] += 1
        across = sum(size(t, ext) for t in kept)
        extra = sum(size(t, ext) for t in always) + sum(size(t, ext) for t in maybe_write - owned)
        inner = prune(((across + c, t, w) for c, t, w in
                       part_curve(group, ops, ext, external | kept, owned | written_here)), max_capacity)
        candidates = ((c, t + extra, (w, wg, group, decisions))
                      for c, t, w, wg in sweep(prefix, inner, max_capacity))
        if _ordered_prefix:
            # Consume while loop locals still refer to this transition.
            results.append(tuple(candidates))
        else:
            results.extend(candidates)
    if _profile_prefix or (_ordered_prefix and stats is not None):
        count = sum(map(len, results)) if _ordered_prefix else len(results)
        begin = perf_counter()
    if _ordered_prefix:
        selected = ordered_union(results, max_capacity)
    else:
        selected = prune(results, max_capacity)
    if _profile_prefix or (_ordered_prefix and stats is not None):
        elapsed = perf_counter() - begin
    if _ordered_prefix and stats is not None:
        # Same logical Pareto-union accounting although B uses no sort.
        stats['pareto_calls'] += 1
        stats['pareto_candidates'] += count
        stats['pareto_points'] += len(selected)
        stats['max_frontier'] = max(stats['max_frontier'], len(selected))
        stats['pareto_seconds'] += elapsed
    if _profile_prefix:
        _prefix_work['prefix_union_seconds'] += elapsed
        _prefix_work['prefix_candidates'] += count
        _prefix_work['prefix_survivors'] += len(selected)
        begin = perf_counter()
    out = tuple((c, t, w if not witness else
                 (w[0] + (group,), w[1] | decisions, join(w[2], wg)))
                for c, t, (w, wg, group, decisions) in selected)
    if _profile_prefix:
        _prefix_work['prefix_witness_seconds'] += perf_counter() - begin
        _prefix_work['prefix_witness_constructions'] += len(out) if witness else 0
    return out


def instrument_eager(node):
    """Instrument the control only in separate work workers; timed AST unchanged."""
    loop = next(n for n in node.body if isinstance(n, ast.For))
    append = loop.body[-1]
    assert isinstance(append, ast.Expr) and isinstance(append.value, ast.Call)
    assert isinstance(append.value.func, ast.Attribute) and append.value.func.attr == 'extend'
    # The instrumented sweep is materialized by the core, but calling it in
    # extend's generator would charge its time to witness construction. Hoist
    # it before the timer; neither operation includes recursive child search.
    gen = append.value.args[0]
    sweep_call = gen.generators[0].iter
    gen.generators[0].iter = ast.Name(id='_swept', ctx=ast.Load())
    loop.body[-1:] = ([ast.Assign(targets=[ast.Name(id='_swept', ctx=ast.Store())], value=sweep_call)]
                     + ast.parse('_before = len(results)\n_begin = perf_counter()').body
                     + [append] + ast.parse('''
_prefix_work['prefix_witness_seconds'] += perf_counter() - _begin
_prefix_work['prefix_witness_constructions'] += len(results) - _before if witness else 0
''').body)
    node.body[-1:] = ast.parse('''
_begin = perf_counter()
out = prune(results, max_capacity)
_prefix_work['prefix_union_seconds'] += perf_counter() - _begin
_prefix_work['prefix_candidates'] += len(results)
_prefix_work['prefix_survivors'] += len(out)
return out
''').body


def prefix_transitions(ops, q, external, bits_q):
    # Incidence/decision skeleton: independent of extents, private-weight
    # residency, and ownership. These still enter every numeric child query.
    first, writer, all_crossing, touched, readers = cut_metadata(ops)
    crossing = [tuple(t for t in ts if t not in external) for ts in all_crossing[:q+1]]
    decided_q = dict(zip(crossing[q], bits_q))
    transitions = []
    for p in range(q):
        group = ops[p:q]
        free = tuple(t for t in crossing[p] if t not in decided_q)
        new = tuple(t for t in crossing[q] if t not in crossing[p])
        for free_bits in product((True, False), repeat=len(free)):
            choice = dict(decided_q, **dict(zip(free, free_bits)))
            bits_p = tuple(choice[t] for t in crossing[p])
            if not split_shared and any(not choice[t] and t in produced and n_consumers[t] > 1
                                        for t in new):
                continue
            dropped = {t for t, k in choice.items() if not k and t in touched[p, q]}
            if not write_through and any(writer[t] is not None and p <= writer[t] < q
                                         and t in readers[p, q] for t in dropped):
                continue
            kept = frozenset(t for t, k in choice.items() if k)
            always, maybe_write = set(), set()
            for t in dropped:
                if writer[t] is not None and t in consumed:
                    (maybe_write if p <= writer[t] < q else always).add(t)
                elif writer[t] is None and first[t] < p:
                    always.add(t)
            written_here = frozenset(t for t, k in choice.items()
                                     if not k and writer[t] is not None and t in consumed)
            decisions = frozenset(choice.items())
            transitions.append((p, group, bits_p, kept, written_here,
                                frozenset(always), frozenset(maybe_write), decisions))
    return max(map(len, crossing)), tuple(transitions)


def transform(tree, projection=True, frames=False, composition='eager', profile_prefix=False,
              reductions=False):
    if composition not in ('eager', 'numeric', 'ordered'):
        raise ValueError('unknown prefix composition')
    if frames and not projection:
        raise ValueError('parent-frame quotient requires prefix projection')
    outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'curve')
    positions = [i for i, n in enumerate(outer.body) if isinstance(n, ast.FunctionDef) and n.name == 'cut_dp']
    if len(positions) != 1:
        raise ValueError('native cut_dp source anchor changed')
    definitions = []
    functions = (cut_dp, prefix_query, prefix_parent,
                     prefix_cached if composition == 'eager' else prefix_numeric,
                     prefix_transitions)
    if composition == 'ordered':
        functions += (ordered_union,)
    for function in functions:
        node = ast.parse(inspect.getsource(function)).body[0]
        if function is prefix_numeric:
            node.name = 'prefix_cached'
        if function is prefix_cached and profile_prefix:
            instrument_eager(node)
        if reductions and function in (prefix_cached, prefix_numeric):
            # Test the actual child contract before recursively constructing its
            # prefix. Extents and private residency MUST NOT enter the structural
            # transition cache. Native part_curve's scalar Hold is nonempty, so
            # the same predicate is safe for the whole-parent special case.
            loop = next(n for n in node.body if isinstance(n, ast.For))
            loop.body[:0] = ast.parse('''
if empty_groups is not None and infeasible(group, ext, external | kept):
    if stats is not None:
        stats['prefix_infeasible_skips'] = stats.get('prefix_infeasible_skips', 0) + 1
    continue
''').body
        if function in (prefix_parent, prefix_cached, prefix_numeric, prefix_transitions):
            node.decorator_list = ast.parse('@lru_cache(maxsize=None)\ndef f(): pass').body[0].decorator_list
        class Constants(ast.NodeTransformer):
            def visit_Name(self, n):
                values = dict(_ordered_prefix=composition == 'ordered', _profile_prefix=profile_prefix)
                return ast.copy_location(ast.Constant(values[n.id]), n) if n.id in values else n
        node = Constants().visit(node)
        definitions.append(node)
    i = positions[0]
    outer.body[i:i+1] = definitions
    outer.body[1:1] = ast.parse(f'''
_share_prefix = {bool(projection)!r}
_share_frames = {bool(frames)!r}
_prefix_frames = {{}}
from heapq import merge as _merge_ordered
_prefix_work = dict(prefix_candidates=0, prefix_survivors=0,
                   prefix_witness_constructions=0, prefix_witness_seconds=0.,
                   prefix_union_seconds=0.) if {bool(profile_prefix)!r} else None
if (partitions != 'dp' or scalar_leaf != 'v2' or grid is not None
    or root_groups is not None or root_kept is not None or whole_span_cuts is not None
    or legacy_nested_writes or canonical_spans
    or (not {bool(reductions)!r} and (canonical_remainders or independent_ops or prune_infeasible_groups))
    or not ownership_projection
    or len(graph.produced()) != len(graph.ops)):
    raise ValueError('prefix adapter requires exact unconstrained v2 single-writer cut DP; reductions need opt-in')
''').body
    final = next(n for n in reversed(outer.body) if isinstance(n, ast.Try) and n.finalbody)
    final.finalbody.extend(ast.parse('''
if stats is not None:
    stats['prefix_cache'] = prefix_cached.cache_info()._asdict()
    stats['prefix_transition_cache'] = prefix_transitions.cache_info()._asdict()
    stats['prefix_projection'] = _share_prefix
    stats['prefix_parent_cache'] = prefix_parent.cache_info()._asdict()
    stats['prefix_frame_classes'] = len(_prefix_frames)
    stats['prefix_frame_aliases'] = prefix_parent.cache_info().misses - len(_prefix_frames)
    stats['prefix_frames_enabled'] = _share_frames
    if _prefix_work is not None:
        stats.update(_prefix_work)
''').body)


def make_kernel(projection=True, unit=False, frames=False, composition='eager', profile_prefix=False,
                reductions=False):
    """Return (curve variant, unit-form registry); installation is separately timed."""
    if unit:
        return make_exact_kernel(reductions=reductions, transform=lambda tree: transform(
            tree, projection, frames, composition, profile_prefix, reductions))
    tree = ast.parse(SOURCE.read_text(), filename=str(SOURCE))
    transform(tree, projection, frames, composition, profile_prefix, reductions)
    namespace = dict(__name__='research.index_coupling.graph._prefix_experiment',
                     __package__='research.index_coupling.graph')
    exec(compile(ast.fix_missing_locations(tree), str(SOURCE), 'exec'), namespace)
    return namespace['curve'], {}
