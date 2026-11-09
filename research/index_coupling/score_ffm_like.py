"""Score P14: FFM-like curve versus FFM's archived best on the union of breakpoints."""
import json
import sys

from research.index_coupling.compare_curves import at, cases
from research.index_coupling.classify import ffn_case
from research.index_coupling.curve_model import curve
from research.index_coupling.ffm_like import ffm_like_curve

if __name__ == '__main__':
    todo = list(cases()) if 'small' in sys.argv[1:] else [ffn_case()]
    for name, graph, ffm in todo:
        model = ffm_like_curve(graph)
        caps = sorted({c for c, _ in ffm} | {c for c, _ in model})
        diffs = [[c, at(c, ffm), at(c, model) - at(c, ffm)] for c in caps
                 if at(c, ffm) < float('inf') and at(c, model) != at(c, ffm)]
        full = [list(p[:2]) for p in curve(graph)] if 'attention' in name else None
        print(json.dumps({'case': name, 'ffm_like': [list(p) for p in model], 'diffs': diffs,
                          'equals_graph_curve': full == [list(p) for p in model] if full else None}),
              flush=True)
