"""Measure one real template in one process; never use profiling instrumentation."""
import argparse
import copy
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from research.tracking_audit import benchmark_parametric_template as b
from research.tracking_audit import parametric_operator as op
from research.tracking_audit.benchmark_parametric_operator import FAMILY
from research.tracking_audit.factorized_region_experiment import SharedEvaluationRegions
from research.tracking_audit.parametric_template import Box, RegionEnumerator


def run(index, mode, output):
    b.common.af.set_n_parallel_jobs(1)
    b.common.clear_switches()
    programs = op.prepare_all(256, tuple(hi for _, hi in FAMILY.ranges))
    objectives, axes = b.parameterize(programs[index])
    family = Box((*FAMILY.ranges[:2], tuple(8*x for x in FAMILY.ranges[2])))
    b.frontier(np.array([[1.,2.,3.],[2.,1.,2.]]))
    cls = RegionEnumerator if mode == 'baseline' else SharedEvaluationRegions
    engine = cls(b.tiles, copy.deepcopy(objectives), family, axes=axes,
                 **copy.deepcopy(programs[index].kwargs))
    start = time.perf_counter()
    engine.build()
    elapsed = time.perf_counter() - start
    # Fingerprint exact ordered assignments, dtype, region boxes and history.
    h = hashlib.sha256()
    for leaf in engine.leaves:
        h.update(str((leaf.choices.dtype.str, leaf.choices.shape, leaf.targets,
                      sorted([sorted(map(str, x)) for x in leaf.history]))).encode())
        h.update(leaf.choices.tobytes())
    report = dict(template=index, mode=mode, build_s=elapsed, states=len(engine.leaves),
                  signature=h.hexdigest(), peak_rss_gib=b.common.peak_rss_gb()['main'],
                  counters=engine.stats)
    if mode == 'shared':
        report['candidate_ids'] = engine.pool.count
        report['cache'] = engine.cache_stats
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--template', type=int, required=True)
    p.add_argument('--mode', choices=('baseline', 'shared'), required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    run(args.template, args.mode, args.output)
