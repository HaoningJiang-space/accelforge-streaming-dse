"""2mm separator DP; architecture remains unbound throughout construction."""
from itertools import product
from collections import Counter
from random import Random
from .conditional_frontier import conditioned, frontier
from .resource_demand import summarize
from .composition import compose, enforcer_choices
from .schedule_rules import generate
from .layout_rule import LayoutWitness, matching_sram_prefix


def solve(graph,model,include_spill_reload=True,*,local_pruning=True,order_seed=None,witnesses=None,
          layout_pruning=True,requirements=None,layout_witnesses=None):
    if type(include_spill_reload) is not bool:
        raise ValueError('explicit boolean enforcer grammar selection required')
    def choices(source,target):
        routes=list(enforcer_choices(source,target) if include_spill_reload else ('direct',))
        if rng is not None:rng.shuffle(routes)
        return routes
    if type(local_pruning) is not bool:raise ValueError('boolean local-pruning mode required')
    if type(layout_pruning) is not bool:raise ValueError('boolean layout-pruning mode required')
    if order_seed is not None and type(order_seed) is not int:raise ValueError('integer order seed required')
    rng=Random(order_seed) if order_seed is not None else None
    first,second=generate(graph,requirements)
    if rng is not None:
        first=list(first);second=list(second);rng.shuffle(first);rng.shuffle(second)
    prefix_stats={};suffix_stats={};root_stats={}
    prefixes=conditioned((summarize(p,model)for p in first),lambda s:s.plan.delivered,
        prune=local_pruning,stats=prefix_stats,witnesses=None if witnesses is None else witnesses.setdefault('prefix',[]))
    suffixes=conditioned((summarize(p,model)for p in second),lambda s:s.plan.required,
        prune=local_pruning,stats=suffix_stats,witnesses=None if witnesses is None else witnesses.setdefault('consumer',[]))
    candidates=[];skipped_pairs=0;skipped_alternatives=0
    for lefts,rights in product(prefixes.values(),suffixes.values()):
        for a,b in product(lefts,rights):
            routes=choices(a.plan.delivered,b.plan.required)
            replacement=matching_sram_prefix(a,b,prefixes) if layout_pruning else None
            if replacement is not None:
                skipped_pairs+=1;skipped_alternatives+=len(routes)
                if layout_witnesses is not None:
                    layout_witnesses.append(LayoutWitness(a,replacement,b,tuple(routes)))
                continue
            for enforcer in routes:
                candidates.append(compose(a,b,model,enforcer))
    result=frontier(candidates,stats=root_stats)
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
        materialized_kernel_pairs=sum(len(a)*len(b) for a,b in product(prefixes.values(),suffixes.values()))-skipped_pairs,
        layout_pruning=layout_pruning,layout_pairs_skipped=skipped_pairs,
        layout_alternatives_skipped=skipped_alternatives,
        root_states_by_enforcer=dict(Counter(d.plan.enforcer for d in result)),
        local_pruning=local_pruning,frontier_work=dict(prefix=prefix_stats,consumer=suffix_stats,root=root_stats),
        enforcer_grammar='direct_and_spill_reload' if include_spill_reload else 'direct_only',
        root_frontier_states=len(result),architecture_points_supplied=0,
        oracle_responses_used=False,ffm_search_calls=0)
