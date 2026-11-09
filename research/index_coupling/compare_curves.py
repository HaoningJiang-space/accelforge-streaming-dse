"""Compare curve_model frontiers with every saved FFM frontier (small graphs)."""
import json
from pathlib import Path

from research.index_coupling.curve_model import curve
from research.index_coupling.nest_model import attention, coupling

R = Path(__file__).parent / 'results'


def at(cap, points):
    return min((t for c, t, *_ in points if c <= cap), default=float('inf'))


def cases():
    shapes = {'n4': (4,) * 4, 'n8': (8,) * 4, 'n16': (16,) * 4, 'T1': (32,) * 4, 'T2': (64, 8, 8, 8),
              'T3': (8, 32, 32, 32), 'C1': (16, 4, 32, 8), 'C2': (8, 16, 4, 32)}
    for key, dims in shapes.items():
        for variant in ('same', 'cross'):
            report = json.loads((R / f'{key}_{variant}.json').read_text())
            yield f'{key} {variant}', coupling(*dims, variant == 'cross'), \
                [(p['capacity_bytes'], p['traffic_bytes']) for p in report['graph']['points']]
    for line in (R / 'attention_heldout.jsonl').read_text().splitlines():
        record = json.loads(line)
        d = record['dims']
        yield f"attention {d['M']},{d['P']},{d['E']},{d['F']}", attention(d['M'], d['P'], d['E'], d['F']), \
            [tuple(p) for p in record['frontier']]


if __name__ == '__main__':
    total = exact = 0
    for name, graph, ffm in cases():
        model = curve(graph)
        diffs = [(c, at(c, model) - t) for c, t in ffm]
        better = [d for d in diffs if d[1] < -1e-9]
        worse = [d for d in diffs if d[1] > 1e-9]
        total += len(diffs)
        exact += len(diffs) - len(better) - len(worse)
        print(f'{name:22s} FFM points {len(diffs):2}  model better {better}  model worse {worse}', flush=True)
    print(f'total {total} points, {exact} exact')
