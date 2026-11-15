import gzip, json, sys, resource, random
from collections import defaultdict
resource.setrlimit(resource.RLIMIT_AS, (6 * 2**30, 6 * 2**30))
out_dir, case = sys.argv[1], sys.argv[2]
rec = json.load(open(f'{out_dir}/{case}.json'))
access = {o: a for o, a in rec['operators']}; order = [o for o, _ in rec['operators']]
nodes = json.load(gzip.open(f'{out_dir}/{case}.baseline.json.gz', 'rt'))['nodes']
def cut(span):
    t_in = {t for o in span for t in access[o]}; t_out = {t for o in order if o not in span for t in access[o]}
    return t_in & t_out
cls = defaultdict(list)
for n in nodes:
    s = n['state']; span = tuple(s['ops']); x = frozenset(s['external']); c = cut(span)
    cls[(span, tuple(s['ext']), x & c, frozenset(s['owned']), s['stage'], s['constrained'])].append((x - c, n))
random.seed(1); shown = 0
keys = [k for k, v in cls.items() if len(k[0]) <= 4 and len(v) > 2 and any(not p for p, _ in v)]
random.shuffle(keys)
for k in keys:
    v = cls[k]; base = [n for p, n in v if not p][0]
    others = [(p, n) for p, n in v if p and n['points'] and n['points'] != base['points']]
    if not others: continue
    print('span', ' '.join(k[0]), 'ext', k[1], 'cutX', sorted(k[2]), 'owned', sorted(k[3]), k[4])
    print('   {}       :', base['points'])
    for p, n in sorted(others, key=lambda t: len(t[0]))[:5]:
        print('  ', sorted(p), ':', n['points'])
    shown += 1
    if shown >= 6: break
