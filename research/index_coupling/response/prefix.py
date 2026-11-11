"""Opt-in conditional prefix sharing; WORK_ATTRIBUTION.md section 5.

The adapter changes the partition recurrence, not the loop grammar. Prefix
frontiers carry native witness references and never trigger recovery search.
The template functions below are installed inside curve() by AST transformation
so that their resource operations are the original solver's lexical bindings.
"""
import ast
import inspect
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
    return prefix_cached(ops, q, ext, external, owned, bits_q)


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


def transform(tree, projection=True):
    outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'curve')
    positions = [i for i, n in enumerate(outer.body) if isinstance(n, ast.FunctionDef) and n.name == 'cut_dp']
    if len(positions) != 1:
        raise ValueError('native cut_dp source anchor changed')
    definitions = []
    for function in (cut_dp, prefix_query, prefix_cached, prefix_transitions):
        node = ast.parse(inspect.getsource(function)).body[0]
        if function in (prefix_cached, prefix_transitions):
            node.decorator_list = ast.parse('@lru_cache(maxsize=None)\ndef f(): pass').body[0].decorator_list
        definitions.append(node)
    i = positions[0]
    outer.body[i:i+1] = definitions
    outer.body[1:1] = ast.parse(f'''
_share_prefix = {bool(projection)!r}
if (partitions != 'dp' or scalar_leaf != 'v2' or grid is not None
    or root_groups is not None or root_kept is not None or whole_span_cuts is not None
    or legacy_nested_writes or canonical_spans or canonical_remainders
    or independent_ops or prune_infeasible_groups or not ownership_projection
    or len(graph.produced()) != len(graph.ops)):
    raise ValueError('prefix adapter requires exact unconstrained v2 single-writer cut DP without other reductions')
''').body
    final = next(n for n in reversed(outer.body) if isinstance(n, ast.Try) and n.finalbody)
    final.finalbody.extend(ast.parse('''
if stats is not None:
    stats['prefix_cache'] = prefix_cached.cache_info()._asdict()
    stats['prefix_transition_cache'] = prefix_transitions.cache_info()._asdict()
    stats['prefix_projection'] = _share_prefix
''').body)


def make_kernel(projection=True, unit=False):
    """Return (curve variant, unit-form registry); installation is separately timed."""
    if unit:
        return make_exact_kernel(transform=lambda tree: transform(tree, projection))
    tree = ast.parse(SOURCE.read_text(), filename=str(SOURCE))
    transform(tree, projection)
    namespace = dict(__name__='research.index_coupling.graph._prefix_experiment',
                     __package__='research.index_coupling.graph')
    exec(compile(ast.fix_missing_locations(tree), str(SOURCE), 'exec'), namespace)
    return namespace['curve'], {}
