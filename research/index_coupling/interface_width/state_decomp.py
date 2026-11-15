"""Decompose archived baseline states of one census case by (span, extents, external, owned)."""
import gzip, json, sys, resource
from collections import defaultdict, Counter
resource.setrlimit(resource.RLIMIT_AS, (6 * 2**30, 6 * 2**30))
out_dir, case = sys.argv[1], sys.argv[2]
rec = json.load(open(f'{out_dir}/{case}.json'))
access = {o: a for o, a in rec['operators']}
order = [o for o, _ in rec['operators']]
b = json.load(gzip.open(f'{out_dir}/{case}.baseline.json.gz', 'rt'))
nodes = b['nodes']
tot = sum(n['work']['dp_transitions'] for n in nodes)
by_span = defaultdict(list)
for n in nodes:
    s = n['state']; by_span[tuple(s['ops'])].append(n)
def cut(span):
    inside = set(span)
    t_in = {t for o in span for t in access[o]}
    t_out = {t for o in order if o not in inside for t in access[o]}
    return t_in & t_out, t_in
rows = []
for span, ns in by_span.items():
    c, t_in = cut(span)
    ext = {tuple(n['state']['ext']) for n in ns}
    exts = Counter(frozenset(n['state']['external']) for n in ns)
    ext_cut = {frozenset(n['state']['external']) & c for n in ns}
    ext_priv = {frozenset(n['state']['external']) - c for n in ns}
    own = {frozenset(n['state']['owned']) for n in ns}
    stg = Counter(n['state']['stage'] for n in ns)
    useful = sum(1 for n in ns if n['points'])
    work = sum(n['work']['dp_transitions'] for n in ns)
    rows.append((work, len(span), ' '.join(span), len(ns), useful, dict(stg), len(ext), len(exts), len(ext_cut), len(ext_priv), len(own), len(c), len(t_in)))
rows.sort(reverse=True)
print(f'case {case} states {len(nodes)} spans {len(by_span)} dp {tot} useful {sum(1 for n in nodes if n["points"])}')
print('work% | span | states useful stage | #ext #externalSets (#cutPart #privatePart) #owned | w=|cut| |tensors|')
for r in rows[:25]:
    print(f'{100*r[0]/tot:5.1f}% | {r[2]} | {r[3]} {r[4]} {r[5]} | ext {r[6]} xs {r[7]} ({r[8]} cut, {r[9]} priv) own {r[10]} | w {r[11]} T {r[12]}')
# global: product decomposition
print('distinct (span,ext)', len({(tuple(n['state']['ops']), tuple(n['state']['ext'])) for n in nodes}))
print('distinct (span,ext,external)', len({(tuple(n['state']['ops']), tuple(n['state']['ext']), frozenset(n['state']['external'])) for n in nodes}))
print('distinct (span,ext,external∩cut,owned,stage)', len({(tuple(n['state']['ops']), tuple(n['state']['ext']), frozenset(n['state']['external']) & cut(tuple(n['state']['ops']))[0], frozenset(n['state']['owned']), n['state']['stage']) for n in nodes}))
