"""Observe the frozen 2mm engine; no search/model/provider code is changed.

Run timing and observation in separate passes. Scoped function wrappers are
diagnostic only, serial, exception-safe, and removed before returning. Nested
inclusive times must not be added; exclusive named-scope remainders can be.
"""
from collections import defaultdict
from contextlib import ExitStack
from dataclasses import asdict
from functools import wraps
import inspect
from time import perf_counter_ns
from unittest.mock import patch

from research.joint_synthesis import search_engine as engine
from research.joint_synthesis import conditional_frontier as pareto
from research.joint_synthesis import physical_plan as plans
from research.joint_synthesis import composition


class WorkObservation:
    """Process-local observation context, never part of the search API."""
    _active = False

    def __init__(self):
        self.scopes = defaultdict(lambda: dict(calls=0, failed_calls=0,
                                               inclusive_ns=0, exclusive_ns=0))
        self.buckets = defaultdict(int)
        self.frames = []
        self.stack = ExitStack()
        self.used = False

    def _stage(self):
        return next((f['stage'] for f in reversed(self.frames) if f['stage']), 'root')

    def _install(self, owner, name, label, bucket, stage=None):
        descriptor = inspect.getattr_static(owner, name)
        function = descriptor.__func__ if isinstance(descriptor, (classmethod, staticmethod)) else descriptor

        @wraps(function)
        def observed(*args, **kwargs):
            current_stage = stage(args, kwargs) if stage else self._stage()
            key = label.format(stage=current_stage)
            frame = dict(stage=current_stage, start=perf_counter_ns(), children=0)
            self.frames.append(frame)
            failed = True
            try:
                result = function(*args, **kwargs)
                failed = False
                return result
            finally:
                elapsed = perf_counter_ns() - frame['start']
                assert self.frames.pop() is frame
                exclusive = elapsed - frame['children']
                stat = self.scopes[key]
                stat['calls'] += 1
                stat['failed_calls'] += failed
                stat['inclusive_ns'] += elapsed
                stat['exclusive_ns'] += exclusive
                self.buckets[bucket] += exclusive
                if self.frames:
                    self.frames[-1]['children'] += elapsed

        replacement = type(descriptor)(observed) if isinstance(descriptor, (classmethod, staticmethod)) else observed
        self.stack.enter_context(patch.object(owner, name, replacement))

    def __enter__(self):
        if WorkObservation._active or self.used:
            raise RuntimeError('use a fresh serial observation context')
        WorkObservation._active = True
        self.used = True
        try:
            self._install(engine.TwoMMSearch, 'solve', 'search', 'search_control', lambda a,k: None)
            self._install(engine, 'generate', 'provider.generate', 'candidate_generation', lambda a,k: None)
            self._install(plans.KernelPlan, '__init__', 'kernel.construct.{stage}', 'candidate_generation',
                          lambda a,k: (k['op'] if 'op' in k else a[1]).name)
            self._install(engine.StageCatalog, 'build', 'catalog.{stage}', 'catalog_control',
                          lambda a,k: (k['operator'] if 'operator' in k else a[2]).name)
            self._install(engine, 'conditioned', 'grouping.{stage}', 'interface_grouping')
            self._install(engine, 'summarize', 'evaluate.{stage}', 'local_evaluation',
                          lambda a,k: (k['plan'] if 'plan' in k else a[0]).op.name)
            for method in ('add', 'finish'):
                self._install(pareto.Frontier, method, 'pareto.'+method+'.{stage}', 'pareto_maintenance')
            self._install(engine.SearchPolicy, 'enforcers', 'routes', 'interface_analysis')
            self._install(engine, 'matching_sram_prefix', 'layout.match', 'interface_analysis')
            self._install(engine, 'compose', 'compose', 'composition_control')
            self._install(composition, 'conversion', 'conversion', 'conversion_evaluation')
            self._install(plans.CompletePlan, '__init__', 'complete.construct', 'complete_materialization')
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *exc):
        try:
            return self.stack.__exit__(*exc)
        finally:
            WorkObservation._active = False

    def snapshot(self):
        if self.frames:
            raise RuntimeError('observation still running')
        scopes = {key:dict(calls=v['calls'], failed_calls=v['failed_calls'],
                           inclusive_s=v['inclusive_ns']/1e9, exclusive_s=v['exclusive_ns']/1e9)
                  for key,v in sorted(self.scopes.items())}
        buckets = {key:value/1e9 for key,value in sorted(self.buckets.items())}
        search_ns = self.scopes.get('search', {}).get('inclusive_ns', 0)
        if sum(self.buckets.values()) != search_ns:
            raise AssertionError('named exclusive scopes did not partition the search interval')
        return dict(scopes=scopes, exclusive_buckets_s=buckets,
                    search_inclusive_s=search_ns/1e9,
                    exclusive_partition_equal=True,
                    attribution='Instrumented named-scope remainders; include wrapper overhead and uninstrumented helpers.')


def observe(graph, model, policy):
    with WorkObservation() as observation:
        start = perf_counter_ns()
        result, stats = engine.TwoMMSearch(graph, model, policy).solve()
        wall_s = (perf_counter_ns()-start)/1e9
    trace = observation.snapshot()
    scopes = trace['scopes']
    def calls(name):
        return scopes.get(name, {}).get('calls', 0)
    stages = {}
    for stage, raw, kept, key in (('produce','raw_prefixes','retained_prefixes','prefix'),
                                  ('consume','raw_consumers','retained_consumers','consumer')):
        work = stats['frontier_work'][key]
        stages[stage] = dict(candidates=stats[raw],
            kernel_plan_constructions=calls('kernel.construct.'+stage),
            evaluations=calls('evaluate.'+stage), retained=stats[kept],
            pareto_inputs=work.get('inputs', 0), pareto_add_calls=calls('pareto.add.'+stage),
            dominance_checks=work.get('dominance_checks', 0),
            pareto_pruned=work.get('pruned', 0),
            largest_interface_frontier=work.get('peak_kept', 0))
        s = stages[stage]
        if not s['candidates'] == s['kernel_plan_constructions'] == s['evaluations']:
            raise AssertionError('candidate construction/evaluation accounting disagrees')
        if s['pareto_add_calls'] != s['pareto_inputs']:
            raise AssertionError('local Pareto accounting disagrees')
    complete = calls('complete.construct')
    if not complete == calls('compose') == calls('conversion') == stats['materialized_complete_pairs']:
        raise AssertionError('composition/materialization accounting disagrees')
    if calls('pareto.add.root') != complete or stats['frontier_work']['root']['inputs'] != complete:
        raise AssertionError('root Pareto input accounting disagrees')
    trace.update(instrumented_wall_s=wall_s, stages=stages,
        composition=dict(kernel_pairs_visited=stats['materialized_kernel_pairs']+stats['layout_pairs_skipped'],
            layout_pairs_skipped=stats['layout_pairs_skipped'],
            complete_pairs_composed=complete, complete_plan_constructions=complete,
            raw_complete_alternatives=stats['raw_complete_pairs'],
            conversion_evaluations=calls('conversion'), route_queries_including_statistics=calls('routes'),
            layout_match_calls=calls('layout.match')),
        root_pareto=dict(inputs=complete, states=len(result), **{
            key:stats['frontier_work']['root'].get(key,0)
            for key in ('dominance_checks','pruned','peak_kept')}),
        policy=asdict(policy), search_stats=stats,
        no_evaluation_avoided_before_local_pareto=all(
            s['evaluations']==s['candidates'] for s in stages.values()))
    return (result, stats), trace
