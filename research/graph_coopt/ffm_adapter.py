"""Candidate preparation and resumable reference-order FFM composition."""
from copy import deepcopy

from accelforge.mapper.FFM.main import make_pmappings
from accelforge.mapper.FFM._join_pmappings.compress_pmappings import compress_einsum2pmappings
from accelforge.mapper.FFM._join_pmappings.join_context import JoinContext
from accelforge.mapper.FFM._join_pmappings import join_engine
from accelforge.mapper.FFM._join_pmappings.join_pmappings import (
    _check_einsum2pmappings_not_empty, restore_mappings,
)

from .memo import GraphMemo
from .workload_dag import WorkloadDAG


def generate_memo(spec):
    dag = WorkloadDAG.from_workload(spec.workload)
    dag.require_chain()
    return GraphMemo(dag, make_pmappings(spec, print_number_of_pmappings=False))


class CandidateStore:
    """Owned source/decompression metadata plus one strict Join context."""
    def __init__(self, pmappings):
        self._source = deepcopy(pmappings)
        _check_einsum2pmappings_not_empty(self._source.einsum2pmappings, self._source)
        self._groups, self._decompress = compress_einsum2pmappings(self._source.einsum2pmappings)
        self.context = JoinContext.from_spec(self._source.spec)

    def start(self):
        return join_engine.start(self._groups, self.context)

    def advance(self, state, next_einsum=None):
        return join_engine.advance(state, next_einsum, self.context)

    def finalize(self, state):
        joined = join_engine.finalize(state, self.context)
        source = deepcopy(self._source)
        return restore_mappings(source, joined, deepcopy(self._decompress),
                                tuple(source.einsum2pmappings))


def prepare_candidates(pmappings):
    """Prepare already generated candidates; does not regenerate any Einsum."""
    return CandidateStore(pmappings)


def join_memo(memo, state=None):
    state = memo.start() if state is None else state
    while state.remaining:
        state = memo.advance(state)
    return memo.finalize(state)
