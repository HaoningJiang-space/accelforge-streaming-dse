"""Group exclusive DP work of an archived census case by (stage, op span)."""
import gzip, json, sys
from collections import Counter
from research.index_coupling.decode_census import CASES
from research.index_coupling.response.chains import archived
out, case = sys.argv[1], sys.argv[2]
builder, m = CASES[case]; g = builder(m)
b = json.load(gzip.open(f'{out}/{case}.baseline.json.gz', 'rt'))
work, kind = Counter(), {}
for n in b['nodes']:
    s = n['state']; key = (s['stage'], ' '.join(s['ops']))
    work[key] += n['work']['dp_transitions']
    if archived(g, s, unit_rows=True) is not None:
        kind[key] = 'unit-chain'
    elif archived(g, s) is not None:
        kind.setdefault(key, 'chain')
total = sum(work.values())
print(case, 'total dp_transitions', total)
for (stage, ops), w in work.most_common(12):
    print(f'{w/total:6.1%} {stage:5} {kind.get((stage, ops), "-"):10} {ops}')
