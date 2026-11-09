"""One FFN M8 D4 F8 curve per process, for P12 and P14-FFN (server runner).

Parts: graph, nowt, chain, and ffm_like:<materialized intermediates joined by +>
(empty for none). Each prints one JSON line; score_ffn.py combines them.
"""
import json
import sys
import time

from research.index_coupling.chain_view import chain_curve
from research.index_coupling.curve_model import curve
from research.index_coupling.ffm_like import consumers, separate
from research.index_coupling.nest_model import ffn

if __name__ == '__main__':
    part = sys.argv[1]
    # Optional capacity cap: exact up to the cap (see curve()), and above FFM's largest
    # saved capacity (147) it cannot change any P12/P14-FFN comparison.
    kw = {'max_capacity': int(sys.argv[2])} if len(sys.argv) > 2 else {}
    graph = ffn(8, 4, 8)
    t = time.time()
    if part == 'graph':
        points = curve(graph, **kw)
    elif part == 'nowt':
        points = curve(graph, write_through=False, **kw)
    elif part == 'chain':
        points = chain_curve(graph, **kw)
    else:
        chosen = {x for x in part.split(':', 1)[1].split('+') if x}
        produced = {list(graph.access[op])[-1] for op in graph.ops}
        inputs = {x for x in graph.tensors(graph.ops) if len(consumers(graph, x)) > 1 and x not in produced}
        points = curve(separate(graph, inputs | chosen), split_shared=False, **kw)
    print(json.dumps({'part': part, 'seconds': round(time.time() - t), 'points': [list(p[:2]) for p in points]}))
