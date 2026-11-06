"""Frozen-baseline differential controls and typed-frontier contracts.

Fixtures are exact c0f62874 Git blobs, not a second maintained implementation.
They use the unchanged physical cost/composition backend and their own Pareto.
"""
import hashlib
from itertools import product
import sys
import types
from dataclasses import dataclass
import pytest
from research.joint_synthesis.graph_dp import solve
from research.joint_synthesis.graph_ir import TwoMM,CostModel
from research.joint_synthesis.search_engine import SearchPolicy,StageCatalog,TwoMMSearch
from research.joint_synthesis.conditional_frontier import Frontier,frontier,conditioned
from research.joint_synthesis.schedule_rules import generate
from research.joint_synthesis.resource_demand import summarize
from research.joint_synthesis.composition import compose
from research.joint_synthesis.requirements import PhysicalRequirements

LEGACY_DP = '''"""2mm separator DP; architecture remains unbound throughout construction."""
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
'''

LEGACY_PARETO = '''"""Exact componentwise demand frontier; equal-vector sources may be folded."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DominanceWitness:
    removed: object
    dominator: object


class Frontier:
    """Incremental numerical frontier; tracing is opt-in, not search overhead."""
    def __init__(self,witnesses=None,stats=None):
        self.kept=[];self.removed=[] if witnesses is not None else None
        self.witnesses=witnesses;self.stats=stats if stats is not None else {}

    def dominates(self,a,b):
        self.stats['dominance_checks']=self.stats.get('dominance_checks',0)+1
        return all(x<=y for x,y in zip(a.vector,b.vector))

    def add(self,state):
        self.stats['inputs']=self.stats.get('inputs',0)+1
        if any(self.dominates(old,state) for old in self.kept):
            if self.removed is not None:self.removed.append(state)
            self.stats['pruned']=self.stats.get('pruned',0)+1
            return
        survivors=[]
        for old in self.kept:
            if self.dominates(state,old):
                if self.removed is not None:self.removed.append(old)
                self.stats['pruned']=self.stats.get('pruned',0)+1
            else:survivors.append(old)
        survivors.append(state);self.kept=survivors
        self.stats['peak_kept']=max(self.stats.get('peak_kept',0),len(self.kept))

    def finish(self):
        if self.witnesses is not None:
            # Resolve to a final survivor, even if an earlier dominator was
            # itself removed later. Witness resolution is validation-only.
            self.witnesses.extend(DominanceWitness(s,next(p for p in self.kept
                if all(a<=b for a,b in zip(p.vector,s.vector)))) for s in self.removed)
            self.removed.clear()
        return list(self.kept)


def frontier(states,*,witnesses=None,stats=None):
    active=Frontier(witnesses,stats)
    for state in states:active.add(state)
    return active.finish()


def conditioned(states,property_key,*,witnesses=None,stats=None,prune=True):
    groups={}
    for state in states:
        groups.setdefault(property_key(state),[]).append(state)
    return {key:frontier(group,witnesses=witnesses,stats=stats) if prune else group
            for key,group in groups.items()}
'''


def load_legacy():
    def module(name,source):
        m=types.ModuleType('research.joint_synthesis.'+name)
        m.__package__='research.joint_synthesis';sys.modules[m.__name__]=m
        exec(compile(source,'<frozen '+name+'>','exec'),m.__dict__)
        return m
    old_frontier=module('_refactor_old_frontier',LEGACY_PARETO)
    old_dp=module('_refactor_old_dp',LEGACY_DP)
    old_dp.conditioned=old_frontier.conditioned;old_dp.frontier=old_frontier.frontier
    return old_dp


def git_blob(source):
    data=source.encode();return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


def test_reference_fixtures_are_exact_base_git_blobs():
    assert git_blob(LEGACY_DP)=='bc640aaa618ce47bf612b6227a5abea083260b62'
    assert git_blob(LEGACY_PARETO)=='c69bb34d6f3a714ff5e7cb0de981d0fca1ac3770'


@pytest.mark.parametrize('spill,prune,layout,seed',list(product((False,True),(False,True),(False,True),(None,7,29))))
def test_complete_outputs_stats_and_witnesses_match_frozen_solver(spill,prune,layout,seed):
    legacy=load_legacy();graph=TwoMM(1,2,2,1);model=CostModel(3,2,7,5)
    old_witnesses={};new_witnesses={};old_layout=[];new_layout=[]
    kwargs=dict(local_pruning=prune,layout_pruning=layout,order_seed=seed)
    old_result,old_stats=legacy.solve(graph,model,spill,witnesses=old_witnesses,layout_witnesses=old_layout,**kwargs)
    actual,stats=solve(graph,model,spill,witnesses=new_witnesses,layout_witnesses=new_layout,**kwargs)
    assert actual==old_result and stats==old_stats
    normalize=lambda w:{k:[(r.removed,r.dominator)for r in rows]for k,rows in w.items()}
    assert normalize(new_witnesses)==normalize(old_witnesses)
    assert new_layout==old_layout


@pytest.mark.parametrize('empty',[False,True])
def test_requirements_and_empty_catalog_preserve_results(empty):
    graph=TwoMM(1,2,2,1);model=CostModel();a,b=generate(graph)
    allowed=frozenset()if empty else frozenset([a[0].delivered])
    requirement=PhysicalRequirements(allowed,frozenset([b[0].required]))
    assert solve(graph,model,requirements=requirement)==load_legacy().solve(graph,model,requirements=requirement)


def test_provider_is_injected_once_without_changing_grammar():
    graph=TwoMM(1,2,2,1);model=CostModel();called=[]
    def provider(g,req):
        called.append((g,req));a,b=generate(g,req)
        return iter(a),iter(b)
    engine=TwoMMSearch(graph,model,SearchPolicy(order_seed=7),candidate_provider=provider)
    expected=solve(graph,model,order_seed=7)
    assert engine.solve()==expected and engine.solve()==expected
    assert called==[(graph,None),(graph,None)]


def test_provider_cannot_supply_another_stage_operator():
    graph=TwoMM();a,b=generate(graph)
    with pytest.raises(ValueError):StageCatalog.build(b,graph.operators[0],'delivered',CostModel())


def test_same_vector_length_does_not_allow_different_physical_state_types():
    a,b=generate(TwoMM());model=CostModel()
    local=summarize(a[0],model);complete=compose(local,summarize(b[0],model),model)
    assert len(local.vector)==len(complete.vector)==6
    with pytest.raises(TypeError):frontier([local,complete])
    with pytest.raises(TypeError):Frontier().dominates(local,complete)
    for prune in (True,False):
        with pytest.raises(TypeError):conditioned([local,complete],lambda s:type(s),prune=prune)


@dataclass
class NumericState:
    vector:tuple


def test_mismatched_dimensions_cannot_be_silently_truncated():
    with pytest.raises(ValueError):frontier([NumericState((1,2)),NumericState((1,2,3))])
    with pytest.raises(ValueError):frontier([NumericState(())])
    assert frontier([])==[]


def test_witness_resolution_rechecks_dimension_invariants():
    a=NumericState((2,2));b=NumericState((1,1));w=[]
    f=Frontier(witnesses=w);f.add(a);f.add(b)
    a.vector=(2,)
    with pytest.raises(ValueError):f.finish()


@pytest.mark.parametrize('kwargs',[dict(include_spill_reload=1),dict(local_pruning=1),dict(layout_pruning=1),dict(order_seed=True)])
def test_policy_rejects_ambiguous_modes(kwargs):
    with pytest.raises(ValueError):SearchPolicy(**kwargs)


def test_injected_provider_cannot_ignore_physical_requirements():
    graph=TwoMM();model=CostModel()
    def ignores_request(g,req):return generate(g)
    engine=TwoMMSearch(graph,model,candidate_provider=ignores_request)
    request=PhysicalRequirements(producer_delivered=frozenset())
    with pytest.raises(ValueError):engine.solve(requirements=request)


def test_finish_rejects_mutated_kept_vector_even_without_witnesses():
    state=NumericState((1,2));f=Frontier();f.add(state);state.vector=(1,)
    with pytest.raises(ValueError):f.finish()
