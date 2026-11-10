"""Score frozen P21e from saved records (DIR/<case>_<arm>.json). See PROTOCOL.md.

Usage: python -m research.index_coupling.score_p21e DIR
Exits 0 only if all three scored predictions pass.
"""
import json
import sys
from pathlib import Path

from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.run_p21e import CASES


def load(directory, case, arm):
    path = Path(directory) / f'{case:02d}_{arm}.json'
    if not path.exists():
        return None
    record = json.loads(path.read_text())
    return record if record.get('status') == 'complete' else None


def plateau_capacity(points):
    return min(c for c, q in points if q == points[-1][1])


def diagnostic(record_free, gaps):
    # Does a free witness at the smallest gap capacity have a group with EH0,
    # without EX, that loops over L?
    first = gaps[0]
    witness = max((p for p in record_free['witnesses'] if p[0] <= first), key=lambda p: p[0])[2]
    return any(step[0] == 'loop' and 'EH0' in step[1] and 'EX' not in step[1] and step[2] == 'L'
               for step in witness)


def main(directory):
    rows, a, b, c = [], 0, 0, 0
    for case, (shape, reads_x) in enumerate(CASES):
        free, tied = load(directory, case, 'free'), load(directory, case, 'tied')
        above = shape[2] > shape[1]
        row = dict(case=case, shape=shape, reads_x=reads_x, l_gt_k=above, complete=bool(free and tied))
        if free and tied:
            f, t = free['points'], tied['points']
            hi = max(p[0] for p in f + t)
            gaps = [x for x in range(hi + 1) if traffic_at(x, t) != traffic_at(x, f)]
            higher = [x for x in gaps if traffic_at(x, t) > traffic_at(x, f)]
            lower = [x for x in gaps if traffic_at(x, t) < traffic_at(x, f)]
            same_tail = f[-1][1] == t[-1][1]
            row.update(gap_capacities=len(gaps), tied_higher=len(higher), tied_lower=len(lower),
                       free_plateau=plateau_capacity(f), tied_plateau=plateau_capacity(t),
                       same_min_traffic=same_tail)
            if above:
                a += bool(higher) and not lower
                c += same_tail and row['tied_plateau'] > row['free_plateau']
                row['diagnostic_eh0_l_loop'] = diagnostic(free, higher) if higher else None
            else:
                b += not gaps and same_tail
        rows.append(row)
        print(json.dumps(row))
    verdict = dict(p21e_a=f'{a}/16 (need 15)', p21e_b=f'{b}/16 (need 15)', p21e_c=f'{c}/16 (need 15)',
                   complete=sum(r['complete'] for r in rows))
    print(json.dumps(verdict))
    return 0 if a >= 15 and b >= 15 and c >= 15 else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
