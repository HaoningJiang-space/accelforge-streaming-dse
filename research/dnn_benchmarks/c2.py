"""Opt-in implementation of GRAMMAR_V2.md C2; no edits to the core solver.

The all-kept child's response is a lower bound, not a feasible plan for a
different mask. It is used only to reject a mask whose entire lower frontier
is dominated by actual incumbent plans. The small AST adapter fails closed
if its source anchors change. Construct one kernel per process (not threads).
"""
import ast
import importlib
import inspect
from functools import wraps


def lower_dominated(incumbent, lower, capacity, extra, trips):
    """Incumbent and lower are increasing-capacity Pareto frontiers."""
    j, best = 0, float('inf')
    for c, q, *_ in lower:
        while j < len(incumbent) and incumbent[j][0] <= capacity+c:
            best = min(best,incumbent[j][1])
            j += 1
        if best > extra+trips*q:
            return False
    return True


def make_c2_kernel():
    module = importlib.import_module('research.index_coupling.graph.curve')
    tree = ast.parse(inspect.getsource(module.curve))
    group = next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_group_curve')
    masks = [n for n in ast.walk(group) if isinstance(n,ast.For) and ast.unparse(n.target)=='keep_bits']
    assert len(masks)==1, 'core retention loop changed'
    masks = masks[0]
    tile_loop = next(n for n in ast.walk(group) if isinstance(n,ast.For) and masks in n.body)
    pos = tile_loop.body.index(masks)
    tile_loop.body[pos:pos] = ast.parse('''
c2_lower = solve(group, inner_ext, external | frozenset(lacking), owned) if lacking else None
if lacking:
    __c2_ledger__['bound_queries'] += 1
''').body
    solves = [n for n in masks.body if isinstance(n,ast.Assign) and ast.unparse(n.targets[0])=='inner']
    assert len(solves)==1 and ast.unparse(solves[0].value)=='solve(group, inner_ext, external | kept, owned)'
    pos = masks.body.index(solves[0])
    masks.body[pos:pos] = ast.parse('''
if c2_lower is not None:
    __c2_ledger__['choices_checked'] += 1
    results = prune(results, max_capacity, grid)
    if __c2_dominated__(results, c2_lower, cap, extra, trips):
        __c2_ledger__['choices_pruned'] += 1
        continue
''').body
    # pareto returns a tuple; retain the original list.extend contract.
    assigned = masks.body[pos]
    assign = next(n for n in assigned.body if isinstance(n,ast.Assign))
    assign.value = ast.Call(func=ast.Name(id='list',ctx=ast.Load()),args=[assign.value],keywords=[])
    namespace = dict(module.__dict__)
    ledger = {}
    namespace.update(__c2_ledger__=ledger,__c2_dominated__=lower_dominated)
    exec(compile(ast.fix_missing_locations(tree),'<grammar-v2-c2>','exec'),namespace)
    kernel = namespace['curve']

    @wraps(module.curve)
    def run(graph, *args, c2_stats=None, **kwargs):
        if kwargs.get('scalar_leaf')!='v2' or kwargs.get('grid') is not None:
            raise ValueError('C2 requires explicit grammar v2 and exact frontiers')
        ledger.clear()
        ledger.update(bound_queries=0,choices_checked=0,choices_pruned=0)
        try:
            return kernel(graph,*args,**kwargs)
        finally:
            if c2_stats is not None:
                c2_stats.update(ledger)
    return run
