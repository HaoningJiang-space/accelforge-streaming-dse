"""Checks for an observational continuation audit, never a new pruning rule."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from accelforge.mapper.FFM._join_pmappings.compatibility import Compatibility
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from accelforge.mapper.FFM._join_pmappings.pmapping_group import PmappingGroup
from accelforge.util import fzs
from research.graph_coopt.cut_state_analysis import (
    LEVELS, audit, isolate_row, numeric_resources, response_equal, summarize,
)


def record(name, suffix, energy):
    completions = [] if suffix is None else [dict(suffix=suffix, binding='mode', energy=energy,
                                                 latency=2., resources={'GB': 8}, units={'GB': 64})]
    return dict(id=name, group=0, interfaces={level: 'same' for level in LEVELS},
                completions=completions, prefix_cost=dict(energy=energy / 2, latency=1.),
                cut_resources={'GB': 8}, supported_suffixes=[] if suffix is None else [suffix],
                supported_bindings=[] if suffix is None else [f'{suffix}:mode'],
                reached_native_numeric_join=True)


def test_cost_difference_is_not_a_feasibility_counterexample():
    a, b = record('a', 3, 1.), record('b', 3, 2.)
    level = summarize([a, b])[LEVELS[0]]
    assert level['suffix_set_counterexample_pairs'] == 0
    assert level['cost_resource_counterexample_pairs'] == 1
    assert level['finite_observed_dominance_pairs'] == 1
    assert level['actual_rows_pruned'] == 0
    assert not level['universal_sufficiency_proven']


def test_different_supported_suffixes_falsify_the_projection():
    level = summarize([record('a', 3, 1.), record('b', 4, 1.)])[LEVELS[0]]
    assert level['suffix_set_counterexample_pairs'] == 1
    assert level['witnesses'][0]['suffixes_a_only'] == [3]
    assert level['witnesses'][0]['suffixes_b_only'] == [4]
    assert level['finite_observed_dominance_pairs'] == 0


def test_incremental_response_excludes_inherited_prefix_cost():
    a, b = record('a', 3, 1.), record('b', 3, 2.)
    a['prefix_cost']['energy'] = .25
    b['prefix_cost']['energy'] = 1.25
    assert not response_equal(a, b)
    assert response_equal(a, b, subtract_prefix=True)


def test_finite_response_dominance_can_mask_a_larger_prefix_reservation():
    a, b = record('a', 3, 1.), record('b', 3, 2.)
    a['cut_resources']['GB'] = 16
    b['cut_resources']['GB'] = 8
    # The observed completion has the same final reservation, despite the
    # prefix tradeoff. This finite witness is not a general max/spill theorem.
    level = summarize([a, b])[LEVELS[3]]
    assert level['finite_dominance_pairs_beyond_immediate_row_comparison'] == 1
    assert level['actual_rows_pruned'] == 0


def test_resource_bits_are_not_rounded_through_float64():
    bits = np.uint64(2**63 + 3)
    row = {'resource_capacity_bits<SEP>GB': np.uint64(2**64 - 1),
           'reservation<SEP>GB<SEP>0<SEP>right': bits}
    value = numeric_resources(row)['reservation<SEP>GB<SEP>0<SEP>right']
    assert type(value) is int and value == int(bits)


def test_row_isolation_retains_operation_history_and_extended_ledger():
    frame = pd.DataFrame({'Total<SEP>energy': [1., 2.], 'Total<SEP>latency': [2., 1.]})
    pdf = PmappingDataframe(frame, 40, 30, skip_pareto=True)
    pdf._prev_free_to_loop_index = 3
    group = PmappingGroup(Compatibility(fzs()), pdf)
    group.tensors['extended'] = {'mutable': [7]}
    group.n_pre_prune_mappings = 99
    state = SimpleNamespace(left=[group], pmgroups=[], remaining=('next',))
    isolated = isolate_row(state, 0, 1)
    assert isolated.left[0].mappings._prev_free_to_loop_index == 3
    assert isolated.left[0].mappings.n_total_pmappings == 40
    assert isolated.left[0].n_pre_prune_mappings == 99
    assert isolated.left[0].mappings.data.index.tolist() == [1]
    isolated.left[0].tensors['extended']['mutable'].append(8)
    isolated.left[0].mappings._data.iloc[0, 0] = 9
    assert group.tensors['extended']['mutable'] == [7]
    assert frame['Total<SEP>energy'].tolist() == [1., 2.]


@pytest.fixture(scope='module')
def real_cut():
    # Includes reconstruction for every distinct pre-Pareto cost/resource
    # response, plus a full uninstrumented/observed frontier comparison.
    return audit(2, (4, 8), 96)


def test_real_same_numeric_compatibility_does_not_determine_suffix_support(real_cut):
    levels = real_cut['interface_levels']
    assert levels['numeric_compatibility']['suffix_set_counterexample_pairs'] > 0
    assert levels['observed_copy_declarations']['suffix_set_counterexample_pairs'] > 0
    # The strongest observed key has only singleton groups here: its zero
    # counterexample count is vacuous and cannot be promoted to a theorem.
    strict = levels['execution_contract']
    assert strict['groups'] == real_cut['cut_rows']
    assert strict['same_key_pairs'] == 0
    assert not strict['universal_sufficiency_proven']


def test_real_observer_separates_capacity_checked_rows_from_pareto(real_cut):
    work = real_cut['original_continuation_work']
    assert work['materialized_pair_rows'] >= work['capacity_checked_row_occurrences']
    assert work['capacity_checked_row_occurrences'] > work['post_local_pareto_row_occurrences']
    assert real_cut['distinct_completion_cost_resource_responses_re_evaluated'] > 0
    assert real_cut['observer_numeric_frontier_equal']
    assert real_cut['observer_mapping_sources_equal']
    assert real_cut['source_and_checkpoint_unchanged']
    assert real_cut['generation_calls_after_cut'] == 0
    assert real_cut['actual_search_work_skipped'] == 0


def test_three_matmul_posthoc_ceiling_is_explicitly_oracle_assisted():
    result = audit(3, (4, 8), 128, validate_completions=False)
    oracle = result['posthoc_oracle_ablation']
    assert oracle['oracle_uses_target_suffix_results']
    assert not oracle['usable_pruning_rule']
    assert oracle['removed_rows_reaching_native_join'] > 0
    assert oracle['numeric_frontier_equal'] and oracle['mapping_source_ids_equal']
    assert oracle['continuation_work']['materialized_pair_rows'] < result['original_continuation_work']['materialized_pair_rows']
    assert not result['safe_substitution_rule_established']
