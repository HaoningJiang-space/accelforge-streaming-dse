"""RQ1: measure architecture/mapping coupling before designing a joint solver.

An exhaustive architecture grid with a complete per-architecture mapper is a
joint reference, not a quality-losing decoupled baseline. Here FFM is heuristic:
the reference is explicitly best returned by its current search contract.
Compare fixed-shape/reoptimized-mapping and frozen-mapping/reselected-shape
policies within equal-PE, equal-SRAM, equal-bandwidth strata. Never select free
extra SRAM or bandwidth across strata. No calibrated area model is assumed.
"""
import argparse
from dataclasses import asdict, dataclass
import copy
import hashlib
import itertools
import json
import math
from pathlib import Path
import platform
import time

import numpy as np

from accelforge.frontend.mapping import Loop, TensorHolder
from accelforge.mapper.FFM.generation_contract import effective_pareto_tolerance
from research.graph_coopt.workload_dag import WorkloadDAG
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, mapping_structure, validate_pick


RAW_GB = 'reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right'
DEFAULT_SHAPES = ((8, 32), (16, 16), (32, 8))


@dataclass(frozen=True)
class Point:
    px: int
    py: int
    capacity_bytes: int
    gb_latency_scale: float

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in (self.px, self.py, self.capacity_bytes)):
            raise ValueError('positive integer shape and byte capacity required')
        if not math.isfinite(self.gb_latency_scale) or self.gb_latency_scale <= 0:
            raise ValueError('positive finite bandwidth scale required')

    @property
    def shape(self):
        return self.px, self.py

    @property
    def key(self):
        return f'{self.px}x{self.py}_{self.capacity_bytes}B_gbscale{self.gb_latency_scale:g}'

    @property
    def budget(self):
        return self.px * self.py, self.capacity_bytes, self.gb_latency_scale


def make_spec(case, point, zero_fused_loops=False):
    spec = build(case, point.shape, point.capacity_bytes, common.RU, point.gb_latency_scale)
    if zero_fused_loops:
        spec.mapper.ffm.max_fused_loops = 0
    return spec


def graph_observations(mapping, dag):
    """Observed storage/loop decisions, not a physical lifetime proof."""
    intermediates = {t for _, _, t in dag.edges}
    declarations, loops, splits = [], [], []

    def walk(nodes, path=(), enclosing=()):
        prefix = list(enclosing)
        for i, node in enumerate(nodes):
            p = (*path, i)
            if isinstance(node, Loop):
                loop = dict(path=list(p), type=type(node).__name__,
                            rank=str(node.rank_variable), tile=int(node.tile_shape),
                            component=getattr(node, 'component', None),
                            dimension=getattr(node, 'name', None), fused=bool(node._fused))
                loops.append(loop)
                prefix.append(loop)
            if isinstance(node, TensorHolder):
                for tensor in sorted(set(map(str, node.tensors)) & intermediates):
                    declarations.append(dict(tensor=tensor, component=node.component,
                                             persistent=bool(node.persistent), path=list(p),
                                             enclosing_loops=list(prefix)))
            if hasattr(node, 'nodes'):
                splits.append(dict(path=list(p), type=type(node).__name__))
                walk(node.nodes, p, prefix)
    walk(mapping.nodes)
    components = {t: sorted({d['component'] for d in declarations if d['tensor'] == t})
                  for t in sorted(intermediates)}
    document = dict(intermediate_storage_declarations=declarations, loop_decisions=loops,
                    nesting=splits, intermediate_storage_components=components)
    blob = json.dumps(document, sort_keys=True, separators=(',', ':'))
    return dict(**document, signature=hashlib.sha256(blob.encode()).hexdigest(),
                lifetime_sufficiency_proven=False)


def evaluate_frozen(case, point, mapping, anchor):
    """Re-evaluate fixed decisions; do not retile, rebind, or assume membership."""
    for use in anchor['spatial']:
        if any(u > limit for u, limit in zip(use['used'], point.shape)):
            return dict(feasible=False, reason='spatial_binding_does_not_fit')
    if anchor['gb_bits'] > point.capacity_bytes * 8:
        return dict(feasible=False, reason='exact_globalbuffer_capacity_does_not_fit')
    spec = make_spec(case, point)
    spec.model.metrics = common.RU
    spec.mapping = copy.deepcopy(mapping)
    evaluated = common.evaluate_mapping(spec).data
    if len(evaluated) != 1:
        raise ValueError('expected one evaluated fixed mapping')
    for column in evaluated:
        if column.startswith('reservation_bits<SEP>'):
            resource = column.split('<SEP>')[1]
            value = evaluated[column].iloc[0]
            capacity = evaluated[f'capacity_reference_bits<SEP>{resource}'].iloc[0]
            if value != int(value) or not 0 <= value <= capacity:
                return dict(feasible=False, reason='reevaluated_resource_does_not_fit', resource=resource)
        elif column.startswith('reservation<SEP>'):
            if not 0 <= evaluated[column].iloc[0] <= 1:
                return dict(feasible=False, reason='reevaluated_normalized_resource_does_not_fit')
    energy, latency = (float(evaluated[c].iloc[0]) for c in ('Total<SEP>energy', common.LATENCY))
    if any(not math.isfinite(v) or v <= 0 for v in (energy, latency)):
        raise ValueError('invalid re-evaluated frozen-mapping costs')
    return dict(feasible=True, energy=energy, latency=latency, edp=energy * latency,
                gb_bits=int(evaluated[RAW_GB].iloc[0]), mapping_id=common.mapping_identity(mapping),
                policy_membership_claimed=False)


def search_point(case, point, dag, zero_fused_loops=False):
    started = time.perf_counter()
    spec = make_spec(case, point, zero_fused_loops)
    result, stats = common.search(spec)
    picked = common.best_row(result.data)
    if picked is None:
        raise ValueError(f'no selected mapping for {point.key}')
    mapping = picked['Total<SEP>mapping']()
    search_seconds = time.perf_counter() - started
    checked = validate_pick(case, point.shape, point.capacity_bytes, picked, point.gb_latency_scale)
    if not checked['feasible'] or not checked['ok']:
        raise AssertionError('own-architecture selected mapping failed reconstruction')
    energy = result.data['Total<SEP>energy'].to_numpy(dtype=np.float64)
    latency = result.data[common.LATENCY].to_numpy(dtype=np.float64)
    edp = energy * latency
    tied = np.flatnonzero(edp <= float(edp.min()) * (1 + common.TIE_REL))
    tied_ids = sorted({common.mapping_identity(result.data.iloc[int(p)]['Total<SEP>mapping']())
                       for p in tied[:common.MAX_TIES]})
    numeric = result.data.select_dtypes(include='number')
    numeric = numeric[sorted(numeric)].sort_values(sorted(numeric)).reset_index(drop=True)
    record = dict(point=asdict(point), key=point.key, budget=list(point.budget),
                  search_stats=stats, spec_search_and_selection_s=search_seconds,
                  validation=dict(ok=True, energy=checked['energy'], latency=checked['latency']),
                  energy=checked['energy'], latency=checked['latency'], edp=checked['edp'],
                  gb_bits=int(picked[RAW_GB]), spatial=checked['spatial'],
                  mapping_id=checked['mapping_id'], mapping=mapping_structure(mapping),
                  tied_mapping_ids=tied_ids, tied_set_complete=len(tied) <= common.MAX_TIES,
                  graph=graph_observations(mapping, dag),
                  frontier_columns={c: numeric[c].tolist() for c in numeric},
                  frontier_dtypes={c: str(numeric[c].dtype) for c in numeric},
                  zero_fused_loops=zero_fused_loops)
    return record, mapping


def comparison(reference, candidate):
    if candidate is None:
        return dict(feasible=False, relative_edp_gap=None)
    # Negative gaps are retained: the current FFM policy is not a global oracle.
    return dict(feasible=True, edp=candidate['edp'],
                relative_edp_gap=candidate['edp'] / reference['edp'] - 1)


def budget_comparisons(records, frozen, nominal_shape):
    grouped = {}
    for r in records:
        grouped.setdefault(tuple(r['budget']), []).append(r)
    results = []
    for budget, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda r: (r['edp'], r['key']))
        best = ordered[0]
        nominal = next(r for r in rows if (r['point']['px'], r['point']['py']) == nominal_shape)
        transfers = [(r, frozen[r['key']]) for r in rows if frozen[r['key']]['feasible']]
        transferred = min(transfers, key=lambda pair: (pair[1]['edp'], pair[0]['key'])) if transfers else None
        tied = [r['key'] for r in rows if r['edp'] <= best['edp'] * (1 + common.TIE_REL)]
        results.append(dict(
            budget=dict(pe_count=budget[0], globalbuffer_bytes=budget[1], gb_latency_scale=budget[2],
                        gb_read_GBps=512 / budget[2], gb_write_GBps=128 / budget[2]),
            reference_best_key=best['key'], reference_tied_keys=tied, reference_edp=best['edp'],
            fixed_nominal_shape=dict(key=nominal['key'], **comparison(best, nominal)),
            fixed_anchor_mapping=dict(best_key=transferred[0]['key'] if transferred else None,
                                      feasible_shapes=len(transfers),
                                      **comparison(best, transferred[1] if transferred else None)),
            best_known_edp=min([best['edp']] + [r['edp'] for _, r in transfers]),
            grid_reference_globally_optimal_claimed=False,
        ))
    return results


def switch_observations(records):
    """Adjacent grid changes; disjoint tied sets differ from chosen-ID changes."""
    changes = []
    for axis, fixed in (('capacity_bytes', ('px', 'py', 'gb_latency_scale')),
                        ('gb_latency_scale', ('px', 'py', 'capacity_bytes'))):
        groups = {}
        for r in records:
            groups.setdefault(tuple(r['point'][k] for k in fixed), []).append(r)
        for group in groups.values():
            ordered = sorted(group, key=lambda r: r['point'][axis])
            for a, b in zip(ordered, ordered[1:]):
                changes.append(dict(axis=axis, a=a['key'], b=b['key'],
                    selected_mapping_changed=a['mapping_id'] != b['mapping_id'],
                    complete_tied_sets_disjoint=(not set(a['tied_mapping_ids']) & set(b['tied_mapping_ids']))
                        if a['tied_set_complete'] and b['tied_set_complete'] else None,
                    graph_decisions_changed=a['graph']['signature'] != b['graph']['signature'],
                    intermediate_storage_components_changed=(a['graph']['intermediate_storage_components'] !=
                                                             b['graph']['intermediate_storage_components']),
                    gb_peak_bits_changed=a['gb_bits'] != b['gb_bits']))
    return changes


def run(case, shapes, capacities, scales, output, controls=True):
    common.clear_switches()
    common.af.set_n_parallel_jobs(1)
    if effective_pareto_tolerance() != 0:
        raise ValueError('coupling reference requires zero Pareto tolerance')
    if len({math.prod(s) for s in shapes}) != 1 or (16, 16) not in shapes:
        raise ValueError('use equal PE counts and include predeclared nominal shape 16x16')
    if 1.0 not in scales:
        raise ValueError('nominal bandwidth scale 1 must be included')
    nominal_shape = (16, 16)
    anchor_point = Point(16, 16, sorted(capacities)[len(capacities) // 2], 1.)
    points = [Point(*shape, cap, scale) for cap, scale, shape in itertools.product(capacities, scales, shapes)]
    points = [anchor_point] + [p for p in points if p != anchor_point]
    dag = WorkloadDAG.from_workload(make_spec(case, anchor_point).workload)
    report = dict(case=asdict(case), workload=str(case), graph=asdict(dag),
        config=dict(shapes=shapes, capacities_bytes=capacities, gb_latency_scales=scales,
                    anchor=asdict(anchor_point), nominal_shape=nominal_shape,
                    fixed_topology=True, calibrated_area_budget=False, bandwidth_energy_scaled=False,
                    comparison_scope='Equal PE count, exact SRAM bytes and GB read/write bandwidth within each stratum; no best architecture across different strata.',
                    mainmemory_GBps=38.4, leakage_zero=True, workers=1),
        records=[], frozen_mapping_evaluations={}, zero_fused_loop_controls=[],
        status='in_progress', new_joint_optimizer_implemented=False,
        environment=dict(python=platform.python_version(), platform=platform.platform(),
                         numpy=np.__version__))
    started = time.perf_counter()
    anchor_record, anchor_mapping = None, None

    def save():
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, separators=(',', ':'), allow_nan=False) + '\n')
        temporary.replace(output)

    try:
        for point in points:
            record, mapping = search_point(case, point, dag)
            report['records'].append(record)
            if point == anchor_point:
                anchor_record, anchor_mapping = record, mapping
            transfer = evaluate_frozen(case, point, anchor_mapping, anchor_record)
            report['frozen_mapping_evaluations'][point.key] = transfer
            save()
            print(json.dumps(dict(point=point.key, edp=record['edp'], gb_bits=record['gb_bits'],
                                  search_s=record['spec_search_and_selection_s'],
                                  frozen_feasible=transfer['feasible'])), flush=True)
        if controls:
            # Same graph and hardware; limits shared-loop granularity. This is
            # not an independent-layer or necessarily all-DRAM mapping space.
            for cap, scale in itertools.product(capacities, scales):
                point = Point(16, 16, cap, scale)
                control, _ = search_point(case, point, dag, zero_fused_loops=True)
                reference = next(r for r in report['records'] if r['key'] == point.key)
                report['zero_fused_loop_controls'].append(dict(
                    **control, relative_gap_to_full_graph_search=control['edp'] / reference['edp'] - 1))
                save()
        report['budget_comparisons'] = budget_comparisons(
            report['records'], report['frozen_mapping_evaluations'], nominal_shape)
        report['mapping_switches'] = switch_observations(report['records'])
        report['total_experiment_s'] = time.perf_counter() - started
        report['timing_scope'] = 'One serial diagnostic grid, including own-architecture validation, frozen-map reevaluations and control searches; not a speedup benchmark.'
        report['source_sha256'] = {str(p.relative_to(common.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in (Path(__file__), common.ROOT / 'research/tracking_audit/shape_capacity_audit.py',
                                            common.ROOT / 'examples/arches/nvdla.yaml')}
        report['status'] = 'complete'
    except Exception as exc:
        report['status'] = 'failed'
        report['failure'] = dict(type=type(exc).__name__, message=str(exc))
        save()
        raise
    save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workload', choices=('matmuls', 'glu'), required=True)
    parser.add_argument('--params', required=True)
    parser.add_argument('--shapes', default='8x32,16x16,32x8')
    parser.add_argument('--capacities', default='4096,8192,16384')
    parser.add_argument('--gb-latency-scales', default='1,4,16')
    parser.add_argument('--skip-controls', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(common.Case.parse(args.workload, 'nvdla', args.params),
        tuple(tuple(map(int, s.split('x'))) for s in args.shapes.split(',')),
        tuple(sorted(set(map(int, args.capacities.split(','))))),
        tuple(sorted(set(map(float, args.gb_latency_scales.split(','))))),
        args.output, not args.skip_controls)


if __name__ == '__main__':
    main()
