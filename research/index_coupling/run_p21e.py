"""Frozen P21e runner: one (case, arm) per process. See PROTOCOL.md (P21e).

Usage (designated server): python -m research.index_coupling.run_p21e CASE ARM
  CASE in 0..31, ARM in {free, tied}. Prints one JSON record. Run under an
  8 GiB address-space limit and an 1800 s wall limit (enforced here too).
  python -m research.index_coupling.run_p21e --list   prints the case table.
"""
import json
import platform
import resource
import signal
import subprocess
import sys
import time
from itertools import product

from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import residual
from research.index_coupling.simulate_nest import simulate

ABOVE = ((4, 4, 6), (8, 8, 12), (4, 8, 12), (16, 4, 8), (2, 4, 16), (6, 4, 12), (16, 2, 8), (4, 4, 16))
BELOW = ((4, 6, 4), (8, 12, 8), (4, 12, 8), (16, 8, 4), (8, 16, 4), (12, 8, 4), (6, 12, 8), (16, 16, 8))
DEPTH = 6
CASES = tuple((shape, reads_x) for shape, reads_x in product(ABOVE + BELOW, (False, True)))


def timeout(*_):
    raise TimeoutError


def main(case, arm):
    shape, reads_x = CASES[case]
    graph = residual(*shape, DEPTH, reads_x)
    options = dict(whole_span_cuts=range(2, len(graph.ops))) if arm == 'tied' else {}
    record = dict(case=case, shape=list(shape), depth=DEPTH, reads_x=reads_x, arm=arm,
                  source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  python=platform.python_version(), status='running')
    start = time.time()
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(1800)
    try:
        points = curve(graph, witness=True, partitions='dp', **options)
        search = time.time() - start
        replays = []
        for c, q, w in points:
            a = simulate(graph, w)
            replays.append(a['valid'] and (a['peak'], a['traffic']) == (c, q))
        record.update(status='complete' if all(replays) else 'replay_failure',
                      points=[list(p[:2]) for p in points], replay_exact=sum(replays),
                      search_seconds=search, witnesses=[[c, q, w] for c, q, w in points])
    except TimeoutError:
        record.update(status='timeout')
    except MemoryError:
        record.update(status='memory')
    finally:
        signal.alarm(0)
    record.update(seconds=time.time() - start,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    print(json.dumps(record, default=list))


if __name__ == '__main__':
    if sys.argv[1] == '--list':
        for i, (shape, reads_x) in enumerate(CASES):
            print(i, *shape, int(reads_x))
    else:
        main(int(sys.argv[1]), sys.argv[2])
