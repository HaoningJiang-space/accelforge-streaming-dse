"""Measure observed FFM state overlap before building another search engine.

All catalogs are generated independently, before Join mutates them. Signatures
are diagnostic projections, never authorization for pruning or substitution.
"""
import argparse
from collections import Counter
import copy
from dataclasses import fields, is_dataclass
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
import platform
import time

import numpy as np
import sympy

from accelforge.frontend.mapping import Loop, MappingNode, Reservation, TensorHolder, TilePattern
from research.graph_coopt.workload_dag import WorkloadDAG
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build


KINDS = ('template', 'resolved_compatibility', 'observed_boundary', 'full_local_mapping', 'row_payload')


def encode(value):
    """Typed, deterministic diagnostic encoding; unknown values are rejected."""
    if value is None:
        return ['none']
    if isinstance(value, Enum):
        return ['enum', type(value).__module__ + '.' + type(value).__qualname__, value.name]
    if isinstance(value, np.generic):
        if value.dtype.hasobject:
            raise TypeError('object scalar is unsupported')
        return ['numpy', value.dtype.str, value.tobytes().hex()]
    if isinstance(value, bool):
        return ['bool', value]
    if isinstance(value, int):
        return ['int', str(value)]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('nonfinite value is unsupported')
        return ['float', value.hex()]
    if isinstance(value, str):
        return ['str', value]
    if isinstance(value, sympy.Basic):
        return ['sympy', sympy.srepr(value)]
    if isinstance(value, dict):
        items = [[encode(k), encode(v)] for k, v in value.items()]
        return ['dict', sorted(items, key=lambda x: json.dumps(x[0], sort_keys=True))]
    if isinstance(value, (set, frozenset)):
        return ['set', sorted((encode(v) for v in value), key=lambda x: json.dumps(x, sort_keys=True))]
    if isinstance(value, (list, tuple)):
        return ['sequence', [encode(v) for v in value]]
    if is_dataclass(value):
        return [type(value).__module__ + '.' + type(value).__qualname__,
                [[f.name, encode(getattr(value, f.name))] for f in fields(value)]]
    raise TypeError(f'unsupported signature value: {type(value).__name__}')


def digest(document):
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def resolve(value, row, einsum):
    name = value.name if isinstance(value, sympy.Symbol) else value
    if isinstance(name, str):
        for col in (name, f'{einsum}<SEP>{name}'):
            if col in row:
                return row[col]
        raise ValueError(f'missing numeric tile column: {name}')
    return value


def resolved_compatibility(value, row, einsum):
    """Include all dataclass fields, even ones ignored by Compatibility.__eq__."""
    if isinstance(value, TilePattern):
        return ['TilePattern', [[f.name, encode(resolve(getattr(value, f.name), row, einsum))]
                                for f in fields(value)]]
    if is_dataclass(value):
        return [type(value).__qualname__, [[f.name, resolved_compatibility(getattr(value, f.name), row, einsum)]
                                          for f in fields(value)]]
    if isinstance(value, (set, frozenset)):
        return ['set', sorted((resolved_compatibility(v, row, einsum) for v in value),
                              key=lambda x: json.dumps(x, sort_keys=True))]
    if isinstance(value, (list, tuple)):
        return ['sequence', [resolved_compatibility(v, row, einsum) for v in value]]
    return encode(value)


def instantiate(template, row, einsum):
    """Resolve flat perfect-tiling sources, retaining unit loops and labels."""
    mapping = copy.deepcopy(template)
    if any(hasattr(n, 'nodes') for n in mapping.nodes):
        raise ValueError('nested local source is unsupported')
    for node in mapping.nodes:
        if isinstance(node, Loop):
            for attr in ('tile_shape', 'initial_tile_shape'):
                value = resolve(getattr(node, attr), row, einsum)
                if value is not None:
                    if int(value) != value or value <= 0:
                        raise ValueError('positive integer tile required')
                    value = int(value)
                setattr(node, attr, value)
            if node.initial_tile_shape not in (None, node.tile_shape):
                raise ValueError('imperfect tiling is unsupported')
            # Derived iteration metadata is recomputed from bounds and tiles;
            # symbolic variable names are not a physical mapping decision.
            node._calculated_n_iterations = None
    return mapping


def node_document(node, erase_tiles=False):
    if not isinstance(node, MappingNode):
        raise TypeError('expected a MappingNode')
    public = {}
    for name in type(node).model_fields:
        if name == 'component_object':
            continue  # evaluated hardware context is not a physical interface
        value = getattr(node, name)
        public[name] = '*tile*' if erase_tiles and isinstance(node, Loop) and name in (
            'tile_shape', 'initial_tile_shape') else encode(value)
    # Include ALL private fields (unknown functions/objects fail closed), except
    # the explicitly derived iteration cache. Extra public fields also matter.
    private = {k: encode(v) for k, v in (node.__pydantic_private__ or {}).items()
               if k != '_calculated_n_iterations'}
    extra = encode(node.__pydantic_extra__ or {})
    return dict(type=type(node).__module__ + '.' + type(node).__qualname__,
                fields=public, private=private, extra=extra)


def local_document(mapping, erase_tiles=False):
    return dict(type=type(mapping).__qualname__,
                private=encode(mapping.__pydantic_private__ or {}),
                extra=encode(mapping.__pydantic_extra__ or {}),
                nodes=[node_document(n, erase_tiles) for n in mapping.nodes])


def boundary_document(mapping, boundary_tensors, compatibility):
    """Observed copy scope, not a sufficient future interface or lifetime proof."""
    relevant = []
    for i, node in enumerate(mapping.nodes):
        names = (node.tensors if isinstance(node, TensorHolder) else
                 node.purposes if isinstance(node, Reservation) else ())
        if set(names) & set(boundary_tensors):
            relevant.append(i)
    last = max(relevant, default=-1)
    nodes = [[i, node_document(n)] for i, n in enumerate(mapping.nodes)
             if i in relevant or isinstance(n, Loop) and (i < last or n._fused)]
    return dict(tensors=sorted(boundary_tensors), copies_and_loop_prefix=nodes,
                compatibility=compatibility, future_equivalence_proven=False)


def histogram(keys):
    counts = Counter(keys)
    sizes = Counter(counts.values())
    return dict(unique=len(counts), singleton_groups=sum(n == 1 for n in counts.values()),
                max_group_size=max(counts.values(), default=0),
                group_size_histogram={str(k): v for k, v in sorted(sizes.items())})


def analyze_candidates(pmappings):
    """Read only; never concatenate groups or delete a row."""
    dag = WorkloadDAG.from_workload(pmappings.spec.workload)
    dag.require_chain()
    catalogs, summaries = {}, {}
    for einsum, groups in pmappings.einsum2pmappings.items():
        entries, unsupported = [], []
        boundary = {t for a, b, t in dag.edges if str(einsum) in (a, b)}
        for gi, group in enumerate(groups):
            frame = group.mappings.data
            # Column-wise access avoids mixed Series conversion, including loss
            # of uint64 Membership bits or large exact resource integers.
            for ri in range(len(frame)):
                row = {c: frame[c].iloc[ri] for c in frame}
                source_col = f'{einsum}<SEP>mapping'
                try:
                    source = pmappings.pmapping_objects[einsum][row[source_col]]
                    mapping = instantiate(source, row, einsum)
                    compat = resolved_compatibility(group.compatibility, row, einsum)
                    full = local_document(mapping)
                    payload = [[str(c), str(frame[c].dtype), encode(row[c])]
                               for c in sorted(frame) if c != source_col]
                    keys = dict(template=digest(local_document(mapping, True)),
                                resolved_compatibility=digest(compat),
                                observed_boundary=digest(boundary_document(mapping, boundary, compat)),
                                full_local_mapping=digest(full),
                                row_payload=digest([full, compat, encode(group.tensors), payload]))
                    cost_resource = [[str(c), str(frame[c].dtype), encode(row[c])]
                                     for c in sorted(frame) if c in ('Total<SEP>energy', 'Total<SEP>latency')
                                     or c.startswith('reservation_bits<SEP>')]
                    entries.append(dict(group_index=gi, row_position=ri,
                                        source_id=str(row[source_col]), signatures=keys,
                                        cost_resource=digest(cost_resource)))
                except (TypeError, ValueError, KeyError, OverflowError) as error:
                    unsupported.append(dict(group_index=gi, row_position=ri, reason=str(error)))
        catalogs[str(einsum)] = entries
        costs_by_boundary = {}
        for entry in entries:
            costs_by_boundary.setdefault(entry['signatures']['observed_boundary'], set()).add(entry['cost_resource'])
        summaries[str(einsum)] = dict(
            candidate_rows=sum(len(g.mappings.data) for g in groups),
            ffm_groups=len(groups), analyzed_rows=len(entries), unsupported=unsupported,
            boundary_tensors=sorted(boundary),
            observations={kind: histogram(e['signatures'][kind] for e in entries) for kind in KINDS},
            boundary_groups_with_distinct_cost_or_resource=len([v for v in costs_by_boundary.values() if len(v) > 1]),
            certified_semantic_merges=0)
    return dict(dag_nodes=dag.nodes, dag_edges=dag.edges, einsums=summaries), catalogs


def compare_catalogs(source, target):
    """Directed overlap; no new target candidate is generated or validated here."""
    result = {}
    for einsum in target:
        rows = target[einsum]
        result[einsum] = {}
        for kind in KINDS:
            source_keys = {r['signatures'][kind] for r in source[einsum]}
            target_keys = {r['signatures'][kind] for r in rows}
            result[einsum][kind] = dict(target_rows=len(rows),
                covered_rows=sum(r['signatures'][kind] in source_keys for r in rows),
                target_unique=len(target_keys), shared_unique=len(source_keys & target_keys))
        full_with_cost = {(r['signatures']['full_local_mapping'], r['cost_resource']) for r in source[einsum]}
        result[einsum]['full_mapping_and_cost_resource'] = dict(target_rows=len(rows), covered_rows=sum(
            (r['signatures']['full_local_mapping'], r['cost_resource']) in full_with_cost for r in rows))
    return result


def run_case(n, extent, shapes, capacities):
    case = common.Case('matmuls', 'nvdla', (n, extent, extent))
    runs, catalogs = [], {}
    for shape in shapes:
        for capacity in capacities:
            common.clear_switches()
            spec = build(case, shape, capacity, common.RU)
            start = time.perf_counter()
            pmappings = common.make_pmappings(spec, print_number_of_pmappings=False)
            generated = time.perf_counter() - start
            start = time.perf_counter()
            summary, catalog = analyze_candidates(pmappings)
            analyzed = time.perf_counter() - start
            label = f'{shape[0]}x{shape[1]}:{capacity}B'
            catalogs[label] = catalog
            runs.append(dict(architecture=label, shape=shape, capacity_bits=capacity * 8,
                             generation_s=generated, analysis_s=analyzed, **summary))
    overlaps = [dict(source=a, target=b, einsums=compare_catalogs(catalogs[a], catalogs[b]))
                for a in catalogs for b in catalogs if a != b]
    unions = {}
    for einsum in next(iter(catalogs.values())):
        all_rows = [r for c in catalogs.values() for r in c[einsum]]
        unions[einsum] = dict(analyzed_row_occurrences=len(all_rows),
                             observations={kind: histogram(r['signatures'][kind] for r in all_rows)
                                           for kind in KINDS})
    return dict(workload=str(case), runs=runs, overlaps=overlaps, union=unions, catalogs=catalogs)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--extent', type=int, default=32)
    p.add_argument('--shapes', default='8x32,16x16,32x8')
    p.add_argument('--capacities-bytes', default='2048,4096')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    shapes = [tuple(map(int, s.split('x'))) for s in args.shapes.split(',')]
    capacities = sorted(set(map(int, args.capacities_bytes.split(','))))
    if args.extent <= 0 or not shapes or len(set(shapes)) != len(shapes) or not capacities:
        raise ValueError('positive extent, distinct shapes and capacities required')
    if any(len(s) != 2 or min(s) <= 0 for s in shapes) or min(capacities) <= 0:
        raise ValueError('positive two-dimensional shapes and byte capacities required')
    common.af.set_n_parallel_jobs(1)
    report = dict(scope='Post-generation diagnostic overlap only; no safe merging, no candidate removal, no new search speed.',
                  signature_kinds=KINDS, platform=platform.platform(), python=platform.python_version(),
                  gates=dict(G1='observed clustering measured; semantic merging uncertified',
                             G2='unchanged FFM composition, see fixed-architecture audit',
                             G3='cross-architecture signature overlap only; avoided search work is zero'),
                  results=[run_case(n, args.extent, shapes, capacities) for n in (2, 3)])
    paths = [Path(__file__), Path(__file__).with_name('physical_traits.py'),
             common.ROOT / 'research/tracking_audit/shape_capacity_audit.py',
             common.ROOT / 'accelforge/mapper/FFM/_join_pmappings/compatibility.py']
    report['source_sha256'] = {str(f.relative_to(common.ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
                               for f in paths}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({r['workload']: r['union'] for r in report['results']}, indent=2))


if __name__ == '__main__':
    main()
