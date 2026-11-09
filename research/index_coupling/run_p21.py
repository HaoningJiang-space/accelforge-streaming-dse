"""Frozen P21 experiment. Run on the designated server: --case 0..15.

Each case includes full-granularity and three conditional tile interfaces.
No inferred partial-retention policy is constructed by shrinking a graph.
"""
import argparse
import gc
import hashlib
import json
import os
from math import isfinite
from pathlib import Path
import platform
import resource
import signal
import subprocess
import time
from itertools import product

from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.curve import curve, pareto
from research.index_coupling.graph.model import Graph, residual
from research.index_coupling.simulate_nest import simulate

SHAPES = ((2, 2, 2), (2, 2, 4), (4, 2, 2), (4, 4, 2))
CASES = tuple(product(SHAPES, (2, 8), (False, True)))


def pts(points):
    return [list(p[:2]) for p in points]


def frontier(points):
    return pts(pareto((c, q, ()) for c, q in points))


def shifted(points, capacity=0, traffic=0):
    return [[c + capacity, q + traffic] for c, q, *_ in points]


def serial(parts):
    # Independent exhaustive product, not the solver's staircase merge.
    return frontier((max(p[0] for p in chosen), sum(p[1] for p in chosen))
                    for chosen in product(*parts))


def intervals(rows):
    out = []
    for capacity, value in rows:
        if out and out[-1]['value'] == value and out[-1]['hi'] == capacity:
            out[-1]['hi'] = capacity + 1
        else:
            out.append(dict(lo=capacity, hi=capacity + 1, value=value))
    return out


def finite(value):
    return value if isfinite(value) else None


def comparison(predicted, actual):
    hi = max((p[0] for p in predicted + actual), default=0)
    rows = []
    for c in range(hi + 1):
        p, a = traffic_at(c, predicted), traffic_at(c, actual)
        if p != a:
            rows.append((c, dict(predicted=finite(p), actual=finite(a),
                                 error=finite(p-a))))
    return dict(exact=not rows, informative=bool(predicted or actual),
                checked_through=hi, constant_tail_equal=(
                    traffic_at(hi, predicted) == traffic_at(hi, actual)),
                wrong_capacities=len(rows), errors=intervals(rows))


def decisions(keep, spill):
    hi = max((p[0] for p in keep + spill), default=0)
    rows = []
    for c in range(hi + 1):
        k, s = traffic_at(c, keep), traffic_at(c, spill)
        decision = ('infeasible' if not isfinite(min(k, s)) else
                    'tie' if k == s else 'keep' if k < s else 'spill')
        rows.append((c, decision))
    return dict(intervals=intervals(rows), tail=rows[-1][1])


def replay(graph, points):
    records = []
    for c, q, witness in points:
        try:
            actual = simulate(graph, witness)
            exact = actual['valid'] and (actual['peak'], actual['traffic']) == (c, q)
            records.append(dict(capacity=c, traffic=q, exact=exact, actual=actual))
        except Exception as exc:
            records.append(dict(capacity=c, traffic=q, exact=False,
                                error=f'{type(exc).__name__}: {exc}'))
    return records


def interface_case(shape, depth, reads_x, free=False):
    graph = residual(*shape, depth, reads_x)
    groups = ((graph.ops[0],), graph.ops[1:-1], (graph.ops[-1],))
    children = [Graph(graph.sizes, [(op, graph.access[op]) for op in group])
                for group in groups]
    s = graph.size('X', ())
    cold = [pts(curve(child, entry='group')) for child in children]
    resident = [pts(curve(child, entry='group', external={'X'})) for child in children]
    predicted_spill = serial(cold)
    predicted_keep = serial([shifted(p, s) for p in resident])
    # The coarse version changes only H; endpoint profiles remain identical.
    coarse_keep = serial([shifted(resident[0], s), shifted(cold[1], s),
                          shifted(resident[2], s)])
    predicted = frontier(predicted_keep + predicted_spill)
    coarse = frontier(coarse_keep + predicted_spill)
    mono_keep = curve(graph, root_groups=groups, root_kept={'X'}, witness=True)
    mono_spill = curve(graph, root_groups=groups, root_kept=set(), witness=True)
    actual = frontier(pts(mono_keep) + pts(mono_spill))
    bridge_keep, bridge_spill = shifted(cold[1], s), shifted(cold[1], traffic=2*s)
    bridge = frontier(bridge_keep + bridge_spill)
    # Independently query the H interface with unused/resident X.
    conditional_bridge = frontier(shifted(resident[1], s) + bridge_spill)
    checks = dict(keep=comparison(predicted_keep, pts(mono_keep)),
                  spill=comparison(predicted_spill, pts(mono_spill)),
                  composed=comparison(predicted, actual),
                  coarse=comparison(coarse, actual),
                  bridge=comparison(bridge, conditional_bridge),
                  h_residency=comparison(cold[1], resident[1]))
    hi = max((c for c, _ in predicted + coarse), default=0)
    eligible, mismatches = [], []
    for c in range(hi + 1):
        ek = sum(traffic_at(c-s, resident[i]) for i in (0, 2))
        es = sum(traffic_at(c, cold[i]) for i in (0, 2))
        if isfinite(ek) and isfinite(es) and es - ek == 2*s:
            eligible.append(c)
            # Compare costs directly: no inf-inf subtraction.
            k, d = traffic_at(c-s, cold[1]), traffic_at(c, cold[1]) + 2*s
            coarse_choice = 'infeasible' if not isfinite(min(k, d)) else 'tie' if k == d else 'keep' if k < d else 'spill'
            ak, ad = traffic_at(c, mono_keep), traffic_at(c, mono_spill)
            actual_choice = 'infeasible' if not isfinite(min(ak, ad)) else 'tie' if ak == ad else 'keep' if ak < ad else 'spill'
            if coarse_choice != actual_choice:
                mismatches.append((c, dict(predicted=coarse_choice, actual=actual_choice)))
    out = dict(shape=shape, depth=depth, reads_x=reads_x, s=s,
               children=dict(cold=cold, resident=resident),
               curves=dict(keep=pts(mono_keep), spill=pts(mono_spill), actual=actual,
                           predicted=predicted, coarse=coarse, bridge=bridge,
                           conditional_bridge=conditional_bridge),
               checks=checks, choices=decisions(pts(mono_keep), pts(mono_spill)),
               coarse_choices=decisions(coarse_keep, predicted_spill),
               bare_inequality=dict(eligible_capacities=eligible,
                                    wrong_choices=intervals(mismatches)),
               witnesses=dict(keep=mono_keep, spill=mono_spill),
               replay=dict(keep=replay(graph, mono_keep), spill=replay(graph, mono_spill)))
    if free:
        unrestricted = curve(graph, witness=True)
        out['curves']['unrestricted'] = pts(unrestricted)
        out['checks']['free'] = comparison(predicted, pts(unrestricted))
        out['witnesses']['unrestricted'] = unrestricted
        out['replay']['unrestricted'] = replay(graph, unrestricted)
    return out


def run(index):
    shape, depth, reads_x = CASES[index]
    grids = [shape, (shape[0]//2, shape[1], shape[2]),
             (shape[0], shape[1]//2, shape[2]), (shape[0]//2, shape[1]//2, shape[2])]
    rows = []
    for tile in dict.fromkeys(grids):
        rows.append(interface_case(tile, depth, reads_x, free=tile == shape))
        gc.collect()
    return dict(case=index, shape=shape, depth=depth, reads_x=reads_x, interfaces=rows)


def timeout(_signum, _frame):
    raise TimeoutError('frozen 180-second case limit')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=int, choices=range(len(CASES)), required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (8*2**30, 8*2**30))
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(180)
    start = time.monotonic()
    protocol = Path(__file__).with_name('PROTOCOL.md').read_bytes()
    revision = os.environ.get('P21_SOURCE_REVISION') or subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True).strip()
    meta = dict(case=args.case, source_revision=revision, python=platform.python_version(),
        protocol_sha256=hashlib.sha256(protocol).hexdigest())
    try:
        result = run(args.case)
        meta.update(status='complete', result=result)
    except Exception as exc:
        meta.update(status='incomplete', error=f'{type(exc).__name__}: {exc}')
    signal.alarm(0)
    meta.update(seconds=time.monotonic()-start,
                peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    print(json.dumps(meta, allow_nan=False), flush=True)
    return 0 if meta['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
