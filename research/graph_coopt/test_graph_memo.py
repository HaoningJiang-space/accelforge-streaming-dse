from types import SimpleNamespace

import pytest
from pandas.testing import assert_frame_equal

from research.graph_coopt.ffm_adapter import generate_memo, join_memo
from research.graph_coopt.physical_traits import PhysicalInterface
from research.graph_coopt.workload_dag import WorkloadDAG
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, validate_pick
from accelforge.mapper.FFM.main import join_pmappings
from research.graph_coopt.memo_state_analysis import analyze_candidates


def einsum(name, inputs, outputs):
    return SimpleNamespace(name=name, input_tensor_names=set(inputs),
                           output_tensor_names=set(outputs))


def test_graph_rejects_branch_cycles_and_ambiguous_producers():
    branch = SimpleNamespace(einsums=[einsum('a', ['x'], ['y']),
                                     einsum('b', ['y'], ['z']),
                                     einsum('c', ['y'], ['w'])])
    graph = WorkloadDAG.from_workload(branch)
    with pytest.raises(ValueError, match='sequential chains'):
        graph.require_chain()
    with pytest.raises(ValueError, match='multiple producers'):
        WorkloadDAG.from_workload(SimpleNamespace(einsums=[
            einsum('a', ['x'], ['y']), einsum('b', ['x'], ['y'])]))
    with pytest.raises(ValueError, match='non-topological'):
        WorkloadDAG.from_workload(SimpleNamespace(einsums=[
            einsum('b', ['y'], ['z']), einsum('a', ['x'], ['y'])]))
    trait = PhysicalInterface('same')
    assert not trait.proves_substitutability(trait)


def numeric_frontier(frame):
    numeric = frame.select_dtypes(include='number')
    columns = sorted(numeric.columns)
    return numeric[columns].sort_values(columns).reset_index(drop=True)


@pytest.mark.parametrize('n,capacity', [(2, 96), (3, 128)])
def test_memo_preserves_real_ffm_frontier_and_reconstructs(n, capacity):
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    case = common.Case('matmuls', 'nvdla', (n, 4, 8))
    spec = build(case, (4, 8), capacity, common.RU)
    memo = generate_memo(spec)
    assert memo.dag.nodes == tuple(f'Matmul{i}' for i in range(n))
    assert memo.dag.prefixes()[-1] == memo.dag.nodes
    assert len(memo.groups) > 0
    assert all(not group.interface.copies_complete for group in memo.groups)
    snapshot = memo.materialize()
    before = {name: [group.mappings.data.copy(deep=True) for group in groups]
              for name, groups in snapshot.einsum2pmappings.items()}
    analysis, _ = analyze_candidates(snapshot)
    assert all(not stats['unsupported'] for stats in analysis['einsums'].values())
    assert all(stats['certified_semantic_merges'] == 0 for stats in analysis['einsums'].values())
    for name, groups in snapshot.einsum2pmappings.items():
        for frame, group in zip(before[name], groups):
            assert_frame_equal(frame, group.mappings.data)
    assert sum(len(memo.groups_for((node,))) for node in memo.dag.nodes) == len(memo.groups)
    with pytest.raises(ValueError, match='single-Einsum'):
        memo.groups_for(memo.dag.nodes)
    # FFM mutates its input; compare independent snapshots from the same source.
    reference = join_pmappings(memo.materialize())
    actual = join_memo(memo)
    assert len(actual.data) > 0
    assert_frame_equal(numeric_frontier(reference.data), numeric_frontier(actual.data))
    reference_ids = sorted(common.mapping_identity(row['Total<SEP>mapping']())
                           for _, row in reference.data.iterrows())
    actual_ids = sorted(common.mapping_identity(row['Total<SEP>mapping']())
                        for _, row in actual.data.iterrows())
    assert reference_ids == actual_ids
    for _, row in actual.data.iterrows():
        assert validate_pick(case, (4, 8), capacity, row)['ok']
    # Modifying a materialized group must not alter the memo's stored candidates.
    clone = memo.materialize()
    group = next(iter(clone.einsum2pmappings.values()))[0]
    original_count = len(group.mappings.data)
    group.mappings._data = group.mappings.data.iloc[:0].copy()
    fresh = memo.materialize()
    assert len(next(iter(fresh.einsum2pmappings.values()))[0].mappings.data) == original_count
