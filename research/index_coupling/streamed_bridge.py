"""Opt-in fixed-order fork theorem for non-scalar X with resident obligations.

Stream active I/K axes at unit tiles when every tensor lacking those axes is
already external. This adds no local reservation or extra traffic. The reduced
problem must attain the per-operator operand-count bound: either scalar_bridge
applies, or the original scalar leaf itself has exactly that capacity.
"""
import ast
from math import prod
from pathlib import Path

from research.index_coupling.scalar_bridge import bridge_response, standard_fork


def streamed_response(graph, ops, ext, external, owned, names, witness=False,
                      max_capacity=float('inf')):
    """Return an internal triple frontier, or None outside the sufficient rule.

The caller establishes standard_fork, unconstrained solve entry, unrestricted
cuts, exact pruning, and the default cost rules. This function handles only
non-scalar X; the existing scalar bridge handles the scalar case separately.
Caller-paid external reservations and compulsory traffic are excluded.
"""
    sizes = dict(zip(names, ext))
    active = tuple(v for v in ('I', 'K') if sizes[v] > 1)
    external = set(external)
    if not active or len(ops) < 2 or 'X' in external or set(owned) - {'X'}:
        return None
    live = graph.tensors(ops) - external
    if any(v not in graph.dims(t) for v in active for t in live):
        return None
    reduced = dict(sizes, I=1, K=1)
    capacity = max(len(set(graph.access[op]) - external) for op in ops)
    if all(prod(reduced[v] for v in graph.dims(t)) == 1 for t in live):
        # The scalar leaf is mandatory before partition search. Merely removing
        # all loop obligations does NOT establish the smaller operand bound.
        if len(live) != capacity:
            return None
        child = ((capacity, 0, ()),)
    else:
        child = bridge_response(graph, ops, tuple(reduced[v] for v in names),
                                external, owned, names, witness=witness)
        if child is None:
            raise AssertionError('reduced state must meet scalar bridge preconditions')
    if capacity > max_capacity:
        return ()
    notes = []
    if witness:
        for axis in active:
            # Each loop re-enters solve, whose one-group partition enters the
            # next loop. Explicit group notes are required by the replay parser.
            notes.append(('groups', (tuple(ops),), 'kept', (), 'via DRAM', ()))
            notes.append(('loop', tuple(ops), axis, f'tile 1 x{sizes[axis]}',
                          'kept', (), 'refetched', ()))
    return ((capacity, 0, tuple(notes) + child[0][2]),)


def make_streamed_bridge_curve():
    """Scalar bridge plus the non-scalar rule; do not mutate production code."""
    path = Path(__file__).parent / 'graph/curve.py'
    tree = ast.parse(path.read_text(), filename=str(path))
    outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'curve')
    outer.body[1:1] = ast.parse('''
_bridge_enabled = (_standard_fork(graph) and grid is None and spill_cost == 2
    and write_through and split_shared and not legacy_nested_writes
    and not canonical_spans and not independent_ops)
''').body
    solver = next(n for n in ast.walk(outer) if isinstance(n, ast.FunctionDef) and n.name == '_solve')
    leaf_test = ast.dump(ast.parse('not constrained and all(size(t, ext) == 1 for t in live)', mode='eval').body)
    leaves = [i for i, n in enumerate(solver.body) if isinstance(n, ast.If) and ast.dump(n.test) == leaf_test]
    if len(leaves) != 1:
        raise ValueError('expected the original solve scalar-leaf rule')
    hook = ast.parse('''
if _bridge_enabled and not constrained and (allowed_mask is None or ops != graph.ops):
    for _bridge_counter, _bridge_function in (
            ('scalar_bridge_hits', _scalar_response), ('streamed_bridge_hits', _streamed_response)):
        _bridge_result = _bridge_function(graph, ops, ext, external, owned, names,
                                         witness=witness, max_capacity=max_capacity)
        if _bridge_result is not None:
            if stats is not None:
                stats[_bridge_counter] = stats.get(_bridge_counter, 0) + 1
            return _bridge_result
''').body
    solver.body[leaves[0] + 1:leaves[0] + 1] = hook
    namespace = dict(__name__='research.index_coupling.graph._streamed_bridge_experiment',
                     __package__='research.index_coupling.graph',
                     _standard_fork=standard_fork, _scalar_response=bridge_response,
                     _streamed_response=streamed_response)
    exec(compile(ast.fix_missing_locations(tree), str(path), 'exec'), namespace)
    return namespace['curve']
