"""Probe whether upstream AccelForge FFM joins reconvergent (diamond) graphs.

Uses only the upstream public API so it runs in a separate upstream venv.
Prints one JSON line per case: status, wall seconds and the capacity/traffic
Pareto frontier in bytes on upstream's Snowcat (1 J/bit MainMemory actions).
"""
import argparse
import json
import math
import traceback
from pathlib import Path
from time import perf_counter

import accelforge as af

ROOT = Path(__file__).parent
GPT_SHRINK = dict(D=4, G=4, J=4, H=1, E=4, F=4, C=16)


def spec_for(case, n):
    if case == 'gpt_scaled':
        spec = af.Spec.from_yaml(af.examples.arches.snowcat, af.examples.workloads.transformers.gpt.gpt3_6_7B,
                                 jinja_parse_data=dict(BATCH_SIZE=1, DECODE=False, N_NEW_TOKENS=2))
        sizes = spec.workload.rank_sizes
        missing = sorted(set(GPT_SHRINK) - set(sizes))
        if missing:
            raise KeyError(f'upstream GPT has no ranks {missing}; available {sorted(sizes)}')
        sizes.update(GPT_SHRINK)
        return spec
    if case in ('shared_input', 'shared_input_copy'):
        return af.Spec.from_yaml(af.examples.arches.snowcat, ROOT / 'shared_input.yaml',
                                 jinja_parse_data=dict(N=n, COPY=case == 'shared_input_copy'))
    if case.startswith('ffn_'):
        return af.Spec.from_yaml(af.examples.arches.snowcat, ROOT / 'ffn_train.yaml',
                                 jinja_parse_data=dict(M=2 * n, D=n, F=2 * n, COPY=case.endswith('_copy'),
                                                       FORWARD_WGRAD_ONLY=case.startswith('ffn_fwd_wgrad')))
    cross, join = {'same': (False, False), 'cross': (True, False), 'same_join': (False, True),
                   'cross_join': (True, True)}[case]
    return af.Spec.from_yaml(af.examples.arches.snowcat, ROOT / 'coupling.yaml',
                             jinja_parse_data=dict(N=n, CROSS=cross, JOIN=join))


def frontier(results, glb_bits):
    pts = sorted((float(u) * glb_bits / 8, float(e) / 8)
                 for u, e in zip(results.resource_usage()['GlobalBuffer'], results.energy()))
    out, best = [], math.inf
    for cap, traffic in pts:
        if traffic < best - 1e-9:
            best = traffic
            out.append((round(cap, 3), traffic))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cases', nargs='+', choices=['same', 'cross', 'same_join', 'cross_join', 'gpt_scaled', 'ffn_full', 'ffn_fwd_wgrad', 'shared_input', 'shared_input_copy', 'ffn_full_copy'])
    parser.add_argument('--n', type=int, default=4)
    parser.add_argument('--actions', action='store_true', help='also record per-tensor DRAM actions at minimum traffic')
    args = parser.parse_args()
    af.set_n_parallel_jobs(1)
    for case in args.cases:
        start = perf_counter()
        record = dict(case=case, n=args.n)
        try:
            spec = spec_for(case, args.n)
            spec.mapper.metrics = af.Metrics.ENERGY | af.Metrics.RESOURCE_USAGE
            results = spec.map_workload_to_arch()
            record.update(status='ok', frontier=frontier(results, float(spec.arch.find('GlobalBuffer').size)))
            if args.actions:
                # Snowcat MainMemory costs 1 J/bit, so its per-tensor energy is DRAM bits.
                idx = int(results.data['Total<SEP>energy'].reset_index(drop=True).idxmin())
                per = results[idx].energy(per_tensor=True, per_component=True)
                record['min_traffic_dram_bytes'] = {f'{t}': float(v) / 8 for (c, t), v in per.items()
                                                    if c == 'MainMemory' and float(v)}
        except Exception as error:
            record.update(status='error', error=f'{type(error).__name__}: {error}'[:600],
                          where=traceback.format_exc().strip().splitlines()[-3][:300])
        record['seconds'] = round(perf_counter() - start, 1)
        print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
