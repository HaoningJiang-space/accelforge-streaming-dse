"""Read-only graph-support certificates over complete raw template catalogs.

This is necessary-condition propagation, not a numeric Fusion implementation.
Unknown interfaces are wildcards. Hardware IDs are never joined across chips.
The caller must supply every raw family of each mandatory graph operator.
"""


def propagate(catalogs, edges, interfaces):
    """Reach arc-consistency fixpoint, retaining a trace of unsupported families.

    catalogs[(hardware_id, operator)] is the complete finite family-ID set.
    interfaces[(hardware_id, operator, family, neighbor)] is either a superset
    of possible boundary keys or None (unknown). The keys must be necessary
    equality conditions for the chosen edge. No dominance/fallback is applied.
    """
    edges = tuple(edges)
    if len(set(edges)) != len(edges) or any(a == b for a, b in edges):
        raise ValueError('distinct directed edges between different operators required')
    operators = {op for _, op in catalogs}
    edge_operators = {x for edge in edges for x in edge}
    hardware = {h for h, _ in catalogs}
    if (not hardware or not operators or not edge_operators.issubset(operators)
            or any((h, op) not in catalogs for h in hardware for op in operators)):
        raise ValueError('complete catalog for every hardware and mandatory operator required')
    current = {key: frozenset(values) for key, values in catalogs.items()}
    directed = tuple(pair for a, b in edges for pair in ((a, b), (b, a)))
    for h in hardware:
        for op, peer in directed:
            for family in current[h, op]:
                key = (h, op, family, peer)
                if key not in interfaces:
                    raise ValueError(f'interface absent (use None for unknown): {key}')
                value = interfaces[key]
                if value is not None and not isinstance(value, frozenset):
                    raise TypeError('interface must be a frozenset or unknown None')
    removed = []
    rounds = 0
    while True:
        rounds += 1
        changed = False
        updated = dict(current)
        # Simultaneous rounds make every deletion certificate depend only on
        # the immutable previous round, never an unrecorded traversal order.
        for h in sorted(hardware):
            for op, peer in directed:
                for family in sorted(current[h, op]):
                    left = interfaces[h, op, family, peer]
                    peers = current[h, peer]
                    supported = False
                    for other in peers:
                        right = interfaces[h, peer, other, op]
                        if left is None or right is None or left & right:
                            supported = True
                            break
                    if not supported and family in updated[h, op]:
                        updated[h, op] = updated[h, op] - {family}
                        removed.append(dict(round=rounds, hardware=h, operator=op,
                            family=family, missing_neighbor=peer,
                            neighbor_families=sorted(peers)))
                        changed = True
        current = updated
        if not changed:
            break
    surviving_hardware = frozenset(h for h in hardware
        if all(current[h, op] for op in operators))
    return current, dict(rounds=rounds, removed=removed,
        surviving_hardware=sorted(surviving_hardware),
        removed_hardware=sorted(hardware - surviving_hardware),
        input_family_instances=sum(map(len, catalogs.values())),
        retained_family_instances=sum(len(v) for (h, _), v in current.items()
                                      if h in surviving_hardware),
        numeric_expansion_calls=0, native_join_calls=0,
        actual_skipped_jobs=0, pruning_enabled=False,
        soundness_scope='necessary boundary equality only; no sufficiency or policy-preserving deletion claim')
