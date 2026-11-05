"""Width diagnostics and exact equality reordering have deliberately narrow scope."""
import numpy as np
import pandas as pd

from research.graph_coopt.decision_hypergraph_audit import (
    audit_equalities, connected_subgraph_diagnostic, eliminate, min_fill,
    primal, run, width_comparison,
)
from research.graph_coopt.workload_dag import WorkloadDAG


def test_min_fill_width_on_chain_and_clique_is_not_called_faq_width():
    chain = primal([['a', 'b'], ['b', 'c'], ['c', 'd']], ['a', 'b', 'c', 'd'])
    assert eliminate(chain, ['b', 'c', 'a', 'd'])['induced_width'] == 2
    assert eliminate(chain, min_fill(chain, chain))['induced_width'] == 1
    clique = primal([['a', 'b', 'c']], ['a', 'b', 'c'])
    assert eliminate(clique, min_fill(clique, clique))['induced_width'] == 2


def test_conditioning_architecture_does_not_establish_joint_decomposability():
    factors = [dict(scope=['x', 'arch:Px']), dict(scope=['y', 'arch:Px'])]
    result = width_comparison(factors, ['x', 'y'], ['x', 'y'])
    assert result['min_fill_architecture_conditioned']['induced_width'] == 0
    assert result['architecture_first_then_native']['induced_width'] == 2
    assert not result['minimum_treewidth_proven']
    assert not result['fractional_faq_width_computed']


def test_all_equality_orders_match_native_lineage_but_not_fewer_numeric_pairs():
    left = pd.DataFrame({'a': [0] * 8, 'b': range(8)})
    right = pd.DataFrame({'c': [0] * 8, 'd': [7] * 8})
    result = audit_equalities(left, right, ['a', 'b'], ['c', 'd'], pd.merge)
    assert result['status'] == 'checked'
    assert result['native_matched_pairs'] == 8
    variants = result['variants']
    assert variants['selective_key_order']['constructed_index_entries'] < variants['native_key_order']['constructed_index_entries']
    assert all(v['matched_pairs'] == 8 for v in variants.values())
    assert result['new_numeric_candidate_evaluations_avoided'] == 0
    assert not result['ffm_resource_or_pareto_order_changed']


def test_cartesian_block_factorization_does_not_remove_legal_pairs():
    left, right = pd.DataFrame({'x': range(3)}), pd.DataFrame({'y': range(4)})
    result = audit_equalities(left, right, [], [], pd.merge)
    variant = result['variants']['native_key_order']
    assert variant['blocks'] == 1 and variant['matched_pairs'] == 12
    assert variant['factorized_leaf_index_entries'] == 7
    assert variant['verification_pair_tuples_materialized'] == 12


def test_unsupported_or_over_budget_matching_is_unknown_not_infeasible():
    frame = pd.DataFrame({'a': [1., np.nan]})
    assert audit_equalities(frame, frame, ['a'], ['a'], pd.merge)['status'] == 'unknown'
    clean = pd.DataFrame({'a': range(4)})
    assert audit_equalities(clean, clean, ['a'], ['a'], pd.merge, budget=8)['status'] == 'unknown'


def test_three_matmul_topology_is_a_chain_not_two_independent_producers():
    dag = WorkloadDAG(('a', 'b', 'c'), (('a', 'b', 't1'), ('b', 'c', 't2')))
    result = connected_subgraph_diagnostic(dag)
    assert result['all_nonempty_subsets'] == 7 and result['connected_subsets'] == 6
    assert len(result['connected_disjoint_pair_partitions']) == 4
    assert result['native_ffm_stages'] == 2
    assert not result['arbitrary_ffm_tree_order_legal']


def test_real_audit_preserves_complete_native_results_and_marks_policy_barriers(tmp_path):
    report = run(2, tmp_path / 'hypergraph.json')
    assert report['full_numeric_frontier_equal'] and report['full_mapping_sources_equal']
    assert report['programs'] and report['numeric_joins']
    assert all(not p['valid_new_ffm_symbol_order_proven'] for p in report['programs'])
    assert all(p['barriers'][0]['kind'] == 'opaque_set_policy_barrier' for p in report['programs'])
    checked = [c['equality_audit'] for c in report['numeric_joins'] if c['equality_audit']['status'] == 'checked']
    assert checked and all(c['all_orders_preserve_exact_pair_set'] for c in checked)
    assert not report['full_factor_decomposition_proven']
