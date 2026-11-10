"""Opt-in scalar-obligation certificate: reservation can attain the slot bound.

If a legal unit loop can retain its sole missing-axis scalar t, all bottleneck
operators access t, and a certified child attains (d-1,0), the parent attains
the global lower bounds (d,0). This does not assert that obligation count alone
determines a response. Existing leaf and bridge rules retain precedence.
"""
import ast
from math import prod
from pathlib import Path

from research.index_coupling.scalar_bridge import bridge_response, standard_fork
from research.index_coupling.streamed_bridge import streamed_response


def retention_candidates(graph, ops, ext, external, owned, names, witness=False):
    """Diagnostic records for legal one-obligation axes at a non-leaf solve.

Caller establishes standard Fork, unrestricted multi-op solve, default exact
cost rules. Candidate counts are axis counts; callers must separately count
unique eligible states. Child proof sources never recurse into this rule.
"""
    if len(ops) < 2 or set(owned) - {'X'}:
        return
    sizes = dict(zip(names, ext))
    external = set(external)
    live = graph.tensors(ops) - external
    size = lambda t, e: prod(e[v] for v in graph.dims(t))
    if all(size(t, sizes) == 1 for t in live):
        return  # Preserve the original scalar leaf, including its capacity.
    demand = {o: len(set(graph.access[o]) - external) for o in ops}
    d = max(demand.values())
    common = set.intersection(*(graph.rank_vars((o,)) for o in ops))
    inside = {graph.output(o) for o in ops} & {
        t for o in ops for t in list(graph.access[o])[:-1]}
    for axis in sorted(common):
        if sizes[axis] <= 1 or any(axis not in graph.dims(t) for t in inside - external):
            continue
        lacking = sorted(t for t in live if axis not in graph.dims(t))
        if len(lacking) != 1:
            continue
        tensor = lacking[0]
        resident = external | {tensor}
        d1 = max(len(set(graph.access[o]) - resident) for o in ops)
        bottlenecks = tuple(o for o in ops if demand[o] == d)
        row = dict(axis=axis, tensor=tensor, size=size(tensor, sizes), d=d, child_bound=d1,
                   bottlenecks=bottlenecks, all_bottlenecks_access=all(tensor in graph.access[o] for o in bottlenecks),
                   eligible=False)
        if row['size'] != 1:
            yield dict(row, reason='nonscalar_obligation')
            continue
        if d1 != d-1:
            yield dict(row, reason='no_slot_drop')
            continue
        reduced = dict(sizes, **{axis: 1})
        inner_ext = tuple(reduced[v] for v in names)
        if all(size(t, reduced) == 1 for t in live - {tensor}):
            kind = 'original_scalar_leaf'
            child = ((len(live - {tensor}), 0, ()),)
        else:
            kind = 'scalar_bridge'
            child = bridge_response(graph, ops, inner_ext, resident, owned, names, witness=witness)
            if child is None:
                kind = 'streamed_bridge'
                child = streamed_response(graph, ops, inner_ext, resident, owned, names, witness=witness)
        if child is None:
            yield dict(row, reason='no_child_certificate')
        elif tuple(p[:2] for p in child) != ((d1, 0),):
            yield dict(row, reason='child_above_slot_bound', child_kind=kind,
                       child_points=tuple(p[:2] for p in child))
        else:
            yield dict(row, reason='certified', eligible=True, child_kind=kind, child=child)


def free_retention_response(graph, ops, ext, external, owned, names, witness=False,
                            max_capacity=float('inf')):
    for certificate in retention_candidates(graph, ops, ext, external, owned, names, witness):
        if not certificate['eligible']:
            continue
        d, axis, tensor = (certificate[k] for k in ('d','axis','tensor'))
        if d > max_capacity:
            return ()
        notes = ()
        if witness:
            trips = ext[names.index(axis)]
            notes = (('groups', (tuple(ops),), 'kept', (), 'via DRAM', ()),
                     ('loop', tuple(ops), axis, f'tile 1 x{trips}', 'kept', (tensor,), 'refetched', ()))
        return ((d, 0, notes + certificate['child'][0][2]),)
    return None


def make_free_retention_curve():
    """Existing bridges plus the new certificate, inserted only in memory."""
    path = Path(__file__).parent / 'graph/curve.py'
    tree = ast.parse(path.read_text(), filename=str(path))
    outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'curve')
    outer.body[1:1] = ast.parse('''
_certificate_enabled = (_standard_fork(graph) and grid is None and spill_cost == 2
    and write_through and split_shared and not legacy_nested_writes
    and not canonical_spans and not independent_ops)
''').body
    solver = next(n for n in ast.walk(outer) if isinstance(n, ast.FunctionDef) and n.name == '_solve')
    leaf_test = ast.dump(ast.parse('not constrained and all(size(t, ext) == 1 for t in live)', mode='eval').body)
    leaves = [i for i,n in enumerate(solver.body) if isinstance(n,ast.If) and ast.dump(n.test) == leaf_test]
    if len(leaves) != 1:
        raise ValueError('expected the original scalar-leaf rule')
    hook = ast.parse('''
if _certificate_enabled and not constrained and (allowed_mask is None or ops != graph.ops):
    for _counter, _response in (('scalar_bridge_hits', _scalar_response),
                               ('streamed_bridge_hits', _streamed_response),
                               ('free_retention_hits', _free_response)):
        _result = _response(graph, ops, ext, external, owned, names,
                            witness=witness, max_capacity=max_capacity)
        if _result is not None:
            if stats is not None:
                stats[_counter] = stats.get(_counter, 0) + 1
            return _result
''').body
    solver.body[leaves[0]+1:leaves[0]+1] = hook
    namespace = dict(__name__='research.index_coupling.graph._free_retention_experiment',
                     __package__='research.index_coupling.graph', _standard_fork=standard_fork,
                     _scalar_response=bridge_response, _streamed_response=streamed_response,
                     _free_response=free_retention_response)
    exec(compile(ast.fix_missing_locations(tree), str(path), 'exec'), namespace)
    return namespace['curve']
