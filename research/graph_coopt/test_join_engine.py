"""Controller differential tests and proof that resume performs no prefix work."""
from copy import deepcopy
from unittest.mock import patch
import importlib

import pytest
from pandas.testing import assert_frame_equal

from accelforge.mapper.FFM._join_pmappings.compress_pmappings import compress_einsum2pmappings
from accelforge.mapper.FFM._join_pmappings.join_context import JoinContext
from accelforge.mapper.FFM._join_pmappings.join_pmappings import restore_mappings
from accelforge.mapper.FFM._join_pmappings import join_engine
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from research.graph_coopt._reference_join_bd39555f import reference_join_pmappings
from research.graph_coopt.memo import GraphMemo
from research.graph_coopt.workload_dag import WorkloadDAG
from research.graph_coopt.ffm_adapter import join_memo
from research.graph_coopt.test_graph_memo import numeric_frontier
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, validate_pick


@pytest.fixture(scope='module', params=[2, 3])
def candidates(request):
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    n = request.param
    case = common.Case('matmuls', 'nvdla', (n, 4, 8))
    capacity = 96 if n == 2 else 128
    pm = common.make_pmappings(build(case, (4, 8), capacity, common.RU),
                              print_number_of_pmappings=False)
    return case, capacity, pm


def reference(pm, **kwargs):
    pm = deepcopy(pm)
    compressed, metadata = compress_einsum2pmappings(pm.einsum2pmappings)
    data = reference_join_pmappings(compressed, pm.spec, **kwargs)
    return restore_mappings(pm, data, metadata, tuple(pm.einsum2pmappings))


def assert_same(expected, actual):
    assert_frame_equal(numeric_frontier(expected.data), numeric_frontier(actual.data))
    assert expected.total_mappings == actual.total_mappings
    assert expected.valid_mappings == actual.valid_mappings
    assert expected.einsum_names == actual.einsum_names
    ids = lambda result: sorted(common.mapping_identity(row['Total<SEP>mapping']())
                                for _, row in result.data.iterrows())
    assert ids(expected) == ids(actual)


def test_pause_resume_matches_frozen_controller_without_prefix_replay(candidates):
    case, capacity, pm = candidates
    expected = reference(pm)
    memo = GraphMemo(WorkloadDAG.from_workload(pm.spec.workload), pm)
    calls = []
    original = PmappingDataframe.merge_next

    def counted(self, right, *args, **kwargs):
        calls.append(tuple(c.split('<SEP>')[0] for c in right.data
                           if c.endswith('<SEP>compressed_index')))
        return original(self, right, *args, **kwargs)

    with patch.object(PmappingDataframe, 'merge_next', counted):
        initial = memo.start()
        with pytest.raises(ValueError, match='before all Einsums'):
            memo.finalize(initial)
        with pytest.raises(ValueError, match='next Einsum'):
            memo.advance(initial, 'not-the-next-einsum')
        middle = memo.advance(initial, 'Matmul1')
        assert initial.processed == ('Matmul0',)
        assert initial.joins_completed == 0
        assert middle.joins_completed == 1
        assert calls and all(names == ('Matmul1',) for names in calls)
        prefix_calls = len(calls)
        memo.save_partial(middle)
        metadata = memo.groups_for(('Matmul0', 'Matmul1'))
        assert metadata and sum(g.row_count for g in metadata) > 0
        # This hook forbids any re-entry into local candidate generation.
        with patch('accelforge.mapper.FFM._make_pmappings.make_pmappings.get_jobs',
                   side_effect=AssertionError('candidate generation replayed')):
            resumed = memo.resume_partial(middle.processed)
            assert len(calls) == prefix_calls
            actual = join_memo(memo, resumed)
        assert all(names == ('Matmul2',) for names in calls[prefix_calls:])
        if len(pm.einsum2pmappings) == 3:
            assert len(calls) > prefix_calls
        # Two resumes and all advances/finalizations must leave the stored
        # snapshot unchanged, including object-valued frame cells.
        other = memo.resume_partial(middle.processed)
        assert other.joins_completed == 1
        for left, right in zip(middle.left, other.left):
            assert_frame_equal(left.mappings.data, right.mappings.data)
        other.left[0].tensors.clear()
        for a, b in zip(middle.left, memo.resume_partial(middle.processed).left):
            assert a.tensors == b.tensors
        for a, b in zip(initial.left, memo.start().left):
            assert_frame_equal(a.mappings.data, b.mappings.data)
    assert_same(expected, actual)
    for _, row in actual.data.iterrows():
        assert validate_pick(case, (4, 8), capacity, row)['ok']


def test_context_order_architecture_and_environment_are_strict(candidates, monkeypatch):
    _, _, pm = candidates
    memo = GraphMemo(WorkloadDAG.from_workload(pm.spec.workload), pm)
    state = memo.start()
    checkpoint = join_engine.snapshot(state)
    assert checkpoint != join_engine.snapshot(state)
    another = JoinContext.from_spec(pm.spec)
    with pytest.raises(ValueError, match='different context'):
        join_engine.resume(checkpoint, another)
    changed_spec = deepcopy(pm.spec)
    changed_spec.arch.find('GlobalBuffer').size *= 2
    with pytest.raises(ValueError, match='different context'):
        join_engine.resume(checkpoint, JoinContext.from_spec(changed_spec))
    changed_graph = build(common.Case('matmuls', 'nvdla', (4, 4, 8)), (4, 8), 128, common.RU)
    with pytest.raises(ValueError, match='different context'):
        join_engine.resume(checkpoint, JoinContext.from_spec(changed_graph))
    other_memo = GraphMemo(memo.dag, pm)
    with pytest.raises(ValueError, match='different context'):
        other_memo.save_partial(state)
    monkeypatch.setenv('AF_MEMBERSHIP_JOIN', 'early')
    with pytest.raises(ValueError, match='switches changed'):
        join_engine.resume(checkpoint, state.context)


@pytest.mark.parametrize('el_only', [False, True])
def test_full_wrapper_matches_frozen_controller(candidates, el_only):
    _, _, pm = candidates
    pm = deepcopy(pm)
    if el_only:
        pm.spec.mapper.ffm.metrics = common.EL
    expected = reference(pm)
    actual = common.join_pmappings(deepcopy(pm))
    assert_same(expected, actual)


def test_real_prefix_rejects_changed_pareto_tolerance_at_every_execution_boundary(candidates, monkeypatch):
    _, _, pm = candidates
    memo = GraphMemo(WorkloadDAG.from_workload(pm.spec.workload), pm)
    state = memo.start()
    checkpoint = join_engine.snapshot(state)
    complete = state
    while complete.remaining:
        complete = memo.advance(complete)
    pareto = importlib.import_module('accelforge.mapper.FFM._pareto_df.pareto')
    monkeypatch.setattr(pareto, 'TOLERANCE', .1)
    for operation in (lambda: join_engine.snapshot(state),
                      lambda: join_engine.resume(checkpoint, state.context),
                      lambda: memo.start(), lambda: memo.advance(state), lambda: memo.finalize(complete)):
        with pytest.raises(ValueError, match='Pareto tolerance changed'):
            operation()
    monkeypatch.setattr(pareto, 'TOLERANCE', 0.)
    assert join_engine.resume(checkpoint, state.context).processed == state.processed


def test_saved_group_metadata_does_not_restore_or_copy_full_state(candidates):
    _, _, pm = candidates
    memo = GraphMemo(WorkloadDAG.from_workload(pm.spec.workload), pm)
    middle = memo.advance(memo.start())
    memo.save_partial(middle)
    with patch.object(memo, 'resume_partial', side_effect=AssertionError('metadata restored state')), \
         patch('accelforge.mapper.FFM._join_pmappings.partial_state.copy_partial_state',
               side_effect=AssertionError('metadata copied state')):
        first = memo.groups_for(middle.processed)
        assert first is memo.groups_for(middle.processed)
    assert sum(g.row_count for g in first) == sum(len(g.mappings.data) for g in middle.left)


def test_generation_contract_is_provenance_not_a_join_equality_constraint(candidates, monkeypatch):
    _, _, pm = candidates
    assert len(pm.generation_contracts) == 1
    assert pm.generation_contracts[0].pareto_tolerance == 0.
    before = pm.generation_contracts
    # Generation-only settings may intentionally differ at the Join boundary.
    monkeypatch.setenv('AF_TARGET_ENUMERATION', 'independent')
    memo = GraphMemo(WorkloadDAG.from_workload(pm.spec.workload), pm)
    state = memo.start()
    assert state.context.generation_contracts == before
    assert dict(state.context.switches)['AF_TARGET_ENUMERATION'] == 'independent'
    assert ('AF_TARGET_ENUMERATION', 'independent') not in before[0].switches
