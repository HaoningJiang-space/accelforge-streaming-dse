"""Within each (span, ext, external∩cut, owned, stage) class, how do curves differ across private external sets?"""
import gzip, json, sys, resource
from collections import defaultdict, Counter
resource.setrlimit(resource.RLIMIT_AS, (6 * 2**30, 6 * 2**30))
out_dir, case = sys.argv[1], sys.argv[2]
rec = json.load(open(f'{out_dir}/{case}.json'))
access = {o: a for o, a in rec['operators']}; order = [o for o, _ in rec['operators']]
nodes = json.load(gzip.open(f'{out_dir}/{case}.baseline.json.gz', 'rt'))['nodes']
cutc = {}
def cut(span):
    if span not in cutc:
        t_in = {t for o in span for t in access[o]}
        t_out = {t for o in order if o not in span for t in access[o]}
        cutc[span] = t_in & t_out
    return cutc[span]
cls = defaultdict(list)
for n in nodes:
    s = n['state']; span = tuple(s['ops']); x = frozenset(s['external'])
    cls[(span, tuple(s['ext']), x & cut(span), frozenset(s['owned']), s['stage'], s['constrained'])].append((x - cut(span), n))
tot = sum(n['work']['dp_transitions'] for n in nodes)
kept = sum(max(n['work']['dp_transitions'] for _, n in v) for v in cls.values())
print(case, 'classes', len(cls), 'states', len(nodes), 'work if one solve per class (max member)', f'{kept/tot:.3f}')
# relation tests between members and the member with empty private part
kinds = Counter()
for key, v in cls.items():
    base = [n for p, n in v if not p]
    if not base or len(v) == 1: continue
    b = [tuple(p) for p in base[0]['points']]
    for p, n in v:
        if not p: continue
        c = [tuple(q) for q in n['points']]
        if c == b: kinds['identical'] += 1
        elif not c or not b: kinds['one empty'] += 1
        elif len(c) == len(b) and len({cc[1]-bb[1] for cc, bb in zip(c, b)}) == 1 and all(cc[0] == bb[0] for cc, bb in zip(c, b)): kinds['Q shift'] += 1
        elif len(c) == len(b) and len({cc[0]-bb[0] for cc, bb in zip(c, b)}) == 1 and all(cc[1] == bb[1] for cc, bb in zip(c, b)): kinds['C shift'] += 1
        else: kinds['other'] += 1
print(dict(kinds))
