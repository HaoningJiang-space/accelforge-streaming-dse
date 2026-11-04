import pandas as pd

from accelforge.frontend.mapping import TilePattern
from accelforge.mapper.FFM._join_pmappings.compatibility import Compatibility, Loop, TensorReservation
from accelforge.util import fzs
from research.graph_coopt.template_support_audit import interface_key, possible_interfaces, support_status


def comp(ranks, memory='GlobalBuffer'):
    loops = tuple(Loop(rank, TilePattern(2, 2), False) for rank in ranks)
    return Compatibility(tensors=fzs({TensorReservation(loops, 'X', memory)}),
                         reservation_indices=fzs({len(loops)}))


def test_unit_loop_collapse_can_connect_different_original_templates():
    producer, consumer = comp(['i', 'j']), comp(['j'])
    assert interface_key(producer, {'X'}) != interface_key(consumer, {'X'})
    collapsed = producer.drop_loop_indices({0})
    assert interface_key(collapsed, {'X'}) == interface_key(consumer, {'X'})
    assert support_status(possible_interfaces(producer, {'X'}),
                          [possible_interfaces(consumer, {'X'})]) == 'possible_support'


def test_all_deletions_and_legal_permutations_stay_inside_relaxation():
    source = comp(['i', 'j', 'k'])
    predicted = possible_interfaces(source, {'X'})
    for mask in range(8):
        dropped = source.drop_loop_indices([i for i in range(3) if not mask & (1 << i)])
        for variant, _ in dropped.make_equivalent_permutations():
            assert interface_key(variant, {'X'}) in predicted
    # Ignoring ranks and order may retain incompatible pairs; that is intentional.
    assert possible_interfaces(comp(['different']), {'X'}) == possible_interfaces(comp(['j']), {'X'})


def test_missing_data_or_budget_is_unknown_not_unsupported():
    assert possible_interfaces(comp(['i', 'j']), {'X'}, max_patterns=1) is None
    assert possible_interfaces(comp(['i']), {'not-X'}) is None
    assert support_status(None, []) == 'unknown'
    assert support_status(frozenset({'known'}), [None]) == 'unknown'
    assert support_status(possible_interfaces(comp(['i']), {'X'}),
                          [possible_interfaces(comp(['i'], 'MainMemory'), {'X'})]) == 'no_relaxed_support'


def test_actual_ffm_normalization_uses_nonunit_iteration_columns():
    from types import SimpleNamespace
    from research.graph_coopt.template_support_audit import observed_masks
    import importlib
    source = comp(['i', 'j'])
    job = SimpleNamespace(compatibility=source, einsum_name='E')
    module = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_pmappings_from_templates')
    assert observed_masks(job, pd.DataFrame({'n_iterations<SEP>0': [1, 4],
                                           'n_iterations<SEP>1': [4, 4]}), module) == {1: 1, 3: 1}


def test_read_only_observer_runs_all_real_jobs_and_preserves_complete_frontier():
    from research.graph_coopt.template_support_audit import SupportAudit
    from research.graph_coopt.test_graph_memo import numeric_frontier
    from research.tracking_audit import common
    from research.tracking_audit.shape_capacity_audit import build
    from pandas.testing import assert_frame_equal
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    case = common.Case('matmuls', 'nvdla', (2, 2, 4))
    spec = build(case, (4, 8), 128, common.RU)
    plain = common.make_pmappings(spec, print_number_of_pmappings=False)
    audit = SupportAudit(spec, max_patterns=1)  # deliberately force unknown patterns
    with audit.observe():
        observed = common.make_pmappings(spec, print_number_of_pmappings=False)
    report = audit.report()
    assert report['summary']['templates'] == sum(len(jobs) for jobs in plain.einsum2jobs.values())
    assert all(r['evaluation_calls'] == 1 for r in report['templates'])
    assert report['summary']['status_counts'].get('unknown', 0) > 0
    assert report['summary']['actual_skipped_jobs'] == 0
    assert report['summary']['inspection_unknowns'] == 0
    for r in report['templates']:
        assert sum(r['observed_effective_loop_patterns'].values()) == r['output_rows']
    assert_frame_equal(numeric_frontier(common.join_pmappings(plain).data),
                       numeric_frontier(common.join_pmappings(observed).data))
