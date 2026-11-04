"""Architecture-bound, lossless storage of original FFM candidate groups."""
from dataclasses import dataclass
from copy import deepcopy

from .physical_traits import PhysicalInterface


@dataclass(frozen=True)
class CandidateGroup:
    einsum: str
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
        self._pmappings = deepcopy(pmappings)
        self.groups = tuple(
            CandidateGroup(str(name), i, PhysicalInterface(group.compatibility),
                           len(group.mappings.data), tuple(group.mappings.data.columns))
            for name, groups in self._pmappings.einsum2pmappings.items()
            for i, group in enumerate(groups)
        )
        if any(not self._pmappings.einsum2pmappings[n] for n in dag.nodes):
            raise ValueError("all Einsums must have at least one candidate group")

    def groups_for(self, subgraph):
        """Expose single-operator entries only; no intermediate joins are cached."""
        nodes = tuple(subgraph)
        if len(nodes) != 1 or nodes[0] not in self.dag.nodes:
            raise ValueError("only single-Einsum subgraphs have memo entries")
        return tuple(group for group in self.groups if group.einsum == nodes[0])

    def materialize(self):
        """Give the mutating FFM join its own complete snapshot."""
        return deepcopy(self._pmappings)
