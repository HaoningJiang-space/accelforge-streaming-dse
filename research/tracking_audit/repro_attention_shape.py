"""Standalone oracle: also runnable against e76e66bf via PYTHONPATH.

No EnumerationReuse, common.search, or shape-audit helper is used. A nonzero
exit after saving JSON means the selected row disagrees with reconstruction.
"""
import argparse
import copy
import json
import math
import os
from pathlib import Path

import accelforge as af
from accelforge.mapper.FFM.main import make_pmappings, join_pmappings
from accelforge.model.main import evaluate_mapping


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for key in list(os.environ):
        if key.startswith('AF_'):
            del os.environ[key]
    af.set_n_parallel_jobs(1)
    spec = af.Spec.from_yaml(args.arch, Path(__file__).parents[1] / 'workloads/attention_qk_av.yaml',
                            jinja_parse_data={'N_TOKENS': 128, 'N_HEADS': 1, 'D_HEAD': 64})
    spec.arch.find('GlobalBuffer').size = 131072 * 8
    spec.arch.find('Register').size = 8
    for dim, fanout in zip(spec.arch.find('ArrayFanout').spatial, (64, 96)):
        dim.fanout = fanout
    metrics = af.Metrics.ENERGY | af.Metrics.LATENCY | af.Metrics.RESOURCE_USAGE
    spec.mapper.ffm.metrics = metrics
    pm = make_pmappings(spec, print_number_of_pmappings=False)
    os.environ['AF_VARIABLE_RESOURCES'] = 'GlobalBuffer'
    result = join_pmappings(pm).data
    del os.environ['AF_VARIABLE_RESOURCES']
    rows = result[result['reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right'] <= 8192 * 8]
    costs = rows['Total<SEP>energy'].astype(float) * rows['Total<SEP>latency'].astype(float)
    row = rows.iloc[int(costs.to_numpy().argmin())]
    target = copy.deepcopy(spec)
    target.arch.find('GlobalBuffer').size = 8192 * 8
    target.model.metrics = metrics
    target.mapping = row['Total<SEP>mapping']()
    ev = evaluate_mapping(target).data
    columns = ['Total<SEP>energy', 'Total<SEP>latency', 'reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right']
    report = {'accelforge_source': af.__file__, 'shape': [64, 96], 'search_bytes': 131072,
              'query_bytes': 8192, 'reported': {c: float(row[c]) for c in columns},
              'reconstructed': {c: float(ev[c].iloc[0]) for c in columns}}
    report['matches'] = all(math.isclose(report['reported'][c], report['reconstructed'][c],
                                         rel_tol=1e-6, abs_tol=0) for c in columns)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)
    if not report['matches']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
