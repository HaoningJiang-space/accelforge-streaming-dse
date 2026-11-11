"""Shared graph fixtures and certified order selection, independent of runners.

Graph definitions, dimensions and representative-order selection are unchanged.
Use graph_for for all controls, dag_graph for the historical DAG-only registry.
"""
from research.index_coupling.graph.branch_symmetry import branch_graph, topological_orders, unequal_prefix_graph
from research.index_coupling.graph.model import Graph
from research.index_coupling.graph.stacks import ffn_stack, attention_stack
from research.index_coupling.run_ancestor_width import control
from research.index_coupling.unified_search import certified_automorphisms, mixed_branch_graph
from .boundary import workload

D1_CASES = {
    'chain_tiny': ('chain', (2, 2, 2)),
    'residual_tiny': ('residual', (2, 2, 2)),
    'residual_rectangle': ('residual', (3, 2, 4)),
    'fork_join_tiny': ('fork_join', (2, 2, 2, 2)),
    'fork_join_rectangle': ('fork_join', (2, 2, 4, 2)),
    'gated_fork_join_tiny': ('gated_fork_join', (2, 2, 2, 2)),
}

JOIN_CASES = ('two_stage_join', 'asymmetric_join', 'mixed_join')
DAG_CASES = tuple(D1_CASES) + JOIN_CASES


def dag_graph(name):
    if name in D1_CASES:
        return workload(*D1_CASES[name])[0]
    if name == 'two_stage_join':
        return branch_graph((2, 2, 2, 2, 2), branches=2, join=True)
    if name == 'asymmetric_join':
        graph = unequal_prefix_graph((2, 1, 2, 2, 1))
        return Graph(dict(graph.sizes), [(o, dict(graph.access[o])) for o in graph.ops] +
                     [('Join', {'V0': ('I','N'), 'V1': ('I','N'), 'Y': ('I','N')})])
    if name == 'mixed_join':
        return mixed_branch_graph((2, 2, 2, 2))
    raise ValueError(name)


def select_orders(graph, symmetry):
    orders = tuple(topological_orders(graph))
    if not symmetry:
        return orders, len(orders), 1
    maps, _ = certified_automorphisms(graph)
    selected, seen = [], set()
    for order in orders:
        orbit = min(tuple(m.ops[o] for o in order) for m in maps)
        if orbit not in seen:
            seen.add(orbit)
            selected.append(order)
    return tuple(selected), len(orders), len(maps)


def graph_for(name):
    if name == 'ffn4':
        return ffn_stack(4)
    if name == 'attention4':
        return attention_stack(4)
    if name == 'ancestor8':
        return control(8)
    return dag_graph(name)
