"""2mm separator DP; architecture remains unbound throughout construction."""
from itertools import product
from .conditional_frontier import conditioned, frontier
from .resource_demand import summarize, compose
from .schedule_rules import generate


def solve(graph,model):
    first,second=generate(graph)
    prefixes=conditioned((summarize(p,model)for p in first),lambda s:s.plan.delivered)
    suffixes=conditioned((summarize(p,model)for p in second),lambda s:s.plan.required)
    candidates=[]
    for lefts,rights in product(prefixes.values(),suffixes.values()):
        for a,b in product(lefts,rights):
            candidates.append(compose(a,b,model))
    result=frontier(candidates)
    return result,dict(raw_prefixes=len(first),raw_consumers=len(second),
        retained_prefixes=sum(map(len,prefixes.values())),retained_consumers=sum(map(len,suffixes.values())),
        prefix_states_by_interface=[dict(interface=repr(k),states=len(v))for k,v in prefixes.items()],
        consumer_states_by_interface=[dict(interface=repr(k),states=len(v))for k,v in suffixes.items()],
        materialized_complete_pairs=len(candidates),raw_complete_pairs=len(first)*len(second),
        root_frontier_states=len(result),architecture_points_supplied=0,
        oracle_responses_used=False,ffm_search_calls=0)
