"""Conservative producer/consumer graph extraction; not a fusion legality test."""
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkloadDAG:
    nodes: tuple[str, ...]
    # One entry per producer, consumer and tensor; graph order is preserved.
    edges: tuple[tuple[str, str, str], ...]

    @classmethod
    def from_workload(cls, workload):
        einsums = list(workload.einsums)
        names = tuple(str(e.name) for e in einsums)
        if not names or len(set(names)) != len(names):
            raise ValueError("workload must have distinct, nonempty Einsum names")
        producers = {}
        for e in einsums:
            for tensor in e.output_tensor_names:
                tensor = str(tensor)
                if tensor in producers:
                    raise ValueError(f"multiple producers for {tensor}: unsupported")
                producers[tensor] = str(e.name)
        index = {name: i for i, name in enumerate(names)}
        edges = []
        for e in einsums:
            consumer = str(e.name)
            for tensor in sorted(map(str, e.input_tensor_names)):
                producer = producers.get(tensor)
                if producer is None:
                    continue
                if producer == consumer or index[producer] >= index[consumer]:
                    raise ValueError("self-dependence or non-topological Einsum order")
                edges.append((producer, consumer, tensor))
        return cls(names, tuple(edges))

    def require_chain(self):
        """Limit the prototype to actual contiguous producer-consumer chains."""
        pairs = {(a, b) for a, b, _ in self.edges}
        expected = set(zip(self.nodes, self.nodes[1:]))
        if pairs != expected:
            raise ValueError("only sequential chains without extra dependencies are supported")

    def prefixes(self):
        return tuple(self.nodes[:i] for i in range(1, len(self.nodes) + 1))
