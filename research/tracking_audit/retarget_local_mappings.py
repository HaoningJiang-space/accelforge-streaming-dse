"""Measure cross-shape local structure coverage; construct rebinding witnesses.

This is a retrospective coverage experiment, not a faster search algorithm.
Target winners select which source structures to inspect; binding alternatives
are enumerated using only source loops and target fanouts, without target tiles.
All nonbinding decisions, including storage and fused loops, remain frozen.
Storage-retile mode changes memory tile extents, but keeps storage positions and
fused-loop values. Missing a chosen winner does not imply missing every tied
optimum. Catalogs are post-pruning; coverage is not a Mapspace completeness test.
"""
import argparse
import copy
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import time

import sympy
from accelforge.frontend.mapping import Loop, Mapping, Spatial, Temporal, TensorHolder, Reservation
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import (
    build, mapping_structure, rows_fitting, save, validate_pick,
)


def instantiate(template, row, einsum):
    """Keep unit loops: removing them loses latent rebinding locations."""
    result = copy.deepcopy(template)
    for node in result.nodes:
        if not isinstance(node, Loop):
            continue
        for attr in ('tile_shape', 'initial_tile_shape'):
            value = getattr(node, attr)
            if isinstance(value, sympy.Symbol):
                value = value.name
            if isinstance(value, str):
                value = row[f'{einsum}<SEP>{value}']
            if value is not None:
                if int(value) != value or value <= 0:
                    raise ValueError('audit supports positive integer perfect tiles only')
                value = int(value)
            setattr(node, attr, value)
        node.calculated_n_iterations = None
    return result


MODES = ('physical', 'spatial_only', 'factor_split', 'storage_retile', 'template')


def binding_slots(mapping, allow_storage_retile=False):
    """Temporal tiles that divide a pure, unfused Temporal/Spatial loop band.

    In NVDLA, T n=128 -> S n=1 means 128 spatial iterations. Rebinding to
    64 changes the T tile. Do not cross storage/reservation/fusion boundaries.
    """
    slots = {}
    for i, node in enumerate(mapping.nodes):
        if not isinstance(node, Spatial) or node._fused:
            continue
        for j in range(i-1, -1, -1):
            parent = mapping.nodes[j]
            if allow_storage_retile and isinstance(parent, (TensorHolder, Reservation)):
                continue
            if not isinstance(parent, Loop) or parent._fused:
                break
            if parent.rank_variable == node.rank_variable:
                if isinstance(parent, Temporal):
                    slots[j] = i
                break
    return slots


def signature(mapping, mode='physical'):
    if mode not in MODES:
        raise ValueError(mode)
    structure = mapping_structure(mapping)
    # Derived component objects and symbol names are deliberately excluded.
    # Copy and fusion labels are retained alongside every actual node decision.
    slots = binding_slots(mapping, allow_storage_retile=mode == 'storage_retile')
    for i, (node, item) in enumerate(zip(mapping.nodes, structure['nodes'])):
        item['fused'] = getattr(node, '_fused', None)
        item['backing'] = sorted(getattr(node, '_backing', ()))
        if ((mode == 'spatial_only' and isinstance(node, Spatial))
                or (mode in ('factor_split', 'storage_retile') and i in slots)
                or (mode == 'template' and isinstance(node, Loop))):
            item['tile_shape'] = '*binding*'
            item['initial_tile_shape'] = '*binding*'
    return json.dumps(structure, sort_keys=True, separators=(',', ':'))


def fingerprint(value):
    return hashlib.sha256(value.encode()).hexdigest()


def rebindings(mapping, bounds, shape, allow_storage_retile=False):
    """Enumerate perfect factor splits; no cost/policy pruning or target oracle.

    This establishes physical loop feasibility, not target min_usage policy
    membership. Witnesses also match an independently searched target candidate.
    """
    limits = dict(zip(('reuse_input', 'reuse_output'), shape))
    slots = binding_slots(mapping, allow_storage_retile)
    result = copy.deepcopy(mapping)

    def walk(i, sizes, usage):
        if i == len(result.nodes):
            yield copy.deepcopy(result)
            return
        node = result.nodes[i]
        if not isinstance(node, Loop):
            yield from walk(i+1, sizes, usage)
            return
        if not isinstance(node.rank_variable, str):
            raise ValueError('local audit requires single-rank loops')
        parent = sizes[node.rank_variable]
        if node.initial_tile_shape not in (None, node.tile_shape):
            raise ValueError('imperfect tiling is unsupported')
        if i in slots:
            spatial = result.nodes[slots[i]]
            if spatial.component != 'ArrayFanout' or spatial.name not in limits:
                raise ValueError('unsupported spatial component')
            # Both factors must divide; subsequent loop checks enforce the
            # remaining hierarchy and product of repeated spatial dimensions.
            choices = [int(d) for d in sympy.divisors(parent)
                       if d % spatial.tile_shape == 0
                       and d // spatial.tile_shape <= limits[spatial.name]]
        else:
            choices = [mapping.nodes[i].tile_shape]
        for tile in choices:
            if tile > parent or parent % tile:
                continue
            next_usage = dict(usage)
            if isinstance(node, Spatial):
                if node.component != 'ArrayFanout' or node.name not in limits:
                    raise ValueError('unsupported spatial component')
                next_usage[node.name] = next_usage.get(node.name, 1) * (parent // tile)
                if next_usage[node.name] > limits[node.name]:
                    continue
            node.tile_shape = tile
            node.initial_tile_shape = tile if mapping.nodes[i].initial_tile_shape is not None else None
            node.calculated_n_iterations = None
            yield from walk(i+1, {**sizes, node.rank_variable: tile}, next_usage)
    yield from walk(0, dict(bounds), {})


def run(case, shapes, capacities, output):
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    report = {'config': common.effective_config(case, shapes=shapes,
              capacities_bytes=capacities, workers=1),
              'scope': 'retrospective source-catalog coverage, not end-to-end speedup',
              'searches': [], 'coverage': [], 'witnesses': []}
    catalogs, winners, bounds_by_shape = {}, {}, {}
    for shape in shapes:
        label = 'x'.join(map(str, shape))
        spec = build(case, shape, max(capacities), common.RU)
        bounds = common.get_rank_variable_bounds_for_all_einsums(spec)
        bounds_by_shape[label] = bounds
        start = time.perf_counter()
        pm = common.make_pmappings(spec, print_number_of_pmappings=False)
        make_s = time.perf_counter() - start
        start = time.perf_counter()
        os.environ['AF_VARIABLE_RESOURCES'] = 'GlobalBuffer'
        try:
            result = common.join_pmappings(pm)
        finally:
            common.clear_switches()
        join_s = time.perf_counter() - start
        catalog = {}
        for einsum, groups in pm.einsum2pmappings.items():
            entries = []
            for group in groups:
                for _, row in group.mappings.data.iterrows():
                    template = pm.pmapping_objects[einsum][row[f'{einsum}<SEP>mapping']]
                    mapping = instantiate(template, row, einsum)
                    entries.append((mapping, {mode: signature(mapping, mode) for mode in MODES}))
            catalog[einsum] = entries
        catalogs[label] = catalog
        winners[label] = []
        for capacity in capacities:
            row = common.best_row(rows_fitting(result.data, capacity))
            validation = validate_pick(case, shape, capacity, row)
            parts = {}
            if row is not None:
                callback = row['Total<SEP>mapping']
                for einsum in callback.einsum_names:
                    part = instantiate(callback.row[f'{einsum}<SEP>mapping'], callback.row, einsum)
                    parts[einsum] = part
            winners[label].append((capacity, row, parts, validation))
        report['searches'].append({'shape': label, 'make_s': make_s, 'join_s': join_s,
            'local_rows': {e: len(v) for e,v in catalog.items()},
            'unique_structures': {e: {mode: len({v[1][mode] for v in entries})
                for mode in MODES} for e, entries in catalog.items()},
            'picks': [dict(capacity_bytes=c, **v) for c, _, _, v in winners[label]]})
        save(output, report)
    for source in catalogs:
        indexes = {e: {mode: {} for mode in MODES}
                   for e in catalogs[source]}
        for e, entries in catalogs[source].items():
            for mapping, signatures in entries:
                for mode, sig in signatures.items():
                    indexes[e][mode].setdefault(sig, mapping)
        for target, target_catalog in catalogs.items():
            for e, entries in target_catalog.items():
                counts = {mode: sum(sig[mode] in indexes[e][mode] for _, sig in entries)
                          for mode in indexes[e]}
                report['coverage'].append(dict(source=source, target=target, einsum=e,
                                                target_rows=len(entries), covered=counts))
            for mode, cap, row, parts, validation in (
                    (m, *w) for m in ('factor_split', 'storage_retile') for w in winners[target]):
                witness = dict(source=source, target=target, capacity_bytes=cap,
                               mode=mode, target_feasible=bool(parts), locals=[])
                rebound_parts = []
                for e, target_mapping in parts.items():
                    logical = signature(target_mapping, mode)
                    source_mapping = indexes[e][mode].get(logical)
                    item = {'einsum': e, 'covered': source_mapping is not None,
                            'logical_id': fingerprint(logical)}
                    if source_mapping is not None:
                        wanted = signature(target_mapping)
                        matched, count = None, 0
                        # Enumerate fully, so this count is not target-order dependent.
                        for candidate in rebindings(source_mapping, bounds_by_shape[target],
                                                    tuple(map(int, target.split('x'))),
                                                    allow_storage_retile=mode == 'storage_retile'):
                            count += 1
                            if signature(candidate) == wanted:
                                matched = candidate
                        item.update(alternatives=count, recovered=matched is not None,
                                    changed=signature(source_mapping) != wanted,
                                    source=mapping_structure(source_mapping),
                                    target=mapping_structure(target_mapping))
                        if matched is not None:
                            rebound_parts.append(matched)
                    witness['locals'].append(item)
                witness['all_recovered'] = bool(parts) and len(rebound_parts) == len(parts)
                if witness['all_recovered']:
                    mapping = Mapping._from_pmappings(rebound_parts, bounds_by_shape[target])
                    # Validate constructed mapping, not the target's callback.
                    transformed = row.copy()
                    transformed['Total<SEP>mapping'] = lambda m=mapping: copy.deepcopy(m)
                    witness['validation'] = validate_pick(case, tuple(map(int, target.split('x'))),
                                                         cap, transformed)
                report['witnesses'].append(witness)
                save(output, report)
    report['summary'] = {'cross_shape_witnesses': {mode: dict(Counter(
        'recovered' if w['all_recovered'] else 'not_recovered'
        for w in report['witnesses'] if w['source'] != w['target'] and w['mode'] == mode))
        for mode in ('factor_split', 'storage_retile')}}
    if any(w['target_feasible'] and not w['all_recovered'] for w in report['witnesses']
           if w['source'] == w['target']):
        raise AssertionError('identity transformation must recover every feasible source pick')
    save(output, report)
    print(json.dumps(report['summary']), flush=True)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workload', choices=('matmuls','attention'), default='matmuls')
    p.add_argument('--params', default='3,256,256')
    p.add_argument('--shapes', default='16x384,32x192,64x96')
    p.add_argument('--capacities-bytes', default='131072,135168,262144')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    run(common.Case.parse(args.workload, 'nvdla', args.params),
        [tuple(map(int, s.split('x'))) for s in args.shapes.split(',')],
        sorted(set(map(int, args.capacities_bytes.split(',')))), args.output)


if __name__ == '__main__':
    main()
