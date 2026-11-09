"""Score P12 and P14-FFN from ffn_parts.py outputs (union of breakpoints).

Usage: python -m research.index_coupling.score_ffn part_*.json
"""
import json
import sys

from research.index_coupling.classify import ffn_case
from research.index_coupling.compare_curves import at
from research.index_coupling.curve_model import pareto


def compare(name, model, ffm):
    caps = sorted({c for c, _ in ffm} | {c for c, _ in model})
    rows = [(c, at(c, ffm), at(c, model) - at(c, ffm)) for c in caps if at(c, ffm) < float('inf')]
    lower = [(c, q, d) for c, q, d in rows if d < 0]
    higher = [(c, q, d) for c, q, d in rows if d > 0]
    print(f'{name}: lower at {len(lower)} breakpoints {lower}')
    print(f'{" " * len(name)}  higher at {len(higher)} breakpoints {higher}')


if __name__ == '__main__':
    parts = {}
    for path in sys.argv[1:]:
        for line in open(path):
            record = json.loads(line)
            parts[record['part']] = record['points']
    _, _, ffm = ffn_case()
    for name in ('graph', 'nowt', 'chain'):
        if name in parts:
            compare(name, parts[name], ffm)
    like = [p for k, v in parts.items() if k.startswith('ffm_like') for p in v]
    if sum(k.startswith('ffm_like') for k in parts) == 8:
        compare('ffm_like', [p[:2] for p in pareto((c, t, ()) for c, t in like)], ffm)
    print('seconds', {k: v for k, v in parts.items() if False} or '')
