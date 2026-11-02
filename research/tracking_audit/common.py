"""Shared helpers for the capacity-tracking audit.

Every experiment here studies the tag1 GLU workload (glu_tag1.yaml) on tpu_v4i while
sweeping the GlobalBuffer capacity. Three search variants are compared:

  indep  one ENERGY|LATENCY search per capacity (the normal FFM baseline)
  var    one RESOURCE_USAGE search at the largest capacity; the join keeps only
         GlobalBuffer variable (AF_VARIABLE_RESOURCES), picks are filtered per capacity
  push   as var, and generation also eliminates fixed resources
         (AF_GENERATION_VARIABLE_RESOURCES)

Picks are trusted only after `check_pick`: the mapping is re-evaluated on the
architecture with the exact target capacity and must reproduce the reported cost, and
costs must be finite. Spatial min_usage constraints are checked separately and reported
as shortfalls, because the mapper may legally accept the best available usage when no
candidate reaches the minimum.
"""
import collections
import copy
import math
import numbers
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GB = 'reservation<SEP>GlobalBuffer<SEP>0<SEP>right'
VARIANTS = ('indep', 'var', 'push')

# Every research switch read by the library starts with this prefix. All such variables
# are cleared before each search so one inherited from the shell cannot silently change
# a run (e.g. AF_NUMERIC_JOIN selects a different join backend).
SWITCH_PREFIX = 'AF_'
# Ablations a caller may request for every search in a run, e.g. from the command line.
ABLATIONS = ('AF_ABL_SKIP_BIG_ENOUGH', 'AF_ABL_SKIP_PMAPPING_ONLY', 'AF_ABL_ALLOW_UNREPRESENTABLE',
             'AF_ABL_BIG_ENOUGH_UNTRACK_ONLY')


import accelforge as af  # noqa: E402
from accelforge.mapper.FFM.main import make_pmappings, join_pmappings  # noqa: E402
from accelforge.model.main import evaluate_mapping  # noqa: E402
from accelforge.frontend.mapping import Compute, Loop, Nested, Spatial, Split  # noqa: E402
from accelforge.mapper.FFM._make_pmappings.make_pmappings import (  # noqa: E402
    get_rank_variable_bounds_for_all_einsums,
)

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
    for k in [k for k in os.environ if k.startswith(SWITCH_PREFIX)]:
        del os.environ[k]


def effective_config(**extra):
    """Code version and settings of a run. Call before set_jobs(1), which forbids subprocesses."""
    def git(*args):
        try:
            return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True,
                                  text=True, check=True).stdout.strip()
        except Exception as e:
            return f'unavailable: {type(e).__name__}'
    spec = build((1, 1, 1), 1, EL)
    return {'commit': git('rev-parse', 'HEAD'), 'dirty': bool(git('status', '--porcelain', '--', 'accelforge')),
            'max_pmapping_templates_per_einsum': str(spec.mapper.ffm.max_pmapping_templates_per_einsum),
            'inherited_switches': sorted(k for k in os.environ if k.startswith(SWITCH_PREFIX)),
            **extra}


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
    try:
        set_env(gen_env)
        t0 = time.perf_counter()
        pm = make_pmappings(spec, print_number_of_pmappings=False)
        t1 = time.perf_counter()
        rows_generated = sum(len(g.mappings.data) for gs in pm.einsum2pmappings.values() for g in gs)
        set_env(join_env)
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

    Returns energy, latency, edp and every reservation column, or raises if the mapping
    does not fit or the evaluation does not produce exactly one row.
    """
    spec = build(shape, cap_mib, RU)
    spec.model.metrics = RU
    spec.mapping = copy.deepcopy(mapping)
    clear_switches()
    ev = evaluate_mapping(spec).data
    if len(ev) != 1:
        raise ValueError(f're-evaluation returned {len(ev)} rows')
    e, l = float(ev['Total<SEP>energy'].iloc[0]), float(ev['Total<SEP>latency'].iloc[0])
    reservations = {c: float(ev[c].iloc[0]) for c in ev.columns if c.startswith('reservation<SEP>')}
    return {'energy': e, 'latency': l, 'edp': e * l, 'reservations': reservations}


def spatial_usage_shortfalls(shape, mapping):
    """Spatial fanout dimensions whose usage in `mapping` is below their min_usage.

    Independent of the mapper: along each path to a Compute node, a spatial loop uses
    (enclosing tile of its rank variable) / (its tile shape) instances of its fanout
    dimension; usage = product over that dimension's loops / fanout.
    """
    spec = build(shape, 1, EL)
    bounds = get_rank_variable_bounds_for_all_einsums(spec)  # rank variable -> bound, shared
    found = []

    def check(einsum, loops):
        size = dict(bounds)
        used = collections.defaultdict(lambda: 1.0)
        for loop in loops:
            rv, tile = loop.rank_variable, loop.tile_shape
            if rv not in size or not isinstance(tile, numbers.Number) or tile <= 0:
                continue
            count = size[rv] / tile
            size[rv] = tile
            if isinstance(loop, Spatial):
                used[(loop.component, loop.name)] *= count
        for (component, name), n in used.items():
            dims = {d.name: d for d in spec.arch.find(component).spatial}
            dim = dims[name]
            usage = n / float(dim.fanout)
            if dim.min_usage and usage < float(dim.min_usage) - 1e-9:
                found.append({'einsum': einsum, 'component': component, 'dimension': name,
                              'usage': usage, 'min_usage': float(dim.min_usage)})

    def walk(nodes, loops):
        loops = list(loops)
        for i, n in enumerate(nodes):
            if isinstance(n, Split):
                for child in n.nodes:
                    walk(child.nodes if isinstance(child, Nested) else [child], loops)
                return
            if isinstance(n, Nested):
                walk(list(n.nodes) + list(nodes[i + 1:]), loops)
                return
            if isinstance(n, Loop):
                loops.append(n)
            elif isinstance(n, Compute):
                check(n.einsum, loops)

    walk(list(mapping.nodes), [])
    return found


def _finite_nonnegative(*xs):
    return all(isinstance(x, numbers.Number) and math.isfinite(x) and x >= 0 for x in xs)


def check_pick(shape, cap_mib, row, rel_tol=1e-6):
    """Strictly validate a picked row. Returns a record with 'ok' set.

    ok requires finite nonnegative reported and re-evaluated costs, a successful
    re-evaluation at exactly cap_mib, and energy and latency matching within rel_tol.
    Spatial min_usage shortfalls are reported in 'min_usage_shortfall' but do not
    affect ok (see module docstring).
    """
    rec = {'cap_mib': cap_mib, 'edp': float(row['Total<SEP>energy'] * row['Total<SEP>latency']),
           'energy': float(row['Total<SEP>energy']), 'latency': float(row['Total<SEP>latency'])}
    if GB in row.index:
        rec['reported_gb_mib_fraction'] = float(row[GB])
    if not _finite_nonnegative(rec['energy'], rec['latency'], rec['edp']):
        rec.update(ok=False, error='reported cost is not finite and nonnegative')
        return rec
    try:
        mapping = row['Total<SEP>mapping']()
        ev = strict_evaluate(shape, cap_mib, mapping)
    except Exception as e:
        rec.update(ok=False, error=f'{type(e).__name__}: {str(e)[:200]}')
        return rec
    rec['reevaluated'] = ev
    if not _finite_nonnegative(ev['energy'], ev['latency'], ev['edp']):
        rec.update(ok=False, error='re-evaluated cost is not finite and nonnegative')
        return rec
    rec['ok'] = all(abs(ev[k] - rec[k]) <= rel_tol * rec[k] for k in ('energy', 'latency'))
    if not rec['ok']:
        rec['error'] = 'reported cost differs from re-evaluation'
    try:
        rec['min_usage_shortfall'] = spatial_usage_shortfalls(shape, mapping)
    except Exception as e:
        rec['min_usage_shortfall_error'] = f'{type(e).__name__}: {str(e)[:200]}'
    return rec


def summarize_quality(history, variants, caps):
    """Per-capacity quality over every repeat; see capacity_audit.py for the fields.

    history[variant][cap] is the list of check_pick records of all repeats. A variant is
    invalid at a capacity if any repeat's pick was invalid, so a later success never
    hides an earlier failure. Returns (quality, any_invalid, all_consistent).
    """
    def same(xs):
        xs = [x for x in xs if x is not None]
        return all(abs(x - xs[0]) <= 1e-9 * abs(xs[0]) for x in xs)

    quality = {}
    for cap in caps:
        valid_edps = [rec['edp'] for v in variants for c in caps if c <= cap
                      for rec in history[v][c] if rec['ok']]
        best = min(valid_edps) if valid_edps else None
        q = {'edp': {}, 'consistent_across_repeats': {}, 'invalid': [], 'suboptimal': [],
             'min_usage_shortfall': [], 'min_usage_check_error': [], 'best_valid_edp': best}
        for v in variants:
            recs = history[v][cap]
            edps = [rec.get('edp') for rec in recs]
            q['edp'][v] = edps[-1]
            q['consistent_across_repeats'][v] = same(edps)
            if not all(rec['ok'] for rec in recs):
                q['invalid'].append(v)
            elif best is not None and max(edps) > best * (1 + 1e-6):
                q['suboptimal'].append(v)
            if any(rec.get('min_usage_shortfall') for rec in recs):
                q['min_usage_shortfall'].append(v)
            if any(rec.get('min_usage_shortfall_error') for rec in recs):
                q['min_usage_check_error'].append(v)
        quality[str(cap)] = q
    any_invalid = any(q['invalid'] for q in quality.values())
    all_consistent = all(all(q['consistent_across_repeats'].values()) for q in quality.values())
    return quality, any_invalid, all_consistent


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
