"""Fail-closed structural checks; these are not physical spill proofs."""
import copy

from accelforge.frontend.mapping import Compute, Mapping, Nested, Pipeline, Sequential, Storage, Temporal
from research.tracking_audit.fusion_cut_inspect import inspect_whole_tensor_cut


def example():
    return Mapping(nodes=[Storage(tensors=['T1'],component='MainMemory'),Sequential(nodes=[
        Nested(nodes=[Storage(tensors=['T1'],component='GlobalBuffer'),
                      Temporal(rank_variable='m',tile_shape=1),Compute(einsum='Matmul0',component='MAC')]),
        Nested(nodes=[Storage(tensors=['T1'],component='GlobalBuffer'),
                      Compute(einsum='Matmul1',component='MAC')]),
    ])])


def test_root_sequential_retains_copy_and_phase_context_without_claiming_spill():
    info = inspect_whole_tensor_cut(example())
    assert info['kind'] == 'root_sequential_producer_consumer'
    assert info['cross_cut_storage'] == ['MainMemory']
    assert [x['einsum'] for x in info['phase_storage']] == ['Matmul0','Matmul1']
    assert all(x['tensor_components'] == ['GlobalBuffer'] for x in info['phase_storage'])
    assert not info['safe_to_prune'] and info['proof_obligations']


def test_outer_loop_and_pipeline_are_not_whole_tensor_barriers():
    mapping = example()
    mapping.nodes.insert(0,Temporal(rank_variable='m',tile_shape=1))
    assert inspect_whole_tensor_cut(mapping)['kind'] == 'unsupported'
    mapping = example()
    mapping.nodes[-1] = Pipeline(nodes=copy.deepcopy(mapping.nodes[-1].nodes))
    assert inspect_whole_tensor_cut(mapping)['kind'] == 'unsupported'


def test_wrong_order_and_extra_compute_are_rejected():
    mapping = example()
    mapping.nodes[-1].nodes.reverse()
    assert inspect_whole_tensor_cut(mapping)['kind'] == 'unsupported'
    mapping = example()
    mapping.nodes[-1].nodes[1].nodes.append(Compute(einsum='Matmul0',component='MAC'))
    assert inspect_whole_tensor_cut(mapping)['kind'] == 'unsupported'


def test_extra_root_node_and_nested_pipeline_are_rejected():
    mapping = example()
    mapping.nodes.append(Storage(tensors=['T1'],component='GlobalBuffer'))
    assert inspect_whole_tensor_cut(mapping)['kind'] == 'unsupported'
    mapping = example()
    mapping.nodes[-1].nodes[0].nodes.insert(0,Pipeline(nodes=[]))
    assert inspect_whole_tensor_cut(mapping)['kind'] == 'unsupported'
    mapping = example()
    mapping.nodes[-1].nodes[0].nodes.append(Temporal(rank_variable='m',tile_shape=1))
    assert inspect_whole_tensor_cut(mapping)['kind'] == 'unsupported'
