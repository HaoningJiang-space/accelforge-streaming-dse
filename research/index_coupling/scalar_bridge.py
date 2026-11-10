"""Opt-in, in-memory fork shortcut; production/frozen solver files are untouched.

When X is scalar but not external, retaining it across singleton operators
attains zero internal extra traffic at the operand-count capacity lower bound.
Keep the original whole-span scalar leaf and all root-cut constraints intact.
"""
import ast
from math import prod
from pathlib import Path

from research.index_coupling.graph.model import fork


def standard_fork(graph):
    """Conservative prototype gate, including literal access/output order."""
    if set(graph.sizes) != {'I', 'J', 'K', 'L'} or len(graph.ops) < 2:
        return False
    roles = []
    for op in graph.ops[1:]:
        dims = graph.dims(graph.output(op))
        if dims == ('I', 'L'):
            roles.append('k')
        elif dims == ('L', 'K'):
            roles.append('i')
        else:
            return False
    expected = fork(*(graph.sizes[v] for v in ('I', 'J', 'K', 'L')), ''.join(roles))
    return graph.ops == expected.ops and all(
        tuple(graph.access[op].items()) == tuple(expected.access[op].items()) for op in graph.ops)


def bridge_response(graph, ops, ext, external, owned, names, witness=False, max_capacity=float('inf')):
    """Internal triple frontier or None if the theorem's preconditions fail.

The caller must establish a standard fork, unconstrained solve entry, exact
pruning, default cost rules, and no whole-span cut restriction on this span.
"""
    sizes = dict(zip(names, ext))
    if len(ops) < 2 or sizes['I'] != 1 or sizes['K'] != 1 or 'X' in external or set(owned) - {'X'}:
        return None
    live = graph.tensors(ops) - set(external)
    if all(prod(sizes[v] for v in graph.dims(t)) == 1 for t in live):
        return None  # The original all-scalar leaf takes precedence over partitioning.
    capacity = max(len(set(graph.access[op]) - set(external)) for op in ops)
    if capacity > max_capacity:
        return ()
    notes = []
    if witness:
        notes.append(('groups', tuple((op,) for op in ops), 'kept', ('X',), 'via DRAM', ()))
        for op in ops:
            private = set(graph.access[op]) - set(external) - {'X'}
            axis = 'J' if op == 'EX' else 'L'
            if private and sizes[axis] > 1:
                notes.append(('loop', (op,), axis, f'tile 1 x{sizes[axis]}',
                              'kept', (), 'refetched', ()))
    return ((capacity, 0, tuple(notes)),)


def make_scalar_bridge_curve():
    """Use the source recurrence with a guarded solve-entry theorem inserted."""
    path = Path(__file__).parent / 'graph/curve.py'
    tree = ast.parse(path.read_text(), filename=str(path))
    outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'curve')
    outer.body[1:1] = ast.parse('''
_scalar_bridge_enabled = (_standard_fork(graph) and grid is None and spill_cost == 2
    and write_through and split_shared and not legacy_nested_writes
    and not canonical_spans and not independent_ops)
''').body
    solver = next(n for n in ast.walk(outer) if isinstance(n, ast.FunctionDef) and n.name == '_solve')
    leaf_test = ast.dump(ast.parse('not constrained and all(size(t, ext) == 1 for t in live)', mode='eval').body)
    leaves = [i for i, n in enumerate(solver.body) if isinstance(n, ast.If) and ast.dump(n.test) == leaf_test]
    if len(leaves) != 1:
        raise ValueError('expected the original solve scalar-leaf rule')
    hook = ast.parse('''
if _scalar_bridge_enabled and not constrained and (allowed_mask is None or ops != graph.ops):
    _scalar_bridge_result = _bridge_response(graph, ops, ext, external, owned, names,
                                             witness=witness, max_capacity=max_capacity)
    if _scalar_bridge_result is not None:
        if stats is not None:
            stats['scalar_bridge_hits'] = stats.get('scalar_bridge_hits', 0) + 1
        return _scalar_bridge_result
''').body
    solver.body[leaves[0] + 1:leaves[0] + 1] = hook
    namespace = dict(__name__='research.index_coupling.graph._scalar_bridge_experiment',
                     __package__='research.index_coupling.graph',
                     _standard_fork=standard_fork, _bridge_response=bridge_response)
    exec(compile(ast.fix_missing_locations(tree), str(path), 'exec'), namespace)
    return namespace['curve']
