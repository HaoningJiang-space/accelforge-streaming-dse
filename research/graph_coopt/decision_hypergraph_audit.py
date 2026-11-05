"""Decision-incidence and exact equality-order feasibility gate, not a mapper.

Inspect actual symbolic template programs, including non-relational policy
barriers. Reorder only conjunctions of already prepared equality predicates.
Keep FFM's execution, Reservation and Pareto order. Never infer an arbitrary
Fusion join order or a semiring decomposition from computational connectivity.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import hashlib
import importlib
import itertools
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import sympy

from research.graph_coopt.ffm_adapter import prepare_candidates
from research.graph_coopt.cut_state_analysis import numeric_frontier
from research.graph_coopt.workload_dag import WorkloadDAG
from accelforge.mapper.FFM._join_pmappings.partial_state import copy_candidate_payload
from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.target_enumeration import _symbol_order
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, validate_pick
from accelforge.mapper.FFM.generation_contract import effective_pareto_tolerance


PARAMETERS = ('arch:Px', 'arch:Py', 'arch:C_GB', 'arch:B_GB')


def primal(scopes, variables):
    graph = {v: set() for v in variables}
    for scope in scopes:
        for v in scope:
            graph[v].update(set(scope) - {v})
    return graph


def eliminate(graph, order):
    graph = {v: set(n) for v, n in graph.items()}
    width, bags = 0, []
    for v in order:
        neighbors = graph[v]
        width = max(width, len(neighbors))
        bags.append([v, *sorted(neighbors)])
        for n in neighbors:
            graph[n].update(neighbors - {n})
            graph[n].discard(v)
        del graph[v]
    boundary_width = max((len(n) for n in graph.values()), default=0)
    return dict(induced_width=max(width, boundary_width), eliminated_variable_width=width,
                retained_boundary_width=boundary_width, bags=bags, retained_variables=sorted(graph))


def min_fill(graph, candidates):
    graph = {v: set(n) for v, n in graph.items()}
    remaining, order = set(candidates), []
    while remaining:
        def score(v):
            neighbors = graph[v]
            missing = sum(b not in graph[a] for a, b in itertools.combinations(sorted(neighbors), 2))
            return missing, len(neighbors), v
        v = min(remaining, key=score)
        neighbors = graph[v]
        for n in neighbors:
            graph[n].update(neighbors - {n})
            graph[n].discard(v)
        del graph[v]
        remaining.remove(v)
        order.append(v)
    return order


def width_comparison(factors, symbols, native):
    variables = sorted(set(symbols) | set(PARAMETERS))
    scopes = [f['scope'] for f in factors if f['scope']]
    graph = primal(scopes, variables)
    conditioned = {v: n - set(PARAMETERS) for v, n in graph.items() if v not in PARAMETERS}
    native = list(native)
    return dict(
        native_architecture_retained=eliminate(graph, native),
        reverse_architecture_retained=eliminate(graph, list(reversed(native))),
        min_fill_architecture_retained=eliminate(graph, min_fill(graph, symbols)),
        architecture_first_then_native=eliminate(graph, [*PARAMETERS, *native]),
        min_fill_architecture_conditioned=eliminate(conditioned, min_fill(conditioned, symbols)),
        representation_clique_lower_bound=max((len(set(s)) - 1 for s in scopes), default=0),
        minimum_treewidth_proven=False, fractional_faq_width_computed=False,
    )


def program_incidence(kwargs):
    symbols = set(kwargs['symbols'])
    names = sorted(map(str, symbols))
    native = list(map(str, _symbol_order(kwargs['symbols'], kwargs['what_tiles_symbol'])))
    factors = []
    for obj in kwargs['objectives']:
        scope = set(map(str, obj.formula.free_symbols & symbols))
        parameter = None
        if obj.name.endswith('reuse_input'):
            parameter = PARAMETERS[0]
        elif obj.name.endswith('reuse_output'):
            parameter = PARAMETERS[1]
        elif obj.name.endswith('GlobalBuffer'):
            parameter = PARAMETERS[2]
        elif obj.name == common.LATENCY:
            parameter = PARAMETERS[3]  # conservative latency-model dependence
        if parameter:
            scope.add(parameter)
        policy = obj.try_best_if_none_reaches_min
        factors.append(dict(name=obj.name, scope=sorted(scope), formula=str(obj.formula),
                            kind='ordered_set_fallback' if policy else
                                 'row_constraint' if obj.min_value is not None or obj.max_value is not None else 'cost_expression',
                            row_local_formula=not policy,
                            new_ffm_search_order_justified=False))
    relations = kwargs['what_tiles_symbol']
    for i, pair in enumerate([*relations.what_tiles_symbol, *relations.tile_shape_and_initial]):
        scope = sorted({str(s) for expression in pair for s in sympy.sympify(expression).free_symbols & symbols})
        factors.append(dict(name=f'tile_relation_{i}', scope=scope, kind='tile_domain_relation',
                            row_local_formula=True, new_ffm_search_order_justified=False))
    # Scope is a conservative dependency barrier, NOT a claimed relational
    # factorization of ordered fallback/Pareto. Avoid falsely dropping history.
    barriers = [dict(name='cohort_and_prefix_pareto_history', scope=[*names, *PARAMETERS],
                     kind='opaque_set_policy_barrier', relational_elimination_justified=False)]
    hard = [f for f in factors if f['kind'] in ('row_constraint', 'tile_domain_relation')]
    return dict(symbols=names, native_symbol_order=native, factors=factors, barriers=barriers,
                hard_scope_width=width_comparison(hard, names, native),
                cost_scope_width=width_comparison(factors, names, native),
                conservative_policy_scope_width=width_comparison([*factors, *barriers], names, native),
                costs_are_atomic_expression_scopes=True, expression_dag_auxiliary_decomposition_implemented=False,
                valid_new_ffm_symbol_order_proven=False)


class ProgramObserver:
    def __init__(self):
        self.programs = []

    @contextmanager
    def installed(self):
        tiles = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')
        original = tiles.get_tile_shape_choices_for_targets
        def observe(**kwargs):
            record = program_incidence(kwargs)
            record.update(einsum=str(kwargs['job'].einsum_name),
                          template=kwargs['job'].mapping.compact_str())
            result = original(**kwargs)
            record['returned_tile_rows'] = len(result[0])
            self.programs.append(record)
            return result
        with patch.object(tiles, 'get_tile_shape_choices_for_targets', observe):
            yield self


def matching_blocks(left, right, key_pairs, order):
    """Exact equality conjunction as a trie of row-index blocks, not full rows.

    Report pending index occurrences (not RSS). Pair tuples are expanded ONLY
    for verification, separately counted. No resource/cost operation is reordered.
    """
    stack = [(0, np.arange(len(left)), np.arange(len(right)))]
    peak, constructed, blocks = len(left) + len(right), len(left) + len(right), []
    while stack:
        depth, lhs, rhs = stack.pop()
        if depth == len(order):
            if len(lhs) and len(rhs):
                blocks.append((lhs, rhs))
            continue
        lk, rk = key_pairs[order[depth]]
        lg, rg = defaultdict(list), defaultdict(list)
        for p in lhs:
            lg[left[lk].iloc[int(p)]].append(p)
        for p in rhs:
            rg[right[rk].iloc[int(p)]].append(p)
        for value in lg.keys() & rg.keys():
            a, b = np.array(lg[value], dtype=np.int64), np.array(rg[value], dtype=np.int64)
            stack.append((depth + 1, a, b))
            constructed += len(a) + len(b)
        peak = max(peak, len(lhs) + len(rhs) + sum(len(a) + len(b) for _, a, b in stack))
    pairs = {(int(a), int(b)) for lhs, rhs in blocks for a in lhs for b in rhs}
    return dict(order=list(order), blocks=len(blocks), matched_pairs=len(pairs),
                factorized_leaf_index_entries=sum(len(a) + len(b) for a, b in blocks),
                peak_pending_index_occurrences=peak, constructed_index_entries=constructed,
                verification_pair_tuples_materialized=len(pairs)), pairs


def audit_equalities(left, right, left_keys, right_keys, pandas_merge, budget=200000):
    if len(left) * len(right) > budget:
        return dict(status='unknown', reason='pair_verification_budget')
    pairs = list(dict.fromkeys(zip(left_keys, right_keys)))
    if any(left[a].dtype != right[b].dtype or left[a].isna().any() or right[b].isna().any()
           for a, b in pairs):
        return dict(status='unknown', reason='mixed_dtype_or_null_key')
    # Independent Pandas lineage oracle; audit-only columns never enter FFM.
    a = pd.DataFrame({f'l{i}': left[x].to_numpy() for i, (x, _) in enumerate(pairs)})
    b = pd.DataFrame({f'r{i}': right[y].to_numpy() for i, (_, y) in enumerate(pairs)})
    a['lid'], b['rid'] = np.arange(len(left)), np.arange(len(right))
    expected = pandas_merge(a, b, how='inner' if pairs else 'cross',
                            **(dict(left_on=[f'l{i}' for i in range(len(pairs))],
                                    right_on=[f'r{i}' for i in range(len(pairs))]) if pairs else {}))
    expected = set(zip(map(int, expected['lid']), map(int, expected['rid'])))
    def selectivity(i):
        x, y = pairs[i]
        lc, rc = Counter(left[x]), Counter(right[y])
        return sum(n * rc[v] for v, n in lc.items()), i
    orders = dict(native_key_order=list(range(len(pairs))),
                  reversed_key_order=list(reversed(range(len(pairs)))),
                  selective_key_order=sorted(range(len(pairs)), key=selectivity))
    variants = {}
    for name, order in orders.items():
        stats, actual = matching_blocks(left, right, pairs, order)
        if actual != expected:
            raise AssertionError('equality-order audit disagrees with native Pandas lineage')
        variants[name] = stats
    return dict(status='checked', key_pairs=pairs, input_cartesian_pairs=len(left) * len(right),
                native_matched_pairs=len(expected), variants=variants,
                all_orders_preserve_exact_pair_set=True,
                ffm_resource_or_pareto_order_changed=False, new_numeric_candidate_evaluations_avoided=0)


class JoinObserver:
    def __init__(self):
        self.calls = []
        self.active = None

    @contextmanager
    def installed(self):
        from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
        merge, pandas_merge = PmappingDataframe.merge_next, pd.merge
        def observe(pdf, right, *args, **kwargs):
            if self.active is not None:
                raise ValueError('serial non-streaming audit only')
            call = dict(input_rows=[len(pdf.data), len(right.data)])
            self.calls.append(call)
            self.active = call
            try:
                result = merge(pdf, right, *args, **kwargs)
                call['post_local_pareto_rows'] = len(result.data)
                return result
            finally:
                self.active = None
        def materialize(left, right, *args, **kwargs):
            result = pandas_merge(left, right, *args, **kwargs)
            if self.active is not None:
                if 'equality_audit' in self.active:
                    raise AssertionError('unexpected nested Pandas merge')
                self.active.update(materialized_pair_rows=len(result),
                    pair_frame_payload_bytes=int(result.memory_usage(index=False, deep=True).sum()),
                    equality_audit=audit_equalities(left, right, kwargs.get('left_on', []),
                                                    kwargs.get('right_on', []), pandas_merge))
                audit = self.active['equality_audit']
                if audit['status'] == 'checked' and audit['native_matched_pairs'] != len(result):
                    raise AssertionError('equality audit did not describe native materialization')
            return result
        with patch.object(PmappingDataframe, 'merge_next', observe), patch.object(pd, 'merge', materialize):
            yield self


def connected_subgraph_diagnostic(dag):
    """Small topology count, not DPhyp or a legal FFM Join-order optimizer."""
    nodes = list(dag.nodes)
    adjacency = {n: set() for n in nodes}
    for a, b, _ in dag.edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    subsets = [frozenset(nodes[i] for i in range(len(nodes)) if mask & (1 << i))
               for mask in range(1, 1 << len(nodes))]
    def connected(s):
        todo, reached = [next(iter(s))], set()
        while todo:
            v = todo.pop()
            if v not in reached:
                reached.add(v)
                todo.extend((adjacency[v] & s) - reached)
        return reached == s
    valid = [s for s in subsets if connected(s)]
    pairs = [[sorted(a), sorted(b)] for i, a in enumerate(valid) for b in valid[i + 1:]
             if not a & b and connected(a | b)]
    return dict(all_nonempty_subsets=len(subsets), connected_subsets=len(valid),
                connected_disjoint_pair_partitions=pairs, native_ffm_stages=len(nodes) - 1,
                arbitrary_ffm_tree_order_legal=False, dphyp_implemented=False,
                topology_alone_additional_native_pairs_avoided=0)


def run(n, output):
    common.clear_switches()
    common.af.set_n_parallel_jobs(1)
    if effective_pareto_tolerance() != 0:
        raise ValueError('decision audit requires zero Pareto tolerance')
    case = common.Case('matmuls', 'nvdla', (n, 16, 16))
    spec = build(case, (16, 16), 4096, common.RU)
    dag = WorkloadDAG.from_workload(spec.workload)
    programs = ProgramObserver()
    with programs.installed():
        pm = common.make_pmappings(spec, print_number_of_pmappings=False)
    expected = common.join_pmappings(copy_candidate_payload(pm))
    store = prepare_candidates(pm)
    observer = JoinObserver()
    active_rows = []
    with observer.installed():
        state = store.start()
        active_rows.append(sum(len(g.mappings.data) for g in state.left))
        while state.remaining:
            state = store.advance(state)
            active_rows.append(sum(len(g.mappings.data) for g in state.left))
        actual = store.finalize(state)
    assert_frame_equal(numeric_frontier(expected.data), numeric_frontier(actual.data))
    ids = lambda result: sorted(common.mapping_identity(r['Total<SEP>mapping']()) for _, r in result.data.iterrows())
    if ids(expected) != ids(actual):
        raise AssertionError('observation changed full Mapping sources')
    for _, row in actual.data.iterrows():
        if not validate_pick(case, (16, 16), 4096, row)['ok']:
            raise AssertionError('final mapping reconstruction failed')
    # One conservative coarse joint representation, not a minimal factorization.
    # Resource transfer over the whole prefix is deliberately left opaque.
    selectors = [f'mapping:{name}' for name in dag.nodes]
    opaque = [dict(name='full_resource_and_fusion_transfer', scope=[*selectors, *PARAMETERS],
                   relational_elimination_justified=False)]
    report = dict(case=str(case), graph=dict(nodes=dag.nodes, edges=dag.edges),
                  computational_topology=connected_subgraph_diagnostic(dag),
                  programs=programs.programs, numeric_joins=observer.calls,
                  coarse_joint_opaque_width=width_comparison(opaque, selectors, selectors),
                  native_active_frontier_rows_by_stage=active_rows,
                  native_peak_active_frontier_rows=max(active_rows),
                  native_materialized_pair_rows=sum(c['materialized_pair_rows'] for c in observer.calls),
                  native_largest_pair_frame_rows=max(c['materialized_pair_rows'] for c in observer.calls),
                  native_largest_pair_payload_bytes=max(c['pair_frame_payload_bytes'] for c in observer.calls),
                  full_numeric_frontier_equal=True, full_mapping_sources_equal=True,
                  reconstructed_final_mappings=len(actual.data),
                  arbitrary_ffm_join_reordering_proven=False, full_factor_decomposition_proven=False,
                  new_joint_search_speedup_measured=False,
                  width_scope='Primal induced width for displayed syntactic scopes; not GHT/FAQ-width or a minimum-width proof.',
                  factorization_scope='Reorders prepared equality checks only. Input payloads, Reservation and full pair cost evaluation remain necessary.')
    report['source_sha256'] = {str(p.relative_to(common.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (Path(__file__), common.ROOT / 'accelforge/mapper/FFM/_join_pmappings/pmapping_dataframe.py')}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('programs', 'numeric_joins')}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--n', type=int, choices=(2, 3), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.n, args.output)
