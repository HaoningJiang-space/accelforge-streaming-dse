"""Physical-capacity oracle for integer boundaries; not a shared-backend oracle."""
import argparse
import hashlib
from contextlib import contextmanager
import importlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import common
from accelforge.mapper.FFM._pareto_df.target_membership import PackedMembership
from accelforge.mapper.FFM._pareto_df import pareto

tiles = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')
CASE = common.Case('matmuls', 'nvdla', (2, 4, 8))
RAW = 'reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right'


@contextmanager
def capture_tiles():
    original, snapshots = tiles.get_tile_shape_choices_for_targets, {}

    def capture(objectives, capacity_targets, **kwargs):
        choices, membership = original(objectives, capacity_targets, **kwargs)
        j = kwargs['job']
        key = repr((j.einsum_name, j.mapping.compact_str(), tuple(map(str, kwargs['symbols']))))
        parts = {}
        if capacity_targets:
            for k, (_, bound) in enumerate(capacity_targets):
                mask = ((membership.words[:, k // 64] >> np.uint64(k % 64)) & np.uint64(1)).astype(bool) if isinstance(membership, PackedMembership) else ~membership[:, k]
                parts[int(bound)] = {tuple(row) for row in choices[mask].tolist()}
        else:
            parts[j.resource_capacities['GlobalBuffer']] = {tuple(row) for row in choices.tolist()}
        if key in snapshots:
            raise AssertionError('template identity collision in coverage audit')
        snapshots[key] = parts
        return choices, membership

    tiles.get_tile_shape_choices_for_targets = capture
    try:
        yield snapshots
    finally:
        tiles.get_tile_shape_choices_for_targets = original


def search(capacity_bytes, targets=None, backend='events', codec='bitset'):
    caps = [c / 2**20 for c in (targets or [capacity_bytes])]
    env = {'AF_GENERATION_VARIABLE_RESOURCES': 'GlobalBuffer', 'AF_TARGET_ENUMERATION': backend,
           'AF_CAPACITY_MEMBERSHIP': codec}
    if targets:
        env.update(common.capacity_fractions_env(caps))
    with capture_tiles() as snapshots:
        result, stats = common.search(common.build(CASE, capacity_bytes / 2**20, common.RU), env,
                                      {'AF_VARIABLE_RESOURCES': 'GlobalBuffer'})
    return result.data, snapshots, stats


def cost_frontier(data):
    cols = ['Total<SEP>energy', 'Total<SEP>latency']
    return pareto.makepareto(data[cols]).drop_duplicates().sort_values(cols).to_numpy(dtype=float)


def compare(reference, shared, capacity_bytes, upper_bytes):
    direct_data, direct_tiles, _ = reference
    shared_data, shared_tiles, _ = shared
    cap = capacity_bytes / 2**20
    projected = common.rows_for_capacity(shared_data, cap, upper_bytes / 2**20)
    assert set(direct_tiles) == set(shared_tiles), 'different template sets'
    missing = extra = 0
    for key, parts in direct_tiles.items():
        a = parts[capacity_bytes * 8]
        b = shared_tiles[key][capacity_bytes * 8]
        missing += len(a - b)
        extra += len(b - a)
    assert missing == extra == 0, (capacity_bytes, upper_bytes, missing, extra)
    np.testing.assert_allclose(cost_frontier(projected), cost_frontier(direct_data), rtol=1e-6, atol=0)
    pick = common.check_pick(CASE, cap, common.best_row(projected))
    reference_pick = common.check_pick(CASE, cap, common.best_row(direct_data))
    assert pick['ok'] and reference_pick['ok'], (pick, reference_pick)
    np.testing.assert_allclose(pick['reevaluated']['edp'], reference_pick['reevaluated']['edp'], rtol=1e-6, atol=0)
    return dict(capacity_bytes=capacity_bytes, upper_bytes=upper_bytes,
                templates=len(direct_tiles), tile_assignments=sum(len(p[capacity_bytes*8]) for p in direct_tiles.values()),
                missing_tiles=missing, extra_tiles=extra, frontier_rows=len(cost_frontier(projected)),
                pick=pick, reference_pick=reference_pick)


def source_digest():
    root = Path(__file__).resolve().parents[2]
    paths = sorted((root/'accelforge').rglob('*.py'))
    paths += [Path(__file__).resolve(), Path(common.__file__).resolve()]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(root)).encode() + b'\0' + path.read_bytes())
    return digest.hexdigest()


def audit_glu():
    """Small real Fusion graph, comparing against physical EL-only searches."""
    records = []
    for arch in ('nvdla','tpu_v4i'):
        case = common.Case('glu',arch,(8,16,32))
        caps = [128/2**20,256/2**20,1024/2**20]
        shared,stats = common.search(common.build(case,max(caps),common.RU),
            {**common.capacity_fractions_env(caps),'AF_TARGET_ENUMERATION':'events',
             'AF_CAPACITY_MEMBERSHIP':'interval','AF_GENERATION_VARIABLE_RESOURCES':'GlobalBuffer'},
            {'AF_VARIABLE_RESOURCES':'GlobalBuffer'})
        checks = []
        for cap in caps:
            direct,_ = common.search(common.build(case,cap,common.EL))
            projected = common.rows_for_capacity(shared.data,cap,max(caps))
            np.testing.assert_allclose(cost_frontier(projected),cost_frontier(direct.data),rtol=1e-6,atol=0)
            a = common.check_pick(case,cap,common.best_row(projected))
            b = common.check_pick(case,cap,common.best_row(direct.data))
            assert a['ok'] and b['ok'], (a,b)
            checks.append(dict(capacity_bytes=cap*2**20,shared=a,direct=b))
        records.append(dict(arch=arch,case=str(case),shared_stats=stats,checks=checks))
        print('PASS GLU',arch,flush=True)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--capacities', default='63,64,65,67,68,69,71,72,73,79,80,81,95,96,97,127,128,129')
    parser.add_argument('--uppers', default='96,128,160')
    parser.add_argument('--glu', action='store_true', help='also audit the small GLU on both architectures')
    args = parser.parse_args()
    capacities = sorted(set(map(int,args.capacities.split(','))))
    uppers = sorted(set(map(int,args.uppers.split(','))))
    common.af.set_n_parallel_jobs(1)
    report = dict(parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  source_sha256=source_digest(),
                  case=str(CASE), capacities=capacities, uppers=uppers, runs=[], complete=False)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    def save():
        args.output.write_text(json.dumps(report,indent=2)+'\n')
    references = {c:search(c) for c in capacities}
    for upper in uppers:
        targets = sorted(set(c for c in capacities if c <= upper) | {upper})
        for backend in ('independent','events'):
            for codec in ('bitset','interval'):
                shared = search(upper, targets, backend, codec)
                for c in targets:
                    if c not in references:
                        continue
                    row = compare(references[c],shared,c,upper)
                    row.update(backend=backend,codec=codec,shared_stats=shared[2])
                    report['runs'].append(row)
                    save()
                    print('PASS',c,upper,backend,codec,flush=True)
    report['complete'] = True
    if args.glu:
        report['glu'] = audit_glu()
    save()


if __name__ == '__main__':
    main()
