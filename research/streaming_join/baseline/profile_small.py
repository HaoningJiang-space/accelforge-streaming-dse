import cProfile
import io
import json
import os
import pstats
import resource
import sys
import time

def no_child_process(event, args):
    if event in {'os.fork', 'os.forkpty', 'os.posix_spawn', 'subprocess.Popen'}:
        raise RuntimeError('Child processes disabled for this bounded experiment: ' + event)
sys.addaudithook(no_child_process)

import numpy as np
import accelforge as af
from accelforge.mapper.FFM.main import make_pmappings, join_pmappings

af.set_n_parallel_jobs(1)
glu = os.path.expanduser('~/graph_dse/accelforge/examples/workloads/transformers/_feedforward_types/glu_standalone.yaml')
spec = af.Spec.from_yaml(af.examples.arches.tpu_v4i, glu, jinja_parse_data={
    'BATCH_SIZE': 1, 'N_NEW_TOKENS': 128, 'N_HIDDEN_DIMS': 256, 'N_FF_DIMS': 512})
spec.arch.find('GlobalBuffer').size = 0.5 * 1024 * 1024 * 8
for action in spec.arch.find('MainMemory').actions:
    action.throughput_scale = 1.0
spec.mapper.metrics = af.Metrics.ENERGY | af.Metrics.LATENCY
start = time.perf_counter()
pm = make_pmappings(spec, print_progress=False)
made = time.perf_counter()
profiler = cProfile.Profile()
profiler.enable()
res = join_pmappings(pm, spec.mapper.metrics, print_progress=False)
profiler.disable()
joined = time.perf_counter()
e = res.data['Total<SEP>energy'].to_numpy(dtype=float)
l = res.data['Total<SEP>latency'].to_numpy(dtype=float)
assert len(e) and np.all(e > 0) and np.all(l > 0)
print('RESULT', json.dumps({'shape': [128, 256, 512], 'glb_mib': 0.5,
    'bw_scale': 1, 'jobs': 1, 'make_s': made-start, 'join_profiled_s': joined-made,
    'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    'n': len(e), 'best_edp': float(np.min(e*l))}), flush=True)
for order in ('cumulative', 'tottime'):
    print('\nPROFILE SORTED BY', order, flush=True)
    pstats.Stats(profiler, stream=sys.stdout).strip_dirs().sort_stats(order).print_stats(40)
