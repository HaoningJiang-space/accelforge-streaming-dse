"""Architecture-bound, lossless storage of original FFM candidate groups."""
from dataclasses import dataclass
from accelforge.mapper.FFM._join_pmappings.partial_state import copy_candidate_payload

from .physical_traits import PhysicalInterface


@dataclass(frozen=True)
class CandidateGroup:
    einsum: str
    group_index: int
    interface: PhysicalInterface
    row_count: int
    columns: tuple[str, ...]


@dataclass(frozen=True)
class IntermediateGroup:
    subgraph: tuple[str, ...]
    group_index: int
    interface: PhysicalInterface
    row_count: int
    columns: tuple[str, ...]


class GraphMemo:
    """Snapshot groups without interpreting equality as a safe merge.

    The complete MultiEinsumPmappings snapshot retains its own Spec, units,
    per-Einsum mapping source objects, and architecture evaluation metadata.
    The snapshot cannot be queried for another architecture.
    """
    def __init__(self, dag, pmappings):
        dag.require_chain()
        if tuple(map(str, pmappings.einsum2pmappings)) != dag.nodes:
            raise ValueError("candidate order must exactly match the workload chain")
        if set(map(str, pmappings.einsums_with_pmappings_generated)) != set(dag.nodes):
            raise ValueError("all Einsums must have generated candidate groups")
        self.dag = dag
        self._pmappings = copy_candidate_payload(pmappings)
        self._store = None
        self._partials = {}
        self._partial_metadata = {}
        self.groups = tuple(
            CandidateGroup(str(name), i, PhysicalInterface(group.compatibility),
                           len(group.mappings.data), tuple(group.mappings.data.columns))
            for name, groups in self._pmappings.einsum2pmappings.items()
            for i, group in enumerate(groups)
        )
        if any(not self._pmappings.einsum2pmappings[n] for n in dag.nodes):
            raise ValueError("all Einsums must have at least one candidate group")

    def groups_for(self, subgraph):
        """Read metadata for source operators or explicitly saved prefixes."""
        nodes = tuple(subgraph)
        if len(nodes) == 1 and nodes[0] in self.dag.nodes:
            return tuple(group for group in self.groups if group.einsum == nodes[0])
        if nodes not in self._partials:
            raise ValueError("no saved intermediate state for this subgraph")
        return self._partial_metadata[nodes]

    def _candidate_store(self):
        if self._store is None:
            from .ffm_adapter import prepare_candidates
            self._store = prepare_candidates(self._pmappings)
        return self._store

    def start(self):
        return self._candidate_store().start()

    def advance(self, state, next_einsum=None):
        return self._candidate_store().advance(state, next_einsum)

    def finalize(self, state):
        return self._candidate_store().finalize(state)

    def save_partial(self, state):
        from accelforge.mapper.FFM._join_pmappings.partial_state import snapshot
        self._candidate_store().context.require_same(state.context)
        if state.processed not in self.dag.prefixes():
            raise ValueError('only reference-order prefixes can be saved')
        checkpoint = snapshot(state)
        metadata = tuple(IntermediateGroup(state.processed, i, PhysicalInterface(g.compatibility),
                                          len(g.mappings.data), tuple(g.mappings.data.columns))
                         for i, g in enumerate(checkpoint._state.left))
        self._partials[state.processed] = checkpoint
        self._partial_metadata[state.processed] = metadata

    def resume_partial(self, subgraph):
        from accelforge.mapper.FFM._join_pmappings.partial_state import resume
        return resume(self._partials[tuple(subgraph)], self._candidate_store().context)

    @property
    def saved_prefixes(self):
        return tuple(self._partials)

    def materialize(self):
        """Give the mutating FFM join its own complete snapshot."""
        return copy_candidate_payload(self._pmappings)
