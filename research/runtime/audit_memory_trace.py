"""Count dense GEMM memory transfers from serialized loops and affine addresses."""

import argparse
from ast import literal_eval
from collections import Counter
from itertools import product
import hashlib
import json
from math import prod
from pathlib import Path


MEMORIES = ("MainMemory", "GlobalBuffer", "Register", "MAC")
SPATIAL_REUSE = {"reuse_input": 0, "reuse_output": 2}


def paths(nodes, prefix=()):
    for index, node in enumerate(nodes):
        kind = node["type"]
        if kind == "Sequential":
            if index != len(nodes) - 1:
                raise ValueError("sequential continuation")
            for branch in node["nodes"]:
                yield from paths([branch], prefix)
            return
        if kind == "Nested":
            yield from paths(node["nodes"] + nodes[index + 1:], prefix)
            return
        if kind == "Compute":
            if index != len(nodes) - 1 or node["component"] != "MAC":
                raise ValueError("unsupported compute")
            yield node["einsum"], prefix
            return
        if kind not in {"Storage", "Reservation", "Temporal", "Spatial"}:
            raise ValueError(f"unsupported node {kind}")
        if node.get("persistent") not in (None, "False", False):
            raise ValueError("persistent storage")
        prefix += (node,)
    raise ValueError("missing compute leaf")


def link_words(nodes, bounds, projection, role, parent, child, addresses=False):
    """Count distinct requested words per transfer epoch and permitted multicast."""
    axis_loops = {axis: [] for axis in bounds}
    for pos, node in enumerate(nodes[:child]):
        if node["type"] not in {"Temporal", "Spatial"}:
            continue
        rank = node["rank_variable"]
        if node["initial_tile_shape"] is not None:
            raise ValueError("irregular first tile")
        width = literal_eval(node["tile_shape"])
        if not isinstance(width, int) or width < 1:
            raise ValueError("noninteger or nonpositive tile")
        merge = (
            node["type"] == "Spatial"
            and parent < pos
            and rank not in projection
            and SPATIAL_REUSE[node["name"]] == role
        )
        axis_loops[rank].append((width, merge))
    if child == len(nodes):
        for rank in bounds:
            axis_loops[rank].append((1, False))

    def cardinality(extent, loops, projected):
        if not loops:
            return extent if projected else 1
        (tile, merge), *rest = loops
        full, tail = divmod(extent, tile)
        if merge:
            # All lanes request the same address. A tail lane is a subset of
            # the request made by a full lane at the same inner iteration.
            return cardinality(min(extent, tile), rest, projected)
        return (full * cardinality(tile, rest, projected) if full else 0) + (
            cardinality(tail, rest, projected) if tail else 0
        )

    def requests(start, extent, loops, projected):
        if not loops:
            for address in range(start, start + extent) if projected else (None,):
                yield (), address
            return
        (tile, merge), *rest = loops
        for lane, offset in enumerate(range(0, extent, tile)):
            for epoch, address in requests(
                start + offset, min(tile, extent - offset), rest, projected
            ):
                yield ((None if merge else lane), *epoch), address

    if addresses:
        dimensions = [
            tuple(requests(0, n, axis_loops[r], r in projection)) for r, n in bounds.items()
        ]
        seen, transfers, first = set(), set(), 0
        for request in product(*dimensions):
            if request in transfers:
                continue
            transfers.add(request)
            address = tuple(word for _, word in request)
            if address not in seen:
                seen.add(address)
                first += 1
        return len(transfers), first
    return (
        prod(cardinality(n, axis_loops[r], r in projection) for r, n in bounds.items()),
        prod(bounds[rank] for rank in projection),
    )


def count(mapping, rows, width, stages, addresses=False):
    counts = Counter()
    seen = []
    for operator, nodes in paths(mapping["nodes"]):
        i = len(seen)
        if operator != f"Matmul{i}":
            raise ValueError(f"unexpected operator order at {operator}")
        seen.append(operator)
        k, n = f"n{i}", f"n{i+1}"
        bounds = {"m": rows, k: width, n: width}
        for role, (tensor, projection) in enumerate(
            ((f"T{i}", ("m", k)), (f"W{i}", (k, n)), (f"T{i+1}", ("m", n)))
        ):
            # Fanout belongs below shared GB and above private Register for
            # every tensor. Moving it across another tensor's placement does
            # not change this tensor's projected addresses.
            events = [node for node in nodes if
                      node["type"] in {"Temporal", "Spatial"} or
                      (node["type"] == "Storage" and tensor in literal_eval(node["tensors"]))]
            spatial = [node for node in events if node["type"] == "Spatial"]
            for node in spatial:
                start = events.index(node)
                crossed = [
                    pos for pos, later in enumerate(events[start + 1:], start + 1)
                    if later["type"] == "Storage" and later["component"] == "GlobalBuffer"
                ]
                if crossed:
                    end = crossed[-1]
                    if any(later["type"] == "Temporal" and
                           later["rank_variable"] == node["rank_variable"]
                           for later in events[start + 1:end]):
                        raise ValueError("noncontiguous fanout tile")
                    events.insert(end, events.pop(start))
            holders = [(pos, node["component"]) for pos, node in enumerate(events)
                       if node["type"] == "Storage"]
            holders.append((len(events), "MAC"))
            if len(holders) < 2 or any(
                MEMORIES.index(a) >= MEMORIES.index(b)
                for (_, a), (_, b) in zip(holders, holders[1:])
            ):
                raise ValueError(f"invalid hierarchy for {operator}/{tensor}")

            def add(memory, action, words):
                if memory != "MAC" and words:
                    counts[f"{operator}<SEP>action<SEP>{memory}<SEP>{tensor}<SEP>{action}"] += 8 * words

            for (parent, upper), (child, lower) in zip(holders, holders[1:]):
                words, first = link_words(events, bounds, projection, role, parent, child, addresses)
                if role == 2:
                    # Output entries start at zero. At each link every first
                    # coordinate update initializes the destination. Subsequent
                    # updates fetch a partial sum before returning it.
                    prior = words - first
                    if prior < 0:
                        raise ValueError("incomplete output projection")
                    add(upper, "read", prior)
                    add(lower, "write", prior)
                    add(lower, "read", words)
                    add(upper, "write", words)
                else:
                    add(upper, "read", words)
                    add(lower, "write", words)
        counts[f"{operator}<SEP>action<SEP>MAC<SEP>None<SEP>compute"] = prod(bounds.values())
    if len(seen) != stages:
        raise ValueError(f"expected {stages} stages, got {len(seen)}")
    return counts


def compare(witness, rows, width, stages):
    actual = count(witness["mapping"], rows, width, stages)
    reference = witness["actions"]
    return {
        key: [actual[key], reference.get(key, 0)]
        for key in sorted(set(actual) | set(reference))
        if actual[key] != reference.get(key, 0)
    }


def audit(source):
    raw = source.read_bytes()
    report = json.loads(raw)
    case = report["case"]
    if (case["workload"], case["arch"]) != ("matmuls", "nvdla"):
        raise ValueError("dense 8-bit NVDLA GEMM chains only")
    stages, rows, width = case["params"]
    passed = 0
    differences = []
    for entry in report.get("points", report.get("entries", [])):
        candidates = [(None, entry["witness"])] if "witness" in entry else [
            (index, row["witness"]) for index, row in enumerate(entry["candidates"])
            if row["status"] == "verified"
        ]
        for index, witness in candidates:
            delta = compare(witness, rows, width, stages)
            if delta:
                differences.append(dict(architecture=entry["architecture"], candidate_index=index,
                                        mapping_id=witness["mapping_id"], differences_bits=delta))
            else:
                passed += 1
    if not passed and not differences:
        raise ValueError("no action-annotated mappings")
    return dict(source_sha256=hashlib.sha256(raw).hexdigest(), passed=passed,
                mismatches=len(differences), differences=differences)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {source.as_posix(): audit(source) for source in args.sources}
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({p: (r["passed"], r["mismatches"]) for p, r in result.items()}))


if __name__ == "__main__":
    main()
