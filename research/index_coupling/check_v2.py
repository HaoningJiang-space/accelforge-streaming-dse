"""Grammar v2 vs v1 on one census case (GRAMMAR_V2.md section 6, check 3).

Computes both root curves with the exact cut DP, replays every v2 frontier
point with the cell-level executor, and checks v2 <= v1 pointwise. Run under
caps on the experiment server, one process per case.

Usage: python -m research.index_coupling.check_v2 CASE OUT_DIR [SECONDS] [MEM_GIB]
"""
import json
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time

from research.index_coupling.census_tools import graph_of
from research.index_coupling.graph.analysis import traffic_at
from research.index_coupling.graph.curve import curve
from research.index_coupling.simulate_nest import simulate


def timeout(*_):
    raise TimeoutError('v2 check wall-time limit')


def main(case, out, seconds=600, mem_gib=4):
    if platform.system() == 'Linux':
        cap = int(mem_gib * 2**30)
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    graph = graph_of(case)
    record = dict(case=case, revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  budgets=dict(seconds=seconds, mem_gib=mem_gib), status='running')
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        times = {}
        for leaf in ('v1', 'v2'):
            start = time.monotonic()
            points = curve(graph, witness=leaf == 'v2', partitions='dp', scalar_leaf=leaf)
            times[leaf] = time.monotonic() - start
            record[leaf] = [list(p[:2]) for p in points]
            if leaf == 'v2':
                witnesses = points
        replays = []
        for c, q, w in witnesses:
            run = simulate(graph, w, scalar_leaf='v2')
            replays.append(run['valid'] and (run['peak'], run['traffic']) == (c, q))
        top = max(c for c, _ in record['v1'] + record['v2'])
        better = [c for c in range(top + 1) if traffic_at(c, record['v2']) < traffic_at(c, record['v1'])]
        worse = [c for c in range(top + 1) if traffic_at(c, record['v2']) > traffic_at(c, record['v1'])]
        record.update(status='complete', seconds=times, replay_exact=sum(replays), replay_total=len(replays),
                      v2_better_at=better, v2_worse_at=worse)
    except TimeoutError:
        record.update(status='timeout')
    except MemoryError:
        record.update(status='memory')
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / f'{case}.v2.json').write_text(json.dumps(record, indent=1) + '\n')
    print(json.dumps({k: record.get(k) for k in ('case', 'status', 'replay_exact', 'replay_total',
                                                  'v2_better_at', 'v2_worse_at', 'seconds')}))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], *(float(a) for a in sys.argv[3:5]))
