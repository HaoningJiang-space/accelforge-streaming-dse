"""Owned intermediate state for the original left-to-right FFM Join."""
from copy import deepcopy
from dataclasses import dataclass, field

from .join_context import JoinContext


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
    return FrozenPartialState(deepcopy(state))


def resume(checkpoint, context):
    context.require_same(checkpoint._state.context)
    state = deepcopy(checkpoint._state)
    # A pause is not time spent performing a merge.
    import time
    state.timer.prev_time = time.time()
    return state
