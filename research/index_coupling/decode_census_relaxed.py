"""Upper bound: work under unit-M chain states if rank recurrence were allowed (no closed form claimed)."""
import gzip, inspect, json, sys
from research.index_coupling.decode_census import CASES
from research.index_coupling.response import chains, dag
src = inspect.getsource(chains.recognise)
line = "    if len(set(distinct)) != len(distinct):\n        return None\n"
assert line in src
ns = dict(vars(chains)); exec(src.replace(line, ''), ns); relaxed = ns['recognise']
out, case = sys.argv[1], sys.argv[2]
builder, m = CASES[case]; g = builder(m)
b = json.load(gzip.open(f'{out}/{case}.baseline.json.gz', 'rt'))
nodes = dict(enumerate(b['nodes'])); children = {}
for e in b['edges']: children.setdefault(e['parent'], []).append(e['child'])
def term(fn):
    t = set()
    for i, n in nodes.items():
        s = n['state']
        if s['stage'] == 'solve' and not s['constrained'] and fn(g, tuple(s['ops']), tuple(s['ext']), frozenset(s['external']), frozenset(s['owned']), sorted(g.sizes), True) is not None:
            t.add(i)
    return dag.terminal_work(dict(root=b['root']), nodes, children, t)['dp_transitions']
print(case, 'strict', term(chains.recognise), 'relaxed', term(relaxed))
