"""Regression checks for state that historical copy()/update() cannot retain."""
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from accelforge.frontend.mapping import TilePattern
from accelforge.mapper.FFM._join_pmappings.compatibility import (
    Compatibility, Loop, TensorReservation, Split, SplitKind,
)
from accelforge.mapper.FFM._join_pmappings.compress_pmappings import compress_einsum2pmappings
from accelforge.mapper.FFM._join_pmappings.join_context import JoinContext
from accelforge.mapper.FFM._join_pmappings.join_pmappings import JoiningTimer, PmappingsOneEinsum
from accelforge.mapper.FFM._join_pmappings.partial_state import (
    PartialState, copy_groups, copy_candidate_payload, snapshot, resume,
)
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from accelforge.mapper.FFM._join_pmappings.pmapping_group import PmappingGroup
from accelforge.util import fzs


def group(payload):
    loops = (Loop('j', TilePattern(2, 2), True), Loop('i', TilePattern(4, 4), False))
    reservation = TensorReservation(loops, 'T1', 'GlobalBuffer')
    compatibility = Compatibility(tensors=fzs({reservation}),
                                  splits=fzs({Split(SplitKind.SEQUENTIAL, 0)}),
                                  reservation_indices=fzs({0, 2}))
    data = pd.DataFrame({
        'reservation<SEP>GlobalBuffer<SEP>0<SEP>right': [0.1, 0.1],
        'reservation<SEP>GlobalBuffer<SEP>1<SEP>right': [0.2, 0.3],
        'reservation<SEP>GlobalBuffer<SEP>2<SEP>right': [0.5, 0.6],
        'A<SEP>compressed_index': np.array([2**63, 2**63 + 1], dtype=np.uint64),
        'mutable_source': [payload, payload],
    }, index=[5, 9])
    frame = PmappingDataframe(data, 128, 64, skip_pareto=True)
    assert frame.free_to_loop_index(0)
    result = PmappingGroup(compatibility, frame)
    # A combined group's ledger may exceed its still-live Compatibility.
    result.tensors['history'] = TensorReservation((), 'history', 'MainMemory')
    result.n_pre_prune_mappings = 4096
    return result


def state(left, right):
    context = JoinContext.from_spec(SimpleNamespace(name='unit-test-spec'))
    return PartialState(context=context, left=[left], left_einsum='A',
        left_tensors={'T1', 'history'}, pmgroups=[PmappingsOneEinsum('B', [right])],
        processed=('A',), total_iterations=2, n_iterations=1,
        drop_valid_reservations=False, ignored_resources={'MainMemory'},
        mixable_ranks={}, aliased_tensors={'T1': {'alias'}}, timer=JoiningTimer(),
        n_mappings={'A': 4096}, runtime={}, nbuckets=[])


def test_tensor_names_track_addition_removal_and_do_not_expose_internal_set():
    g = group({'events': []})
    assert g.tensor_names == {'T1', 'history'}
    g.tensors['new'] = TensorReservation((), 'new', 'GlobalBuffer')
    assert g.tensor_names == {'T1', 'history', 'new'}
    PmappingGroup.remove_dead_tensors([g], {'new'})
    assert g.tensor_names == {'new'}
    g.tensor_names.add('not-a-tensor')
    assert g.tensor_names == {'new'}


def test_snapshot_preserves_ledger_release_cursor_permutation_and_sources():
    payload = {'events': ['generated']}
    original = state(group(payload), group(payload))
    with patch.object(PmappingGroup, 'copy', side_effect=AssertionError('lossy group copy')),\
         patch.object(PmappingDataframe, 'copy', side_effect=AssertionError('lossy table copy')),\
         patch.object(PmappingDataframe, 'update', side_effect=AssertionError('table rebuilt')):
        checkpoint = snapshot(original)
        resume(checkpoint, original.context)
    payload['events'].append('outside-mutation')
    restored = resume(checkpoint, original.context)
    g = restored.left[0]
    assert g.tensors == original.left[0].tensors
    assert g.n_pre_prune_mappings == 4096
    assert [loop.rank_name for loop in g.compatibility.loops] == ['j', 'i']
    assert g.compatibility.splits == original.left[0].compatibility.splits
    assert g.mappings._prev_free_to_loop_index == 0
    assert g.mappings.left_reservations == original.left[0].mappings.left_reservations
    assert g.mappings.right_reservations == original.left[0].mappings.right_reservations
    assert g.mappings.data['A<SEP>compressed_index'].tolist() == [2**63, 2**63 + 1]
    # A lost release cursor would re-enter _make_reservations on this call.
    with patch.object(g.mappings, '_make_reservations', side_effect=AssertionError('release replayed')):
        assert not g.mappings.free_to_loop_index(0)
    cell = g.mappings.data['mutable_source'].iloc[0]
    assert cell == {'events': ['generated']}
    assert cell is g.mappings.data['mutable_source'].iloc[1]
    assert cell is restored.pmgroups[0].pmapping_groups[0].mappings.data['mutable_source'].iloc[0]
    cell['events'].append('resumed-mutation')
    g.tensors.clear()
    again = resume(checkpoint, original.context)
    assert again.left[0].tensors == original.left[0].tensors
    assert again.left[0].mappings.data['mutable_source'].iloc[0] == {'events': ['generated']}


def test_compression_is_isolated_at_owned_working_copy_boundary():
    from research.tracking_audit import common
    common.af.set_n_parallel_jobs(1)
    original = group({'events': []})
    before = original.mappings.data.copy(deep=True)
    working = copy_groups({'A': [original]})
    assert working['A'][0].mappings._prev_free_to_loop_index == 0
    compress_einsum2pmappings(working)
    assert_frame_equal(original.mappings.data, before)
    assert original.mappings.data.index.tolist() == [5, 9]
    assert working['A'][0].mappings.data.index.tolist() == [0, 1]


def test_candidate_sources_and_decompression_objects_are_copied_together():
    payload = {'events': ['generated']}
    g = group(payload)
    pm = SimpleNamespace(einsum2pmappings={'A': [g]}, pmapping_objects={'A': payload})
    metadata = SimpleNamespace(data={'A': {0: g.mappings.data[['mutable_source']]}})
    source, decompression = copy_candidate_payload(pm, metadata)
    copied = source.pmapping_objects['A']
    assert copied is source.einsum2pmappings['A'][0].mappings.data['mutable_source'].iloc[0]
    assert copied is decompression.data['A'][0]['mutable_source'].iloc[0]
    copied['events'].append('output-mutation')
    assert payload == {'events': ['generated']}
    independent = copy_candidate_payload(pm)
    assert independent.pmapping_objects['A'] == {'events': ['generated']}
