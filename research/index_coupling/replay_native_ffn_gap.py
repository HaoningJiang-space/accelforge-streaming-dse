"""Re-search archived FFN contract and re-evaluate two selected native mappings.

Use the upstream AccelForge environment, with upstream ahead of this research
checkout on PYTHONPATH. One worker; set memory/time limits in the launcher.
Search remains ENERGY | RESOURCE_USAGE, with detailed metrics only afterward.
"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from time import perf_counter

import accelforge as af
from accelforge.mapper.FFM.main import map_workload_to_arch
from accelforge.model.main import evaluate_mapping
from research.index_coupling.upstream_probe import frontier, spec_for


def emit(record):
    print(json.dumps(record), flush=True)


def node_summary(node):
    result = {'type': type(node).__name__}
    for key in ('rank_variable', 'tile_shape', 'initial_tile_shape',
                'calculated_n_iterations', 'component', 'resource', 'tensors',
                'purposes', 'einsum'):
        try:
            value = getattr(node, key)
        except (AttributeError, ValueError, TypeError):
            continue
        result[key] = value if value is None or isinstance(value, (str, int, float, bool)) else str(value)
    if hasattr(node, 'nodes'):
        result['nodes'] = [node_summary(n) for n in node.nodes]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace-merge', action='store_true', help='observe original merge calls, without changing their result')
    parser.add_argument('--save-sources', help='optional local pickle of selected native source rows, for repeatable diagnosis')
    args = parser.parse_args()
    start = perf_counter()
    upstream = Path(af.__file__).resolve().parent.parent
    research = Path(__file__).resolve().parents[2]
    emit({'kind': 'metadata',
          'upstream_commit': subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], text=True).strip(),
          'research_commit': subprocess.check_output(['git', '-C', str(research), 'rev-parse', 'HEAD'], text=True).strip(),
          'workload_sha256': hashlib.sha256(Path(__file__).with_name('ffn_train.yaml').read_bytes()).hexdigest(),
          'case': 'ffn_full_copy', 'shape': [8, 4, 8],
          'search_metrics': 'ENERGY | RESOURCE_USAGE', 'workers': 1,
          'query_capacity_rounding_decimals': 3})
    af.set_n_parallel_jobs(1)
    spec = spec_for('ffn_full_copy', 4)
    spec.mapper.metrics = af.Metrics.ENERGY | af.Metrics.RESOURCE_USAGE
    results = map_workload_to_arch(spec, eval_in_detail=False, print_progress=False)
    bits = float(spec.arch.find('GlobalBuffer').size)
    emit({'kind': 'search', 'seconds': perf_counter()-start,
          'rows': len(results.data), 'frontier': frontier(results, bits)})
    reserve = next(c for c in results.data.columns if c.startswith('reservation<SEP>GlobalBuffer<SEP>'))
    from accelforge.frontend.mapping import Nested, Compute
    original_merge = Nested._merge
    merge_trace = []

    def observed_merge(left, right, n_shared_loops):
        record = {'left_ops': [str(n.einsum) for n in left.get_nodes_of_type(Compute)],
                  'right_ops': [str(n.einsum) for n in right.get_nodes_of_type(Compute)],
                  'requested_shared_loops': n_shared_loops,
                  'adjacent_shared_loops': left._get_n_shared_loops(right),
                  'left_nodes_before': node_summary(left),
                  'right_nodes_before': node_summary(right)}
        merge_trace.append(record)
        try:
            merged = original_merge(left, right, n_shared_loops)
        except Exception as error:
            record['status'] = 'failed'
            record['error'] = type(error).__name__+': '+str(error)
            raise
        record['status'] = 'merged'
        return merged

    if args.trace_merge:
        Nested._merge = observed_merge
    selected_sources = []
    for budget in (80, 147):
        # Match the archived frontier's three-decimal capacity contract. Resource
        # fractions are float32; a nominal integer can expand to 147.0000... B.
        candidates = [(float(row['Total<SEP>energy'])/8, round(float(row[reserve])*bits/8, 3), i)
                      for i, (_, row) in enumerate(results.data.iterrows())
                      if round(float(row[reserve])*bits/8, 3) <= budget]
        traffic, capacity, index = min(candidates)
        row = results.data.iloc[index]
        selected_sources.append({'capacity_budget': budget, 'row': row})
        merge_trace.clear()
        record = {'kind': 'native_replay', 'capacity_budget': budget,
                  'source_index': index, 'joined_peak': capacity, 'joined_traffic': traffic,
                  'joined_peak_raw': float(row[reserve])*bits/8,
                  'per_einsum_joined_energy_bytes': {
                      str(c): float(row[c])/8 for c in row.index
                      if c.endswith('<SEP>energy') and not c.startswith('Total<SEP>')},
                  'per_einsum_mapping': {str(c): str(row[c]) for c in row.index
                                        if c.endswith('<SEP>mapping') and not c.startswith('Total<SEP>')}}
        phase = 'reconstruct'
        try:
            local = deepcopy(spec)
            local.mapping = row['Total<SEP>mapping'](_for_model=True)
            record['mapping'] = str(local.mapping)
            phase = 'evaluate'
            local.model.metrics = af.Metrics.ENERGY | af.Metrics.RESOURCE_USAGE | af.Metrics.ACTIONS
            evaluated = evaluate_mapping(local, flattened_arches=results.flattened_arches,
                                         evaluated_specs=results.evaluated_specs)
            record['evaluated_frontier'] = frontier(evaluated, bits)
            record['dram_energy_bytes'] = [
                {'einsum': e, 'tensor': t, 'action': a, 'bytes': float(v)/8}
                for (e, c, t, a), v in evaluated.energy(
                    per_einsum=True, per_component=True, per_tensor=True, per_action=True).items()
                if c == 'MainMemory' and float(v)]
            record['status'] = 'reevaluated'
        except Exception as error:
            record['status'] = 'failed'
            record['phase'] = phase
            record['error'] = (type(error).__name__+': '+str(error)).replace(str(upstream), '<upstream>').replace(str(research), '<research>')[:1500]
        if args.trace_merge:
            record['merge_trace'] = deepcopy(merge_trace)
        emit(record)
    Nested._merge = original_merge
    if args.save_sources:
        try:
            import cloudpickle
            payload = {'spec': spec, 'sources': selected_sources,
                       'flattened_arches': results.flattened_arches,
                       'evaluated_specs': results.evaluated_specs}
            data = cloudpickle.dumps(payload)
            Path(args.save_sources).write_bytes(data)
            emit({'kind': 'source_snapshot', 'status': 'saved', 'bytes': len(data),
                  'sha256': hashlib.sha256(data).hexdigest()})
        except Exception as error:
            emit({'kind': 'source_snapshot', 'status': 'failed',
                  'error': type(error).__name__+': '+str(error)})
    emit({'kind': 'done', 'seconds': perf_counter()-start})


if __name__ == '__main__':
    main()
