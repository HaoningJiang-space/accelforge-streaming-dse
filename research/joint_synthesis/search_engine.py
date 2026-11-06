"""Search control for the existing two-stage materialized-boundary grammar.

Physical validity/costs remain in KernelPlan, summarize and compose. A finite
candidate provider can be injected without changing those execution semantics.
This module introduces no new optimizer or cross-context substitution rule.
"""
from collections import Counter
from dataclasses import dataclass
from itertools import product
from random import Random

from .conditional_frontier import Frontier,conditioned
from .composition import compose,enforcer_choices
from .layout_rule import LayoutWitness,matching_sram_prefix
from .physical_plan import KernelPlan
from .resource_demand import summarize
from .schedule_rules import generate
from .requirements import PhysicalRequirements


@dataclass(frozen=True)
class SearchPolicy:
    include_spill_reload: bool=True
    local_pruning: bool=True
    layout_pruning: bool=True
    order_seed: int|None=None

    def __post_init__(self):
        if type(self.include_spill_reload)is not bool:
            raise ValueError('explicit boolean enforcer grammar selection required')
        if type(self.local_pruning)is not bool:
            raise ValueError('boolean local-pruning mode required')
        if type(self.layout_pruning)is not bool:
            raise ValueError('boolean layout-pruning mode required')
        if self.order_seed is not None and type(self.order_seed)is not int:
            raise ValueError('integer order seed required')

    @property
    def enforcer_grammar(self):
        return 'direct_and_spill_reload' if self.include_spill_reload else 'direct_only'

    def enforcers(self,source,target):
        return enforcer_choices(source,target) if self.include_spill_reload else ('direct',)


@dataclass
class StageCatalog:
    """One stage's immutable choices and interface-conditioned demands."""
    plans: tuple
    groups: dict
    interface_counts: Counter
    stats: dict

    @classmethod
    def build(cls,plans,operator,endpoint,model,*,prune=True,witnesses=None):
        if endpoint not in ('required','delivered'):
            raise ValueError('stage endpoint must be required or delivered')
        plans=tuple(plans)
        if any(not isinstance(p,KernelPlan) or p.op!=operator for p in plans):
            raise ValueError('candidate provider must return plans for the declared stage')
        stats={}
        groups=conditioned((summarize(p,model)for p in plans),
            lambda state:getattr(state.plan,endpoint),prune=prune,stats=stats,witnesses=witnesses)
        return cls(plans,groups,Counter(getattr(p,endpoint)for p in plans),stats)

    @property
    def retained(self):return sum(map(len,self.groups.values()))


class TwoMMSearch:
    """Compose candidates under a fixed policy and existing physical contracts.

    candidate_provider(graph, requirements) returns the two finite iterables of
    legal KernelPlans. Each solve owns fresh catalogs/frontiers/random state.
    """
    def __init__(self,graph,model,policy=None,*,candidate_provider=None):
        if policy is not None and type(policy)is not SearchPolicy:
            raise TypeError('SearchPolicy required')
        self.graph=graph;self.model=model;self.policy=policy or SearchPolicy()
        self.candidate_provider=generate if candidate_provider is None else candidate_provider

    def _completions(self,prefixes,consumers,choices,work,layout_witnesses):
        for lefts,rights in product(prefixes.groups.values(),consumers.groups.values()):
            for a,b in product(lefts,rights):
                routes=choices(a.plan.delivered,b.plan.required)
                replacement=matching_sram_prefix(a,b,prefixes.groups) if self.policy.layout_pruning else None
                if replacement is not None:
                    work['skipped_pairs']+=1;work['skipped_alternatives']+=len(routes)
                    if layout_witnesses is not None:
                        layout_witnesses.append(LayoutWitness(a,replacement,b,tuple(routes)))
                    continue
                for enforcer in routes:
                    work['complete_pairs']+=1
                    yield compose(a,b,self.model,enforcer)

    def solve(self,*,requirements=None,witnesses=None,layout_witnesses=None):
        policy=self.policy;rng=Random(policy.order_seed)if policy.order_seed is not None else None
        def choices(source,target):
            routes=list(policy.enforcers(source,target))
            if rng is not None:rng.shuffle(routes)
            return routes
        effective_requirements=requirements or PhysicalRequirements()
        effective_requirements.validate(self.graph)
        first,second=self.candidate_provider(self.graph,requirements)
        # A provider may stream choices. Materialize each stage once, as required
        # by this finite catalog grammar and its existing statistics contract.
        first=tuple(first);second=tuple(second)
        for plans,endpoint,allowed in (
                (first,'delivered',effective_requirements.producer_delivered),
                (second,'required',effective_requirements.consumer_required)):
            if any(not isinstance(p,KernelPlan)or(allowed is not None and getattr(p,endpoint)not in allowed)for p in plans):
                raise ValueError('candidate provider violated physical requirements')
        if rng is not None:
            first=list(first);second=list(second);rng.shuffle(first);rng.shuffle(second)
        producer,consumer=self.graph.operators
        prefixes=StageCatalog.build(first,producer,'delivered',self.model,prune=policy.local_pruning,
            witnesses=None if witnesses is None else witnesses.setdefault('prefix',[]))
        consumers=StageCatalog.build(second,consumer,'required',self.model,prune=policy.local_pruning,
            witnesses=None if witnesses is None else witnesses.setdefault('consumer',[]))
        work=dict(skipped_pairs=0,skipped_alternatives=0,complete_pairs=0);root_stats={}
        root=Frontier(stats=root_stats)
        for candidate in self._completions(prefixes,consumers,choices,work,layout_witnesses):
            root.add(candidate)
        result=root.finish()
        raw_alternatives=sum(n*m*len(choices(i,j))for i,n in prefixes.interface_counts.items()
                             for j,m in consumers.interface_counts.items())
        return result,dict(raw_prefixes=len(first),raw_consumers=len(second),
            retained_prefixes=prefixes.retained,retained_consumers=consumers.retained,
            prefix_states_by_interface=[dict(interface=repr(k),states=len(v))for k,v in prefixes.groups.items()],
            consumer_states_by_interface=[dict(interface=repr(k),states=len(v))for k,v in consumers.groups.items()],
            materialized_complete_pairs=work['complete_pairs'],raw_complete_pairs=raw_alternatives,
            raw_kernel_pairs=len(first)*len(second),
            materialized_kernel_pairs=sum(len(a)*len(b)for a,b in product(prefixes.groups.values(),consumers.groups.values()))-work['skipped_pairs'],
            layout_pruning=policy.layout_pruning,layout_pairs_skipped=work['skipped_pairs'],
            layout_alternatives_skipped=work['skipped_alternatives'],
            root_states_by_enforcer=dict(Counter(d.plan.enforcer for d in result)),
            local_pruning=policy.local_pruning,frontier_work=dict(prefix=prefixes.stats,consumer=consumers.stats,root=root_stats),
            enforcer_grammar=policy.enforcer_grammar,root_frontier_states=len(result),architecture_points_supplied=0,
            oracle_responses_used=False,ffm_search_calls=0)
