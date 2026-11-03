"""Time and trace only final membership construction/labeling on fixed cohorts.

Peak traced allocation includes NumPy buffers, NOT process RSS or search state.
Inputs are prebuilt and excluded from both paths' measured allocation.
"""
import gc
import json
from pathlib import Path
import statistics
import sys
import time
import tracemalloc

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from accelforge.mapper.FFM._pareto_df.target_membership import build_target_membership
from accelforge.mapper.FFM._pareto_df.capacity_membership import pack_exclusions


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--rows', type=int, default=32768)
    a = p.parse_args()
    report = dict(rows=a.rows, synthetic=True, results=[])
    for k in (64, 256, 1024):
        rng = np.random.default_rng(821)
        groups = [(np.flatnonzero(rng.random(a.rows) < .25),
                   tuple(range(start, min(start + k // 4, k))))
                  for start in range(0, k, max(1, k // 16))]
        fractions = [(i + 1) / k for i in range(k)]

        def construct(mode):
            membership = build_target_membership(a.rows, k, groups, mode)
            return pack_exclusions('GlobalBuffer', fractions, membership, a.rows)

        reference = construct('excluded')
        actual = construct('packed')
        assert reference.keys() == actual.keys()
        assert all(np.array_equal(reference[c], actual[c]) for c in reference)
        del reference, actual
        samples = {'excluded': [], 'packed': []}
        for repeat in range(5):
            for mode in (('excluded','packed') if repeat % 2 == 0 else ('packed','excluded')):
                start = time.perf_counter()
                result = construct(mode)
                samples[mode].append(time.perf_counter()-start)
                del result
        peaks = {}
        for mode in samples:
            gc.collect()
            tracemalloc.start()
            result = construct(mode)
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peaks[mode] = dict(current_bytes=current, peak_bytes=peak,
                               word_payload_bytes=sum(v.nbytes for v in result.values()))
            del result
        report['results'].append(dict(targets=k, exact=True, seconds=samples,
            median_seconds={m:statistics.median(t) for m,t in samples.items()}, traced_allocations=peaks))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
