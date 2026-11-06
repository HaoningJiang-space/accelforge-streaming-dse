"""Compatibility entry point for the existing restricted 2mm search."""
from .search_engine import SearchPolicy,TwoMMSearch


def solve(graph,model,include_spill_reload=True,*,local_pruning=True,order_seed=None,witnesses=None,
          layout_pruning=True,requirements=None,layout_witnesses=None):
    policy=SearchPolicy(include_spill_reload,local_pruning,layout_pruning,order_seed)
    return TwoMMSearch(graph,model,policy).solve(requirements=requirements,witnesses=witnesses,
                                               layout_witnesses=layout_witnesses)
