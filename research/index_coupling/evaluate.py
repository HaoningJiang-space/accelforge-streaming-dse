"""Score the frozen PROTOCOL.md predictions P1-P4 against same/cross result pairs."""
import argparse
import json
import math
from pathlib import Path


def curve(report, key):
    return [(p['capacity_bytes'], p['traffic_bytes']) for p in report[key]['points']]


def at(points, cap):
    return min((t for c, t in points if c <= cap), default=math.inf)


def per_tensor(point):
    out = {}
    for key, bits in point['dram_actions_bits'].items():
        name = next(x for x in key.split('<SEP>') if len(x) == 1 and x.isupper())
        kind = 'write' if 'write' in key else 'read'
        out[(name, kind)] = out.get((name, kind), 0) + bits / 8
    return out


def score(same, cross, square_n=None):
    sizes_s, sizes_c = same['tensor_bytes'], cross['tensor_bytes']
    gs, gc, mc = curve(same, 'graph'), curve(cross, 'graph'), curve(cross, 'materialized')
    floor_s = sum(sizes_s[t] for t in 'ABCDUV')
    floor_c = sum(sizes_c[t] for t in 'ABCDUV')
    plateau_s = next(c for c, t in gs if t <= floor_s + 1e-9)
    plateau_c = next(c for c, t in gc if t <= floor_c + 1e-9)
    r = min(sizes_s['B'] + sizes_s['C'] + sizes_s['D'], sizes_s['A'] + sizes_s['U'] + sizes_s['V'], sizes_s['X'])
    big = max(same.get('dims', {}).values() or [same['n']])
    out = dict(floor_same=floor_s, floor_cross=floor_c, plateau_same=plateau_s, plateau_cross=plateau_c,
               P1=plateau_s == plateau_c and floor_s == floor_c, R=r,
               P2=(plateau_s == square_n**2 + square_n + 1) if square_n else r <= plateau_s <= r + 2 * big + 1)
    checks = []
    for point in same['graph']['points']:
        acts = per_tensor(point)
        if acts.get(('X', 'read'), 0) or acts.get(('X', 'write'), 0):
            continue
        reps = {t: acts.get((t, 'read'), 0) / sizes_s[t] for t in 'BCD'}
        p = reps['D']
        if p < 2 or any(abs(v - p) > 1e-9 for v in reps.values()) or p != int(p):
            continue
        cap = point['capacity_bytes']
        v_once = abs(acts.get(('V', 'write'), 0) - sizes_s['V']) < 1e-9
        predicted = min(at(mc, cap), point['traffic_bytes'] + (p - 1) * (2 * sizes_c['V'] - sizes_s['D']))
        checks.append(dict(capacity=cap, p=p, v_written_once=v_once, predicted=predicted, measured=at(gc, cap)))
    out['P3_checks'] = checks
    out['P3'] = bool(checks) and all(abs(c['predicted'] - c['measured']) < 1e-9 for c in checks)
    narrow = [c for c in checks if c['v_written_once']]
    out['P3_prime'] = bool(narrow) and all(abs(c['predicted'] - c['measured']) < 1e-9 for c in narrow)
    if square_n:
        caps = sorted({c for c, _ in gc + mc})
        onset = next((c for c in caps if at(gc, c) < at(mc, c) - 1e-9), None)
        out.update(onset=onset, P4=onset == (square_n // 2) ** 2 + square_n // 2 + 1)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('same', type=Path)
    parser.add_argument('cross', type=Path)
    parser.add_argument('--square-n', type=int)
    args = parser.parse_args()
    same, cross = (json.loads(p.read_text()) for p in (args.same, args.cross))
    print(json.dumps(score(same, cross, args.square_n), indent=1))


if __name__ == '__main__':
    main()
