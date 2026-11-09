"""Replay a locally produced FFN source snapshot; no mapping search or core patch.

Only the four mutually independent input-copy einsums are permuted. Each keeps
its original tile values, storage and reservations; the remaining eight einsums
keep their order. A reordered result is a new schedule, not a semantics-preserving
repair of the archived search point. Evaluate every successfully reconstructed
mapping before comparing its cost or capacity with the numeric join result.

Run only on the trusted snapshot made by replay_native_ffn_gap --save-sources,
with upstream AccelForge first on PYTHONPATH. Pickle is not an exchange format.
"""
import argparse
from copy import deepcopy
import hashlib
from itertools import permutations
import json
from pathlib import Path
from time import perf_counter

import accelforge as af
import cloudpickle
from accelforge.frontend.mapping import Compute, Nested
from accelforge.mapper.FFM._join_pmappings.join_pmappings import MappingFromRow
from accelforge.model.main import evaluate_mapping
from research.index_coupling.upstream_probe import frontier

COPIES = ('CopyX', 'CopyW1', 'CopyW2', 'CopydY')
BODY = ('EH', 'EZ', 'EY', 'EdW2', 'EdZ', 'EdH', 'EdW1', 'EdX')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('snapshot')
    ap.add_argument('--all-copy-orders', action='store_true')
    args = ap.parse_args()
    raw = Path(args.snapshot).read_bytes()
    payload = cloudpickle.loads(raw)
    print(json.dumps({'kind': 'snapshot', 'sha256': hashlib.sha256(raw).hexdigest(),
                      'bytes': len(raw), 'all_copy_orders': args.all_copy_orders}), flush=True)
    af.set_n_parallel_jobs(1)
    orders = list(permutations(COPIES)) if args.all_copy_orders else [
        COPIES, ('CopyW1', 'CopyW2', 'CopyX', 'CopydY')]
    merge = Nested._merge
    trace = []

    def observed(left, right, count):
        item = {'left': [str(n.einsum) for n in left.get_nodes_of_type(Compute)],
                'right': [str(n.einsum) for n in right.get_nodes_of_type(Compute)],
                'requested': count, 'adjacent': left._get_n_shared_loops(right)}
        trace.append(item)
        try:
            result = merge(left, right, count)
        except Exception as error:
            item['status'] = 'failed'
            raise
        item['status'] = 'merged'
        return result

    Nested._merge = observed
    try:
        for source in payload['sources']:
            row = source['row']
            native = row['Total<SEP>mapping']
            assert set(k.removesuffix('<SEP>mapping') for k in row.index
                       if k.endswith('<SEP>mapping') and k != 'Total<SEP>mapping') == set(COPIES + BODY)
            for order in orders:
                start = perf_counter()
                trace.clear()
                record = {'kind': 'order_replay', 'budget': source['capacity_budget'],
                          'copy_order': order, 'body_order': BODY,
                          'changes': 'copy order only; original per-einsum mapping rows'}
                phase = 'reconstruct'
                try:
                    spec = deepcopy(payload['spec'])
                    spec.mapping = MappingFromRow(row, native.rank_variable_bounds,
                                                  list(order + BODY))(_for_model=True)
                    record['mapping_sha256'] = hashlib.sha256(str(spec.mapping).encode()).hexdigest()
                    record['reconstructed'] = True
                    phase = 'evaluate'
                    spec.model.metrics = af.Metrics.ENERGY | af.Metrics.RESOURCE_USAGE | af.Metrics.ACTIONS
                    evaluated = evaluate_mapping(spec, flattened_arches=payload['flattened_arches'],
                                                 evaluated_specs=payload['evaluated_specs'])
                    bits = float(spec.arch.find('GlobalBuffer').size)
                    record['evaluated_frontier'] = frontier(evaluated, bits)
                    record['dram_energy_bytes'] = [
                        {'einsum': str(e), 'tensor': str(t), 'action': str(a), 'bytes': float(v)/8}
                        for (e, c, t, a), v in evaluated.energy(
                            per_einsum=True, per_component=True, per_tensor=True, per_action=True).items()
                        if c == 'MainMemory' and float(v)]
                    record['status'] = 'reevaluated'
                except Exception as error:
                    record.update(status='failed', phase=phase,
                                  error=type(error).__name__ + ': ' + str(error)[:1200])
                record['merge_trace'] = deepcopy(trace)
                record['seconds'] = perf_counter()-start
                print(json.dumps(record), flush=True)
    finally:
        Nested._merge = merge


if __name__ == '__main__':
    main()
