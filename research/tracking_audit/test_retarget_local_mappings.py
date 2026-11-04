import copy

import pytest

from accelforge.frontend.mapping import Mapping, Temporal, Spatial, Storage, Compute
from research.tracking_audit.retarget_local_mappings import binding_slots, rebindings, signature


def example(storage=False):
    nodes = [Temporal(rank_variable='x', tile_shape=4),
             Temporal(rank_variable='y', tile_shape=8)]
    if storage:
        nodes.append(Storage(component='GlobalBuffer', tensors=['A']))
    nodes += [Spatial(rank_variable='x', tile_shape=1, component='ArrayFanout', name='reuse_input'),
              Spatial(rank_variable='y', tile_shape=1, component='ArrayFanout', name='reuse_output'),
              Compute(component='MAC', einsum='E')]
    return Mapping(nodes=nodes)


def test_rebinding_preserves_source_and_checks_individual_dimensions():
    source = example()
    before = signature(source)
    candidates = list(rebindings(source, {'x':8,'y':8}, (8,4)))
    assert len(candidates) == 12
    assert signature(source) == before
    assert any([n.tile_shape for n in p.nodes[:2]] == [8,4] for p in candidates)
    assert all(p.nodes[0].tile_shape <= 8 and p.nodes[1].tile_shape <= 4 for p in candidates)
    assert all(signature(p, 'factor_split') == signature(source, 'factor_split') for p in candidates)


def test_storage_retile_is_distinct_from_pure_rebinding():
    source = example(storage=True)
    assert not binding_slots(source)
    assert binding_slots(source, True) == {0:3, 1:4}
    assert not list(rebindings(source, {'x':8,'y':8}, (8,4)))
    candidates = list(rebindings(source, {'x':8,'y':8}, (8,4), True))
    assert len(candidates) == 12
    assert any(signature(p, 'factor_split') != signature(source, 'factor_split') for p in candidates)
    assert all(signature(p, 'storage_retile') == signature(source, 'storage_retile') for p in candidates)


def test_fusion_boundary_and_storage_positions_never_erased():
    source = example()
    source.nodes[0]._fused = True
    assert 0 not in binding_slots(source, True)
    changed = copy.deepcopy(source)
    changed.nodes[0].tile_shape = 8
    assert signature(source, 'storage_retile') != signature(changed, 'storage_retile')
    assert signature(example(True), 'template') != signature(example(False), 'template')


def test_imperfect_tile_is_explicitly_unsupported():
    source = example()
    source.nodes[0].initial_tile_shape = 3
    with pytest.raises(ValueError, match='imperfect'):
        list(rebindings(source, {'x':8,'y':8}, (8,4)))
