"""Run P11-P13 (PROTOCOL.md): write-through switch and chain view."""
import json
import sys
import time
from pathlib import Path

from research.index_coupling.chain_view import chain_curve
from research.index_coupling.compare_curves import at, cases
from research.index_coupling.curve_model import curve
from research.index_coupling.nest_model import ffn

R = Path(__file__).parent / 'results'


def ffn_case():
    for line in (R / 'upstream_nodetail.jsonl').read_text().splitlines():
        record = json.loads(line)
        if record['case'] == 'ffn_full_copy':
            return 'FFN M8 D4 F8', ffn(8, 4, 8), [tuple(p) for p in record['frontier']]


def pts(points):
    return [list(p[:2]) for p in points]


if __name__ == '__main__':
    which = sys.argv[1:] or ['small', 'ffn']
    todo = (list(cases()) if 'small' in which else []) + ([ffn_case()] if 'ffn' in which else [])
    for name, graph, ffm in todo:
        t0 = time.time()
        on, off, chain = curve(graph), curve(graph, write_through=False), chain_curve(graph)
        print(json.dumps({
            'case': name, 'seconds': round(time.time() - t0, 1), 'ffm': ffm,
            'graph': pts(on), 'no_write_through': pts(off), 'chain': pts(chain),
            'vs_ffm': [[c, t, at(c, on) - t, at(c, off) - t, at(c, chain) - t] for c, t in ffm],
        }), flush=True)
