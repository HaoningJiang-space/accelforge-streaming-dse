import gzip, json, sys, resource
from collections import defaultdict, Counter
resource.setrlimit(resource.RLIMIT_AS, (6 * 2**30, 6 * 2**30))
out_dir, case = sys.argv[1], sys.argv[2]
rec = json.load(open(f'{out_dir}/{case}.json'))
access = {o: a for o, a in rec['operators']}; order = [o for o, _ in rec['operators']]
nodes = json.load(gzip.open(f'{out_dir}/{case}.baseline.json.gz', 'rt'))['nodes']
cc = {}
def cut(span):
    if span not in cc:
        t_in = {t for o in span for t in access[o]}; t_out = {t for o in order if o not in span for t in access[o]}
        cc[span] = t_in & t_out
    return cc[span]
cls = defaultdict(list)
for n in nodes:
    s = n['state']; span = tuple(s['ops']); x = frozenset(s['external'])
    cls[(span, tuple(s['ext']), x & cut(span), frozenset(s['owned']), s['stage'], s['constrained'])].append(n)
tot = sum(n['work']['dp_transitions'] for n in nodes)
distinct = 0; work_distinct = 0; hist = Counter()
for v in cls.values():
    seen = {}
    for n in v:
        k = json.dumps(n['points'])
        if k not in seen: seen[k] = n['work']['dp_transitions']
    distinct += len(seen); work_distinct += sum(seen.values())
    hist[min(len(seen), 9)] += 1
print(case, 'states', len(nodes), 'classes', len(cls), 'distinct curves', distinct,
      f'work if each distinct curve solved once {work_distinct/tot:.3f}', 'curves/class hist', dict(sorted(hist.items())))
