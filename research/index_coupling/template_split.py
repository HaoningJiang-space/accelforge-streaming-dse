"""Train/test check: templates learned on small matmul shapes reproduce exact frontiers on large ones.

Train: every shape in {1,2,4,8}^3. Test: every shape in {1,16,64,512}^3 with an extent >= 16.
Run with a fixed PYTHONHASHSEED; tie-breaking among equal-cost witnesses depends on it.
"""
import itertools, time
from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import Graph
from research.index_coupling.template_census import template, OPTIONS
from research.index_coupling.template_eval import frontier
mm = lambda i, j, k: Graph(dict(I=i, J=j, K=k), [('E', {'A': ('I', 'J'), 'B': ('J', 'K'), 'C': ('I', 'K')})])
learn = {}
for shape in itertools.product((1, 2, 4, 8), repeat=3):
    for _, _, w in curve(mm(*shape), witness=True, **OPTIONS):
        learn[template(w)] = None
print('templates learned from 64 small shapes:', len(learn))
ok = bad = 0; te = tp = 0
for shape in itertools.product((1, 16, 64, 512), repeat=3):
    if max(shape) < 16: continue
    g = mm(*shape); t = time.time()
    exact = [p[:2] for p in curve(g, **OPTIONS)]; te += time.time() - t; t = time.time()
    pred = list(frontier(g, list(learn))); tp += time.time() - t
    if exact == pred: ok += 1
    else:
        bad += 1
        if bad <= 3: print('MISMATCH', shape, exact[:4], pred[:4])
print(f'test shapes: equal {ok}, mismatch {bad}; exact search {te:.2f}s, templates {tp:.2f}s')
