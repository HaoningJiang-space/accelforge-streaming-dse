"""Score frozen predictions (PROTOCOL.md) from archived runner output.

Usage: python -m research.index_coupling.graph.scoring <command> [files]
  sweep FILE         sign of dS for every shape of a coupling sweep
  p15                P15/P16 on results/coupling_sweep_heldout.jsonl
  p18                P18 on results/p18.jsonl
  p19 FILE           P19 on run output
  ffn FILE...        P12 and P14-FFN from ffn-part outputs (union of breakpoints)
"""
import json
import sys
from collections import Counter, defaultdict
from math import ceil

from research.index_coupling.graph.analysis import compare_to_reference, delta, gap_steps, positive_width, sign
from research.index_coupling.graph.curve import pareto
from research.index_coupling.graph.experiments import P19_ROLES, p19_shapes
from research.index_coupling.graph.references import RESULTS, ffn_case


def read_jsonl(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def sweep(path):
    rows = read_jsonl(path)
    for mode in ('wt', 'nowt'):
        tally = Counter()
        for r in rows:
            tally[sign(delta(r[f'same_{mode}'], r[f'cross_{mode}']))] += 1
        print(mode, dict(tally))


def p15():
    exact = within = p16 = 0
    rows = read_jsonl(RESULTS / 'coupling_sweep_heldout.jsonl')
    for r in sorted(rows, key=lambda r: r['shape']):
        i, j, k, l = r['shape']
        d = delta(r['same_wt'], r['cross_wt'])
        got, want = max(x[1] for x in d), i * min(l, i // 2)
        worst = min(x[1] / x[2] for x in d)
        plateau = [x[1] for x in d if x[0] == 0][0]
        exact += got == want
        within += abs(got - want) <= 0.05 * want
        ok16 = worst >= -0.05 and plateau == 0
        p16 += ok16
        print(r['shape'], 'max dS', got, 'predicted', want, f'min dS/S_same {worst:.3f}', 'plateau dS', plateau,
              '' if got == want else 'MISS', '' if ok16 else 'P16 FAIL')
    n = len(rows)
    print(f'P15 exact {exact}/{n} (need >= 28); P15p within 5% {within}/{n}; P16 {p16}/{n}')


def p18():
    curves = defaultdict(dict)
    for r in read_jsonl(RESULTS / 'p18.jsonl'):
        curves[tuple(r['shape'])][r['roles']] = r['points']
    a = b = c_exact = c_near = d = e = 0
    n_mixed = 0
    for shape, cv in sorted(curves.items()):
        n, j, k, l = shape
        for mixed, pure in (('kki', 'kkk'), ('ikk', 'kkk'), ('iik', 'kkk'), ('kkki', 'kkkk'), ('kkii', 'kkkk')):
            ds = delta(cv[pure], cv[mixed])
            nb = mixed.count('i')
            n_mixed += 1
            ok_a = all(-nb * n * l <= x <= nb * k * l for _, x, _ in ds)
            ok_b = all(x >= -0.05 * s for _, x, s in ds)
            a += ok_a
            b += ok_b
            if not (ok_a and ok_b):
                print(shape, mixed, 'P18a' if not ok_a else '', 'P18b' if not ok_b else '',
                      'min', min(x for _, x, _ in ds), 'max', max(x for _, x, _ in ds))
        got = max(x for _, x, _ in delta(cv['kkk'], cv['kki']))
        want = n * min(l, n // 2)
        c_exact += got == want
        c_near += abs(got - want) <= 0.05 * want
        m1 = max(x for _, x, _ in delta(cv['kkkk'], cv['kkki']))
        m2 = max(x for _, x, _ in delta(cv['kkkk'], cv['kkii']))
        d += m2 >= m1
        e += cv['kki'] == cv['iik']
        print(shape, 'kki max dS', got, 'pred', want, '| 4-consumer max dS 1 minority', m1, '2 minority', m2,
              '| kki==iik', cv['kki'] == cv['iik'], '| kki==ikk', cv['kki'] == cv['ikk'])
    s = len(curves)
    print(f'P18a {a}/{n_mixed}  P18b {b}/{n_mixed}  P18c exact {c_exact}/{s} (need >=10), within 5% {c_near}/{s}'
          f'  P18d {d}/{s}  P18e {e}/{s}')


def p19(path):
    pure, minorities = 'kkkkkk', (('kkkkki', 1), ('kkkkii', 2), ('kkkiii', 3))
    curves = {}
    for r in read_jsonl(path):
        key = (tuple(r['shape']), r['roles'])
        assert key not in curves, key
        curves[key] = r['points']
    expected = {(tuple(s), r) for s in p19_shapes() for r in P19_ROLES}
    print('records', len(curves), 'missing', sorted(expected - set(curves)))
    a_exact = a_strict = a_strict_n = c_ok = d_ok = d_n = 0
    b_ok = {'kkkkki': 0, 'kkkkii': 0}
    for shape in p19_shapes():
        n, _, _, l = shape
        cv = {r: curves.get((tuple(shape), r)) for r in P19_ROLES}
        if None in cv.values():
            continue
        q_hi = max(t - p[-1][1] for p in cv.values() for _, t in p)
        steps = {r: gap_steps(cv[pure], cv[r], q_hi) for r, _ in minorities}
        mx = {r: max(g for *_, g in steps[r]) for r in steps}
        width = {r: positive_width(steps[r]) for r in steps}
        pred = {r: n * min(ceil(b / 2) * l, n // 2) for r, b in minorities}
        a_exact += mx['kkkiii'] == pred['kkkiii']
        if l <= n // 4:
            a_strict_n += 1
            a_strict += mx['kkkiii'] > mx['kkkkii']
        for r in b_ok:
            b_ok[r] += mx[r] == pred[r]
        c_ok += width['kkkkki'] < width['kkkkii'] < width['kkkiii']
        for r, b in minorities:
            d_n += 1
            d_ok += all(-b * n * l <= g <= b * n * l for *_, g in steps[r])
        print(shape, 'max', mx, 'pred', pred, 'positive width', width, 'q_hi', q_hi)
    print(f'P19a exact {a_exact}/8 (need 7), strictly above kkkkii {a_strict}/{a_strict_n} (need all 6)')
    print(f'P19b {b_ok} (need 7 each)')
    print(f'P19c ordered widths {c_ok}/8 (need 7)')
    print(f'P19d bound {d_ok}/{d_n}')


def ffn(paths):
    parts = {}
    for path in paths:
        for record in read_jsonl(path):
            parts[record['part']] = record['points']
    _, _, ffm = ffn_case()

    def report(name, model):
        rows = compare_to_reference(model, ffm)
        lower = [row for row in rows if row[2] < 0]
        higher = [row for row in rows if row[2] > 0]
        print(f'{name}: lower at {len(lower)} breakpoints {lower}')
        print(f'{" " * len(name)}  higher at {len(higher)} breakpoints {higher}')

    for name in ('graph', 'nowt', 'chain'):
        if name in parts:
            report(name, parts[name])
    for prefix in ('ffm_like:', 'ffm_like_si:'):
        like = {k: v for k, v in parts.items() if k.startswith(prefix)}
        if not like:
            continue
        union = [p[:2] for p in pareto((c, t, ()) for v in like.values() for c, t in v)]
        report(f'{prefix} ({len(like)}/8 subsets)', union)
        if len(like) < 8:
            print('  incomplete union: missing subsets can only lower it')


def main(argv):
    command, args = (argv[0], argv[1:]) if argv else ('help', [])
    if command == 'sweep':
        sweep(args[0])
    elif command in ('p15', 'p18'):
        {'p15': p15, 'p18': p18}[command]()
    elif command == 'p19':
        p19(args[0])
    elif command == 'ffn':
        ffn(args)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
