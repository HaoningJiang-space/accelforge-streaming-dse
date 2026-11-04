"""Array-shape x SRAM experiment, with shape-specific reconstruction checks.

The strong baseline searches once per shape at maximum capacity and retains
the complete GlobalBuffer/energy/latency frontier. It is a physical-feasibility
baseline, not an oracle for capacity-dependent min_usage policy membership.
"""
import argparse
from contextlib import nullcontext
import copy
import json
import math
import platform
import time
from pathlib import Path

from research.tracking_audit import common
from research.tracking_audit.generation_profile import GenerationPhases
from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.enumeration_reuse import EnumerationReuse

RAW_GB = 'reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right'


def mapping_structure(mapping):
    """Export nested decisions without serializing derived component objects."""
    def node(n):
        result = {'type': type(n).__name__}
        for name in ('component', 'tensors', 'rank_variable', 'tile_shape',
                     'initial_tile_shape', 'name', 'einsum', 'purposes', 'resource', 'persistent'):
            if hasattr(n, name):
                value = getattr(n, name)
                result[name] = (sorted(map(str, value)) if isinstance(value, (set, frozenset))
                                else str(value) if value is not None else None)
        if hasattr(n, 'nodes'):
            result['nodes'] = [node(child) for child in n.nodes]
        return result
    return node(mapping)


def build(case, shape, capacity_bytes, metrics):
    if len(shape) != 2 or any(type(n) is not int or n <= 0 for n in shape):
        raise ValueError('shape must contain two positive integer fanouts')
    if type(capacity_bytes) is not int or capacity_bytes <= 0:
        raise ValueError('capacity must be a positive integer byte count')
    spec = common.build(case, capacity_bytes / 2**20, metrics)
    # These workloads use 8-bit values. The upstream NVDLA expression uses a
    # dummy 1-bit Register when an Einsum has no weight (QK_softmax), producing
    # different capacity metadata for one physical component. Fix its physical
    # size across the graph; weightless Einsums store nothing in it (keep: weight).
    spec.arch.find('Register').size = 8
    fanout = spec.arch.find('ArrayFanout')
    dimensions = {dim.name: dim for dim in fanout.spatial}
    if set(dimensions) != {'reuse_input', 'reuse_output'}:
        raise ValueError('this audit requires the NVDLA two-dimensional array')
    for name, count in zip(('reuse_input', 'reuse_output'), shape):
        dimensions[name].fanout = count
    return spec


def rows_fitting(data, capacity_bytes):
    """Physical feasibility only; no implied target-policy membership."""
    if RAW_GB not in data:
        raise ValueError('maximum-capacity baseline requires exact GlobalBuffer bits')
    return data[data[RAW_GB] <= capacity_bytes * 8]


def validate_pick(case, shape, capacity_bytes, row):
    if row is None:
        return {'feasible': False, 'ok': True}
    mapping = row['Total<SEP>mapping']()
    spec = build(case, shape, capacity_bytes, common.RU)
    spec.model.metrics = common.RU
    spec.mapping = copy.deepcopy(mapping)
    common.clear_switches()
    ev = common.evaluate_mapping(spec).data
    if len(ev) != 1:
        raise ValueError(f'expected one reconstructed mapping, got {len(ev)}')
    energy, latency = (float(ev[c].iloc[0]) for c in ('Total<SEP>energy', common.LATENCY))
    if not all(math.isfinite(v) and v >= 0 for v in (energy, latency)):
        raise ValueError('nonfinite or negative reconstructed cost')
    for c in ev:
        if c.startswith('reservation_bits<SEP>'):
            value = ev[c].iloc[0]
            bound = ev['capacity_reference_bits<SEP>' + c.split('<SEP>')[1]].iloc[0]
            if not 0 <= value <= bound or value != int(value):
                raise ValueError(f'capacity violation: {c} = {value} > {bound}')
        elif c.startswith('reservation<SEP>'):
            if not 0 <= ev[c].iloc[0] <= 1:
                raise ValueError(f'capacity violation: {c}')
    for column, value in (('Total<SEP>energy', energy), (common.LATENCY, latency)):
        if not math.isclose(float(row[column]), value, rel_tol=1e-6, abs_tol=0):
            raise ValueError(json.dumps(dict(error='reconstruction_cost_mismatch', column=column,
                shape=shape, capacity_bytes=capacity_bytes, reported=float(row[column]),
                reconstructed=value, mapping_id=common.mapping_identity(mapping),
                mapping=mapping_structure(mapping))))
    # Check the actual two-dimensional unfolding, not merely total active PEs.
    from accelforge.frontend.mapping import Compute, Loop, Nested, Spatial, Split
    from collections import defaultdict
    bounds = common.get_rank_variable_bounds_for_all_einsums(spec)
    usage = []

    def walk(nodes, loops):
        loops = list(loops)
        for i, node in enumerate(nodes):
            if isinstance(node, Split):
                for child in node.nodes:
                    walk(child.nodes if isinstance(child, Nested) else [child], loops)
                return
            if isinstance(node, Nested):
                walk(list(node.nodes) + list(nodes[i + 1:]), loops)
                return
            if isinstance(node, Loop):
                loops.append(node)
            elif isinstance(node, Compute):
                sizes, counts = dict(bounds), defaultdict(lambda: 1.)
                for loop in loops:
                    count = sizes[loop.rank_variable] / loop.tile_shape
                    sizes[loop.rank_variable] = loop.tile_shape
                    if isinstance(loop, Spatial):
                        counts[(loop.component, loop.name)] *= count
                used = [counts[('ArrayFanout', name)] for name in ('reuse_input', 'reuse_output')]
                if any(not math.isfinite(n) or n < 1 or n > bound for n, bound in zip(used, shape)):
                    raise ValueError(f'spatial unfolding {used} does not fit {shape}')
                usage.append({'einsum': node.einsum, 'used': used})
    walk(list(mapping.nodes), [])
    return {'feasible': True, 'ok': True, 'energy': energy, 'latency': latency,
            'edp': energy * latency, 'gb_bytes': int(ev[RAW_GB].iloc[0]) / 8,
            'mapping_id': common.mapping_identity(mapping), 'spatial': usage,
            'mapping': mapping_structure(mapping)}


def save(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    # Raw repeated-frontier records are machine-readable; the summary and figure
    # provide the review view. Avoid hundreds of thousands of one-number lines.
    temporary.write_text(json.dumps(report, separators=(',', ':'), allow_nan=False, default=str) + '\n')
    temporary.replace(path)


def search_grid(case, shapes, capacities, method, profile=False, collect_failures=False):
    if method not in ('independent', 'max_frontier', 'reuse_frontier', 'local_reuse'):
        raise ValueError(f'unknown method {method}')
    run = {'method': method, 'searches': [], 'picks': [], 'numeric_frontiers': []}
    pending = []
    # Include scope setup, spec construction, search, queries and teardown in DSE
    # time. Reconstruction validation is performed after the scope closes.
    start = time.perf_counter()
    reuse = EnumerationReuse() if method == 'reuse_frontier' else None
    with reuse if reuse is not None else nullcontext():
        for shape in shapes:
            local = EnumerationReuse() if method == 'local_reuse' else None
            scope = local if local is not None else reuse
            with local if local is not None else nullcontext():
                with scope.target(tuple(shape)) if scope is not None else nullcontext():
                    for cap in capacities if method == 'independent' else [max(capacities)]:
                        spec = build(case, shape, cap, common.EL if method == 'independent' else common.RU)
                        t0 = time.perf_counter()
                        phases = GenerationPhases(common) if profile else None
                        with phases if phases is not None else nullcontext():
                            result, stats = common.search(spec, join_env=(
                                {'AF_VARIABLE_RESOURCES': 'GlobalBuffer'} if method != 'independent' else None))
                        stats.update(shape=shape, capacity_bytes=cap, search_s=time.perf_counter() - t0)
                        if phases is not None:
                            stats['phases'] = phases.snapshot()
                        run['searches'].append(stats)
                        t0 = time.perf_counter()
                        for c in ([cap] if method == 'independent' else capacities):
                            rows = result.data if method == 'independent' else rows_fitting(result.data, c)
                            pending.append((shape, c, common.best_row(rows)))
                        stats['query_s'] = time.perf_counter() - t0
                        # Keep references; serializing/sorting the audit snapshot is
                        # outside DSE timing and never populates the reuse store.
                        run['numeric_frontiers'].append((shape, cap, result.data))
            if local is not None:
                run.setdefault('local_reuse_stats', []).append(dict(local.stats))
    run['dse_s'] = time.perf_counter() - start
    if reuse is not None:
        run['reuse_stats'] = dict(reuse.stats)
    run['search_s'] = sum(s['search_s'] for s in run['searches'])
    run['query_s'] = sum(s['query_s'] for s in run['searches'])
    for shape, c, row in pending:
        try:
            pick = validate_pick(case, shape, c, row)
        except Exception as error:
            if not collect_failures:
                raise
            pick = {'ok': False, 'error': str(error)}
        run['picks'].append(dict(shape=shape, capacity_bytes=c, **pick))
    snapshots = []
    for shape, cap, data in run['numeric_frontiers']:
        numeric = data.select_dtypes(include='number')
        columns = sorted(numeric.columns)
        # Keep integer columns in their native dtype (no mixed row conversion).
        ordered = numeric[columns].sort_values(columns).reset_index(drop=True)
        snapshots.append({'shape': shape, 'capacity_bytes': cap,
                          'dtypes': {c: str(ordered[c].dtype) for c in columns},
                          'columns': {c: ordered[c].tolist() for c in columns}})
    run['numeric_frontiers'] = snapshots
    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workload', choices=('matmuls', 'attention'), default='matmuls')
    parser.add_argument('--params', default='3,256,256')
    parser.add_argument('--capacities-bytes', default='131072,135167,135168,262144')
    parser.add_argument('--shapes', default='16x384,32x192,64x96')
    parser.add_argument('--methods', default='max_frontier,local_reuse,reuse_frontier')
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--warmup', action='store_true')
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--collect-failures', action='store_true',
                        help='save every invalid pick for diagnosis; still exit nonzero')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    case = common.Case.parse(args.workload, 'nvdla', args.params)
    capacities = sorted(set(map(int, args.capacities_bytes.split(','))))
    shapes = [tuple(map(int, s.split('x'))) for s in args.shapes.split(',')]
    if args.repeats < 1 or not capacities or not shapes or any(c <= 0 for c in capacities):
        raise ValueError('at least one repeat, capacity and shape are required')
    if len({math.prod(s) for s in shapes}) != 1:
        raise ValueError('shape comparison must keep the total PE count fixed')
    report = {'config': common.effective_config(case, workload=str(case), shapes=shapes,
              capacities_bytes=capacities, workers=1, platform=platform.platform(),
              python=platform.python_version(), register_bits=8), 'runs': []}
    common.af.set_n_parallel_jobs(1)
    for repeat in range(-int(args.warmup), args.repeats):
        methods = args.methods.split(',')
        if repeat % 2:
            methods.reverse()
        for method in methods:
            try:
                run = search_grid(case, shapes, capacities, method, args.profile, args.collect_failures)
            except Exception as error:
                report['failure'] = dict(repeat=repeat, method=method, error=str(error))
                report['validation'] = {'all_picks_valid': False}
                save(args.output, report)
                raise
            run['repeat'] = repeat
            report['runs'].append(run)
            save(args.output, report)
            print(json.dumps({k: v for k, v in run.items() if k not in ('picks', 'numeric_frontiers')}), flush=True)
    # A reuse optimization must preserve the complete numeric frontier of the
    # strong baseline, not just the winning architecture or one EDP.
    references = [r for r in report['runs'] if r['method'] == 'max_frontier']
    if references:
        reference = references[0]['numeric_frontiers']
        for run in report['runs']:
            if run['method'] != 'independent' and run['numeric_frontiers'] != reference:
                raise ValueError('reuse changed the complete numeric frontier')
    report['validation'] = {'all_picks_valid': all(p['ok'] for r in report['runs'] for p in r['picks']),
                            'complete_frontiers_match': True if references else None,
                            'pick_evaluations': sum(len(r['picks']) for r in report['runs'])}
    save(args.output, report)
    if not report['validation']['all_picks_valid']:
        raise ValueError('invalid reconstructed mappings; diagnostic results are not performance evidence')


if __name__ == '__main__':
    main()
