"""Fusion labels must agree with the reservations used to build Compatibility."""
from types import SimpleNamespace

import pytest

from accelforge.frontend.mapping import Compute, Mapping, Reservation, Storage, Temporal
from accelforge.frontend._workload_isl._symbolic import Irrelevant, Relevant, PartiallyRelevant
from accelforge.frontend.renames import Rank
from accelforge.mapper.FFM._join_pmappings.compatibility import Compatibility
from accelforge.model._looptree.reuse.symbolic.symbolic import insert_reservation_nodes, label_fused_loops


@pytest.mark.parametrize('relevance,barrier,expected', [
    (Irrelevant(), False, [False, False]),
    (PartiallyRelevant('M'), False, [True, False]),
    (Relevant('M'), False, [True, True]),
    (Relevant('M'), True, [False, False]),
])
def test_actual_lowering_defines_fused_prefix(relevance, barrier, expected):
    holder = Storage(tensors=['X'], component='MainMemory')
    holder._backing = {'X'}
    holder._lower = True
    nodes = [holder]
    if barrier:
        other = Storage(tensors=['Y'], component='GlobalBuffer')
        other._backing = {'Y'}
        other._lower = False
        nodes.append(other)
    loops = [Temporal(rank_variable='m', tile_shape=4), Temporal(rank_variable='n', tile_shape=2)]
    nodes += loops + [Compute(einsum='E', component='MAC')]
    info = SimpleNamespace(
        workload=SimpleNamespace(einsums={'E': SimpleNamespace(tensor_names={'X', 'Y'})},
                                 tensor_names_used_in_multiple_einsums={'X'}),
        tensor_to_relevancy={'X': {'m': relevance, 'n': Relevant('N')}},
        tensor_to_reservation_backer_id={},
    )
    insert_reservation_nodes(nodes, info, {'X'})
    compatibility = Compatibility.from_mapping(
        Mapping(nodes=nodes), {'X'}, {'X': {'m': {Rank('M')}, 'n': {Rank('N')}}},
    )
    assert [loop._fused for loop in loops] == expected
    assert sum(loop._fused for loop in loops) == compatibility.n_loops


def test_later_copy_does_not_extend_backing_reservation_boundary():
    holder = Storage(tensors=['X'], component='MainMemory')
    holder._backing = {'X'}
    holder._lower = True
    loop = Temporal(rank_variable='m', tile_shape=4)
    nodes = [holder, Reservation(purposes=['X'], resource='MainMemory'), loop,
             Reservation(purposes=['X'], resource='GlobalBuffer')]
    label_fused_loops(nodes, {'X'})
    assert not loop._fused
