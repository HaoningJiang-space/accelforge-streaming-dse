"""Independent FFM vs shared search with join-only vs generation-time resource elimination.

usage: capacity_pushdown.py M,G,C CAP1,CAP2,... [MODES, default "indep,join,push"]
Capacities are GlobalBuffer sizes in MiB; shared modes search at the largest one.
  indep: one ENERGY|LATENCY search per capacity
  join:  one RESOURCE_USAGE search, AF_VARIABLE_RESOURCES=GlobalBuffer during the join
  push:  as join, plus AF_GENERATION_VARIABLE_RESOURCES=GlobalBuffer during generation
Single process, no children; run under run_capped.sh.
"""
import gc, json, os, resource, sys, time
from pathlib import Path


def no_children(event, args):
    if event in {'os.fork', 'os.forkpty', 'os.posix_spawn', 'subprocess.Popen'}:
        raise RuntimeError('Child processes disabled: ' + event)


sys.addaudithook(no_children)
import accelforge as af
from accelforge.mapper.FFM.main import make_pmappings, join_pmappings

root = Path(__file__).resolve().parents[2]
af.set_n_parallel_jobs(1)
shape = [int(x) for x in sys.argv[1].split(',')]
caps = [float(x) for x in sys.argv[2].split(',')]
modes = (sys.argv[3] if len(sys.argv) > 3 else 'indep,join,push').split(',')
MAXCAP = max(caps)
EL = af.Metrics.ENERGY | af.Metrics.LATENCY
RU = EL | af.Metrics.RESOURCE_USAGE
GB = 'reservation<SEP>GlobalBuffer<SEP>0<SEP>right'
ENV = ('AF_VARIABLE_RESOURCES', 'AF_GENERATION_VARIABLE_RESOURCES', 'AF_STREAMING_JOIN_PAIRS')


def build(cap, metrics):
    spec = af.Spec.from_yaml(root/'examples/arches/tpu_v4i.yaml', root/'research/streaming_join/glu_tag1.yaml',
                             jinja_parse_data=dict(zip(('M', 'G', 'C'), shape)))
    spec.arch.find('GlobalBuffer').size = cap * 1024 * 1024 * 8
    spec.mapper.ffm.metrics = metrics
    return spec


def n_rows(pm):
    return sum(len(g.mappings.data) for gs in pm.einsum2pmappings.values() for g in gs)


def edp_best(data, cap=None):
    if cap is not None:
        data = data[data[GB] <= cap / MAXCAP * (1 + 1e-12)]
    if data.empty:
        return None
    return float((data['Total<SEP>energy'] * data['Total<SEP>latency']).min())


def run(spec, gen_env, join_env):
    for k in ENV:
        os.environ.pop(k, None)
    os.environ.update(gen_env)
    t0 = time.perf_counter()
    pm = make_pmappings(spec, print_number_of_pmappings=False)
    t1 = time.perf_counter()
    rows_gen = n_rows(pm)
    for k in ENV:
        os.environ.pop(k, None)
    os.environ.update(join_env)
    res = join_pmappings(pm)
    t2 = time.perf_counter()
    for k in ENV:
        os.environ.pop(k, None)
    return res, {'make_s': t1 - t0, 'join_s': t2 - t1, 'rows_generated': rows_gen, 'rows_front': len(res.data)}


def record(mode, **kw):
    kw.update(mode=mode, shape=shape, peak_rss_gb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20)
    print('RESULT', json.dumps(kw), flush=True)


for mode in modes:
    if mode == 'indep':
        edps, stats = [], []
        for cap in caps:
            res, st = run(build(cap, EL), {}, {})
            edps.append(edp_best(res.data))
            stats.append(st)
            del res
            gc.collect()
        record(mode, caps=caps, edps=edps, per_cap=stats,
               total_s=sum(s['make_s'] + s['join_s'] for s in stats))
    elif mode in ('join', 'push'):
        gen_env = {'AF_GENERATION_VARIABLE_RESOURCES': 'GlobalBuffer'} if mode == 'push' else {}
        res, st = run(build(MAXCAP, RU), gen_env, {'AF_VARIABLE_RESOURCES': 'GlobalBuffer'})
        record(mode, caps=caps, edps=[edp_best(res.data, c) for c in caps], **st,
               total_s=st['make_s'] + st['join_s'])
        del res
        gc.collect()
    else:
        raise SystemExit(f'unknown mode {mode}')
