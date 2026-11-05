"""2mm separator DP; architecture remains unbound throughout construction."""
from itertools import product
from collections import Counter
from .conditional_frontier import conditioned, frontier
from .resource_demand import summarize
from .composition import compose, enforcer_choices
from .schedule_rules import generate


def solve(graph,model,include_spill_reload=True):
    if type(include_spill_reload) is not bool:
        raise ValueError('explicit boolean enforcer grammar selection required')
    def choices(source,target):
        return enforcer_choices(source,target) if include_spill_reload else ('direct',)
    first,second=generate(graph)
    prefixes=conditioned((summarize(p,model)for p in first),lambda s:s.plan.delivered)
    suffixes=conditioned((summarize(p,model)for p in second),lambda s:s.plan.required)
    candidates=[]
    for lefts,rights in product(prefixes.values(),suffixes.values()):
        for a,b in product(lefts,rights):
            for enforcer in choices(a.plan.delivered,b.plan.required):
                candidates.append(compose(a,b,model,enforcer))
    result=frontier(candidates)
    first_counts=Counter(p.delivered for p in first)
    second_counts=Counter(p.required for p in second)
    raw_alternatives=sum(n*m*len(choices(i,j))
        for i,n in first_counts.items() for j,m in second_counts.items())
    return result,dict(raw_prefixes=len(first),raw_consumers=len(second),
        retained_prefixes=sum(map(len,prefixes.values())),retained_consumers=sum(map(len,suffixes.values())),
        prefix_states_by_interface=[dict(interface=repr(k),states=len(v))for k,v in prefixes.items()],
        consumer_states_by_interface=[dict(interface=repr(k),states=len(v))for k,v in suffixes.items()],
        materialized_complete_pairs=len(candidates),raw_complete_pairs=raw_alternatives,
        raw_kernel_pairs=len(first)*len(second),
        materialized_kernel_pairs=sum(len(a)*len(b) for a,b in product(prefixes.values(),suffixes.values())),
        root_states_by_enforcer=dict(Counter(d.plan.enforcer for d in result)),
        enforcer_grammar='direct_and_spill_reload' if include_spill_reload else 'direct_only',
        root_frontier_states=len(result),architecture_points_supplied=0,
        oracle_responses_used=False,ffm_search_calls=0)
