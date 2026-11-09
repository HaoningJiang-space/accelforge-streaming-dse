"""Score P15/P16 (PROTOCOL.md) on results/coupling_sweep_heldout.jsonl."""
import json
from pathlib import Path

from research.index_coupling.sweep_analysis import delta

if __name__ == '__main__':
    exact = within = p16 = 0
    rows = [json.loads(line) for line in (Path(__file__).parent / 'results/coupling_sweep_heldout.jsonl').open()]
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
