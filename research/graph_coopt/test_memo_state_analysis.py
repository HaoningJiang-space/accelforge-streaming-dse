import copy
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest

from accelforge.frontend.mapping import Mapping, Temporal, Storage, Compute
from research.graph_coopt.memo_state_analysis import (
    boundary_document, compare_catalogs, digest, encode, histogram, instantiate, local_document,
    resolved_compatibility,
    analyze_candidates,
)
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from accelforge.mapper.FFM._join_pmappings.pmapping_group import PmappingGroup
from accelforge.mapper.FFM._join_pmappings.compatibility import Compatibility, Split, SplitKind
from accelforge.util import fzs


def example():
    return Mapping(nodes=[Storage(component='MainMemory', tensors=['X']),
                          Temporal(rank_variable='i', tile_shape=4),
                          Storage(component='GlobalBuffer', tensors=['X']),
                          Compute(component='MAC', einsum='E')])


def test_signature_keeps_copy_placement_backing_fusion_and_order():
    mapping = example()
    original = digest(boundary_document(mapping, {'X'}, 'compat'))
    for kind in ('placement', 'persistent', 'backing', 'fused', 'order', 'tile', 'extra_copy'):
        changed = copy.deepcopy(mapping)
        if kind == 'placement':
            changed.nodes[2].component = 'Register'
        elif kind == 'persistent':
            changed.nodes[2].persistent = True
        elif kind == 'backing':
            changed.nodes[2]._backing = {'X'}
        elif kind == 'fused':
            changed.nodes[1]._fused = True
        elif kind == 'order':
            changed.nodes[1], changed.nodes[2] = changed.nodes[2], changed.nodes[1]
        elif kind == 'tile':
            changed.nodes[1].tile_shape = 2
        else:
            changed.nodes.insert(1, Storage(component='Register', tensors=['X']))
        assert digest(boundary_document(changed, {'X'}, 'compat')) != original
    retiled = copy.deepcopy(mapping)
    retiled.nodes[1].tile_shape = 2
    assert digest(local_document(mapping, True)) == digest(local_document(retiled, True))
    assert digest(local_document(mapping)) != digest(local_document(retiled))


def test_numeric_payload_is_exact_and_unknowns_do_not_silently_merge():
    assert encode(np.uint64(2**63 + 1)) != encode(np.uint64(2**63))
    assert encode(np.float32(1)) != encode(np.float64(1))
    assert encode({'a': {2, 1}}) == encode({'a': {1, 2}})
    with pytest.raises(TypeError, match='unsupported'):
        encode(object())
    mapping = example()
    mapping.nodes[0]._constraint_lambdas = [lambda: True]
    with pytest.raises(TypeError, match='unsupported'):
        local_document(mapping)


def test_resolve_tiles_without_beautification_or_input_mutation():
    mapping = example()
    mapping.nodes[1].tile_shape = 'tile'
    result = instantiate(mapping, {'E<SEP>tile': np.uint64(1)}, 'E')
    assert result.nodes[1].tile_shape == 1
    assert mapping.nodes[1].tile_shape == 'tile'
    assert len(result.nodes) == len(mapping.nodes)
    with pytest.raises(ValueError, match='missing numeric'):
        instantiate(mapping, {}, 'E')
    mapping.nodes[1].initial_tile_shape = 3
    with pytest.raises(ValueError, match='imperfect'):
        instantiate(mapping, {'E<SEP>tile': 2}, 'E')


def test_compatibility_signature_includes_splits_ignored_by_equality():
    left = Compatibility(tensors=fzs(), reservation_indices=fzs({0}))
    right = left.update(splits=fzs({Split(SplitKind.SEQUENTIAL, 0)}))
    assert left == right
    assert resolved_compatibility(left, {}, 'E') != resolved_compatibility(right, {}, 'E')


def test_overlap_is_directed_and_counts_unique_vs_occurrences():
    def row(key, cost):
        return dict(signatures={k: key for k in ('template', 'resolved_compatibility',
                    'observed_boundary', 'full_local_mapping', 'row_payload')}, cost_resource=cost)
    source = {'E': [row('a', 'old')]}
    target = {'E': [row('a', 'new'), row('a', 'old'), row('b', 'new')]}
    report = compare_catalogs(source, target)['E']
    assert report['template'] == dict(target_rows=3, covered_rows=2, target_unique=2, shared_unique=1)
    assert report['full_mapping_and_cost_resource']['covered_rows'] == 1
    assert histogram(['a', 'a', 'b'])['unique'] == 2


def test_analyzer_includes_shared_external_input_in_both_boundaries():
    workload = SimpleNamespace(einsums=[
        SimpleNamespace(name='A', input_tensor_names={'X'}, output_tensor_names={'Y'}),
        SimpleNamespace(name='B', input_tensor_names={'X', 'Y'}, output_tensor_names={'Z'})])
    pm = SimpleNamespace(spec=SimpleNamespace(workload=workload),
                         einsum2pmappings={}, pmapping_objects={})
    for name in ('A', 'B'):
        key = uuid4()
        mapping = example()
        mapping.nodes[-1].einsum = name
        frame = PmappingDataframe(pd.DataFrame({f'{name}<SEP>mapping': [key],
            'Total<SEP>energy': [1.], 'Total<SEP>latency': [1.]}), 1, 1, skip_pareto=True)
        pm.einsum2pmappings[name] = [PmappingGroup(Compatibility(tensors=fzs()), frame)]
        pm.pmapping_objects[name] = {key: mapping}
    summary, _ = analyze_candidates(pm)
    assert summary['external_inputs'] == (('X', ('A', 'B')),)
    for stats in summary['einsums'].values():
        assert stats['boundary_tensors'] == ['X', 'Y']
        assert not stats['unsupported']
