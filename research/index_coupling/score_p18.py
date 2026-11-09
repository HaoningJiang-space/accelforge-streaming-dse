"""Score P18 (PROTOCOL.md) from results/p18.jsonl."""
import json
from collections import defaultdict
from pathlib import Path

from research.index_coupling.sweep_analysis import delta

if __name__ == '__main__':
    curves = defaultdict(dict)
    for line in (Path(__file__).parent / 'results/p18.jsonl').open():
        r = json.loads(line)
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
