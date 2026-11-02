"""Shared helpers for the capacity-tracking audit.

Every experiment here studies the tag1 GLU workload (glu_tag1.yaml) on tpu_v4i while
sweeping the GlobalBuffer capacity. Three search variants are compared:

  indep  one ENERGY|LATENCY search per capacity (the normal FFM baseline)
  var    one RESOURCE_USAGE search at the largest capacity; the join keeps only
         GlobalBuffer variable (AF_VARIABLE_RESOURCES), picks are filtered per capacity
  push   as var, and generation also eliminates fixed resources
         (AF_GENERATION_VARIABLE_RESOURCES)

Picks are trusted only after `strict_evaluate`: the mapping is re-evaluated on the
architecture with the exact target capacity and must reproduce the reported cost.
"""
import copy
import os
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GB = 'reservation<SEP>GlobalBuffer<SEP>0<SEP>right'
VARIANTS = ('indep', 'var', 'push')

# Every research switch read by the library. All are cleared before each search so a
# variable inherited from the shell cannot silently change a run.
SWITCHES = (
    'AF_VARIABLE_RESOURCES',
    'AF_GENERATION_VARIABLE_RESOURCES',
    'AF_ABL_SKIP_BIG_ENOUGH',
    'AF_ABL_SKIP_PMAPPING_ONLY',
    'AF_ABL_ALLOW_UNREPRESENTABLE',
    'AF_STREAMING_JOIN_PAIRS',
)
# Ablations a caller may request for every search in a run, e.g. from the command line.
ABLATIONS = ('AF_ABL_SKIP_BIG_ENOUGH', 'AF_ABL_SKIP_PMAPPING_ONLY', 'AF_ABL_ALLOW_UNREPRESENTABLE')


import accelforge as af  # noqa: E402
from accelforge.mapper.FFM.main import make_pmappings, join_pmappings  # noqa: E402
from accelforge.model.main import evaluate_mapping  # noqa: E402

EL = af.Metrics.ENERGY | af.Metrics.LATENCY
RU = EL | af.Metrics.RESOURCE_USAGE
MAX_JOBS = 16  # hard ceiling: the default (os.cpu_count() = 256) exhausted the shared server


def set_jobs(n):
    """Use n worker processes for AccelForge (1 = serial, no child processes at all).

    Workers are loky processes in the caller's process group, so run_capped.sh counts
    their memory and kills them together with the main process. With n == 1 an audit
    hook forbids child processes, so a serial run really stays in one process.
    """
    if not 1 <= n <= MAX_JOBS:
        raise ValueError(f'jobs must be in [1, {MAX_JOBS}], got {n}')
    af.set_n_parallel_jobs(n)
    if n == 1:
        def hook(event, args):
            if event in {'os.fork', 'os.forkpty', 'os.posix_spawn', 'subprocess.Popen'}:
                raise RuntimeError('Child processes disabled: ' + event)
        sys.addaudithook(hook)


def shutdown_workers():
    """Stop the reusable loky worker pool so no idle workers outlive the run."""
    from joblib.externals.loky import get_reusable_executor
    get_reusable_executor().shutdown(wait=True)


def peak_rss_gb():
    """Peak RSS of this process and of its largest finished child, in GB.

    Children count only once reaped, so call after shutdown_workers(). The total for the
    whole process group is in the run_capped.sh watchdog line.
    """
    self_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    child_kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return {'main': self_kb / 2**20, 'largest_worker': child_kb / 2**20}


def clear_switches():
    for k in SWITCHES:
        os.environ.pop(k, None)


def build(shape, cap_mib, metrics):
    spec = af.Spec.from_yaml(ROOT/'examples/arches/tpu_v4i.yaml', ROOT/'research/streaming_join/glu_tag1.yaml',
                             jinja_parse_data=dict(zip(('M', 'G', 'C'), shape)))
    spec.arch.find('GlobalBuffer').size = cap_mib * 1024 * 1024 * 8
    spec.mapper.ffm.metrics = metrics
    return spec


def search(spec, gen_env=None, join_env=None, ablations=None):
    """make_pmappings + join_pmappings with exactly the given switches set.

    gen_env applies only during generation and join_env only during the join;
    ablations apply to both. Returns (result, stats).
    """
    def set_env(env):
        clear_switches()
        os.environ.update(ablations or {})
        os.environ.update(env or {})
    set_env(gen_env)
    t0 = time.perf_counter()
    pm = make_pmappings(spec, print_number_of_pmappings=False)
    t1 = time.perf_counter()
    rows_generated = sum(len(g.mappings.data) for gs in pm.einsum2pmappings.values() for g in gs)
    set_env(join_env)
    try:
        res = join_pmappings(pm)
    finally:
        clear_switches()
    t2 = time.perf_counter()
    return res, {'make_s': t1 - t0, 'join_s': t2 - t1, 'rows_generated': rows_generated,
                 'rows_front': len(res.data)}


def run_variant(variant, shape, caps, ablations=None):
    """Yield (cap, data, stats) per capacity; shared variants search once at max(caps)."""
    maxcap = max(caps)
    if variant == 'indep':
        for cap in caps:
            res, st = search(build(shape, cap, EL), ablations=ablations)
            yield cap, res.data, st
    elif variant in ('var', 'push'):
        gen_env = {'AF_GENERATION_VARIABLE_RESOURCES': 'GlobalBuffer'} if variant == 'push' else None
        res, st = search(build(shape, maxcap, RU), gen_env, {'AF_VARIABLE_RESOURCES': 'GlobalBuffer'},
                         ablations=ablations)
        for cap in caps:
            yield cap, res.data[res.data[GB] <= cap / maxcap * (1 + 1e-12)], st
    else:
        raise ValueError(f'unknown variant {variant}')


def best_row(data):
    """Row with the lowest EDP, or None if no row fits."""
    if data.empty:
        return None
    edp = data['Total<SEP>energy'] * data['Total<SEP>latency']
    return data.loc[edp.idxmin()]


def strict_evaluate(shape, cap_mib, mapping):
    """Re-evaluate `mapping` on the architecture with exactly `cap_mib` of GlobalBuffer.

    Returns {'energy', 'latency', 'edp'} or raises if the mapping does not fit.
    """
    spec = build(shape, cap_mib, EL)
    spec.model.metrics = EL
    spec.mapping = copy.deepcopy(mapping)
    clear_switches()
    ev = evaluate_mapping(spec).data
    e, l = float(ev['Total<SEP>energy'].iloc[0]), float(ev['Total<SEP>latency'].iloc[0])
    return {'energy': e, 'latency': l, 'edp': e * l}


def check_pick(shape, cap_mib, row, rel_tol=1e-6):
    """Strictly validate a picked row. Returns a record with 'ok' set."""
    rec = {'cap_mib': cap_mib, 'edp': float(row['Total<SEP>energy'] * row['Total<SEP>latency']),
           'energy': float(row['Total<SEP>energy']), 'latency': float(row['Total<SEP>latency'])}
    if GB in row.index:
        rec['reported_gb_mib_fraction'] = float(row[GB])
    try:
        ev = strict_evaluate(shape, cap_mib, row['Total<SEP>mapping']())
    except Exception as e:
        rec.update(ok=False, error=f'{type(e).__name__}: {str(e)[:200]}')
        return rec
    rec['reevaluated'] = ev
    rec['ok'] = all(abs(ev[k] - rec[k]) <= rel_tol * abs(rec[k]) for k in ('energy', 'latency'))
    if not rec['ok']:
        rec['error'] = 'reported cost differs from re-evaluation'
    return rec


def skeleton(obj):
    """str(obj) without the bulky component objects and modeling logs, one node per line."""
    s = str(obj)
    for key in ('component_object=', 'component_modeling_log='):
        out, i = [], 0
        while (j := s.find(key, i)) >= 0:
            out.append(s[i:j])
            k, depth = j + len(key), 0
            while k < len(s):  # skip the value up to its matching close or a top-level comma
                c = s[k]
                if c in '([{':
                    depth += 1
                elif c in ')]}':
                    if depth == 0:
                        break
                    depth -= 1
                    if depth == 0:
                        k += 1
                        break
                elif c == ',' and depth == 0:
                    break
                k += 1
            i = k
        out.append(s[i:])
        s = ''.join(out)
    return ' '.join(s.split()).replace('), ', '),\n').replace('nodes=[', 'nodes=[\n')


def parse_ablations(args):
    """Parse NAME=VALUE pairs (NAME from ABLATIONS) from the command line."""
    out = {}
    for a in args:
        name, _, value = a.partition('=')
        if name not in ABLATIONS or not value:
            raise SystemExit(f'bad ablation {a!r}; expected one of {ABLATIONS} as NAME=VALUE')
        out[name] = value
    return out
