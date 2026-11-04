"""Owned intermediate state for the original left-to-right FFM Join."""
from copy import deepcopy
from dataclasses import dataclass, field
import numpy as np

from .join_context import JoinContext
from .pmapping_group import PmappingGroup


def _groups(tree):
    if isinstance(tree, PmappingGroup):
        yield tree
    elif isinstance(tree, dict):
        for value in tree.values():
            yield from _groups(value)
    elif isinstance(tree, (tuple, list)):
        for value in tree:
            yield from _groups(value)


def _copy_with_frames(value, frames):
    """Preserve operation state and isolate mutable object-valued frame cells.

    Pandas deep=True (including DataFrame.__deepcopy__) copies the object-pointer
    array, not objects within it. Seed deepcopy's memo with recursively copied
    frames, preserving alias relationships throughout the entire checkpoint.
    Do not invoke PmappingGroup.copy or PmappingDataframe.update here.
    """
    frames = {id(frame): frame for frame in frames}
    # Seed every frame before copying cells so cross-frame object references
    # cannot escape through Pandas' nonrecursive __deepcopy__ implementation.
    memo = {key: frame.copy(deep=True) for key, frame in frames.items()}
    for key, frame in frames.items():
        copied = memo[key]
        for position, dtype in enumerate(frame.dtypes):
            if dtype == np.dtype('object'):
                cells = np.empty(len(frame), dtype=object)
                for i, item in enumerate(frame.iloc[:, position]):
                    cells[i] = deepcopy(item, memo)
                copied.isetitem(position, cells)
    return deepcopy(value, memo)


def _isolated_copy(value, group_tree):
    return _copy_with_frames(value, (g.mappings.data for g in _groups(group_tree)))


def copy_groups(groups):
    return _isolated_copy(groups, groups)


def copy_partial_state(state):
    pending = [holder.pmapping_groups for holder in state.pmgroups]
    return _isolated_copy(state, [state.left, pending])


def copy_candidate_payload(pmappings, decompress_data=None):
    """Isolate source candidates and optional decompression frames together."""
    frames = [g.mappings.data for g in _groups(pmappings.einsum2pmappings)]
    if decompress_data is None:
        return _copy_with_frames(pmappings, frames)
    frames.extend(frame for by_index in decompress_data.data.values() for frame in by_index.values())
    return _copy_with_frames((pmappings, decompress_data), frames)


@dataclass(eq=False)
class PartialState:
    context: JoinContext
    left: list
    left_einsum: str
    left_tensors: set
    pmgroups: list
    processed: tuple
    total_iterations: int
    n_iterations: int
    drop_valid_reservations: bool
    ignored_resources: set
    mixable_ranks: object
    aliased_tensors: dict
    timer: object
    n_mappings: dict
    runtime: dict
    nbuckets: list
    n_evaluations: int = 0
    partial_mapping_size: int = 1
    joins_completed: int = 0

    @property
    def remaining(self):
        return tuple(s.einsum_name for s in self.pmgroups)


@dataclass(frozen=True, eq=False)
class FrozenPartialState:
    """Copy-isolated in-memory checkpoint; not a disk or untrusted-input format.

    Arrays remain private mutable Python objects, so freezing the wrapper is not
    an immutable-buffer claim. snapshot/resume always copy their owned payload.
    """
    _state: PartialState = field(repr=False, compare=False)

    @property
    def processed(self):
        return self._state.processed

    @property
    def remaining(self):
        return self._state.remaining


def snapshot(state):
    state.context.check_environment()
    return FrozenPartialState(copy_partial_state(state))


def resume(checkpoint, context):
    context.require_same(checkpoint._state.context)
    state = copy_partial_state(checkpoint._state)
    # A pause is not time spent performing a merge.
    import time
    state.timer.prev_time = time.time()
    return state
