from research.runtime.audit_memory_trace import count


def storage(component, *tensors):
    return dict(type="Storage", component=component, tensors=repr(list(tensors)))


def loop(kind, rank, tile, **fields):
    return dict(type=kind, rank_variable=rank, tile_shape=str(tile),
                initial_tile_shape=None, **fields)


def matmul(i):
    k, n = f"n{i}", f"n{i+1}"
    return dict(type="Nested", nodes=[
        storage("MainMemory", f"W{i}"),
        loop("Temporal", k, 3),
        storage("GlobalBuffer", f"W{i}"),
        loop("Spatial", k, 1, name="reuse_output"),
        loop("Spatial", n, 1, name="reuse_input"),
        storage("Register", f"W{i}"),
        loop("Temporal", "m", 1),
        dict(type="Compute", component="MAC", einsum=f"Matmul{i}"),
    ])


def test_fused_tail_first_read_once_per_output_address():
    mapping = dict(nodes=[
        storage("MainMemory", "T0"),
        storage("GlobalBuffer", "T0", "T1", "T2"),
        dict(type="Sequential", nodes=[matmul(0), matmul(1)]),
    ])
    counts = count(mapping, 2, 5, 2, addresses=True)
    assert count(mapping, 2, 5, 2) == counts
    # Two disjoint reduction tiles update the same 2x5 output.
    assert counts["Matmul0<SEP>action<SEP>GlobalBuffer<SEP>T1<SEP>write"] == 2 * 2 * 5 * 8
    assert counts["Matmul0<SEP>action<SEP>GlobalBuffer<SEP>T1<SEP>read"] == 2 * 5 * 8
    assert counts["Matmul1<SEP>action<SEP>GlobalBuffer<SEP>T1<SEP>read"] == 2 * 5 * 8
    assert counts["Matmul0<SEP>action<SEP>MainMemory<SEP>T1<SEP>write"] == 0
    assert counts["Matmul1<SEP>action<SEP>MainMemory<SEP>T1<SEP>read"] == 0
    # Private weight cells fill once per lane, then read once per MAC.
    assert counts["Matmul0<SEP>action<SEP>Register<SEP>W0<SEP>write"] == 5 * 5 * 8
    assert counts["Matmul0<SEP>action<SEP>Register<SEP>W0<SEP>read"] == 2 * 5 * 5 * 8
