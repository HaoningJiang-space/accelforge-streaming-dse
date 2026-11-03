"""Shared helpers for the capacity-tracking audit.

Every experiment sweeps the GlobalBuffer capacity of one Case: a workload from WORKLOADS
with its template parameters, on an architecture from ARCHES (default: GLU on tpu_v4i).
Three search variants are compared:

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
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GB = 'reservation<SEP>GlobalBuffer<SEP>0<SEP>right'
VARIANTS = ('indep', 'var', 'push')

# Workload name -> (YAML file relative to ROOT, names of its Jinja parameters in the
# order they are given on the command line).
WORKLOADS = {
    'glu': ('research/streaming_join/glu_tag1.yaml', ('M', 'G', 'C')),  # branch and merge
    'matmuls': ('examples/workloads/matmuls.yaml', ('N_EINSUMS', 'M', 'KN')),  # chain
    'mobilenet': ('research/workloads/mobilenet_28_tag1.yaml', ('BATCH_SIZE',)),  # convolutions
}
ARCHES = ('tpu_v4i', 'nvdla')  # examples/arches/<name>.yaml, each with a GlobalBuffer
# eyeriss is left out: its energy comes from a component-model plugin whose installed
# version returns ActionCost objects that the tag1 library cannot index.


@dataclass(frozen=True)
class Case:
    """What is searched: a workload with its parameter values, on an architecture."""
    workload: str
    arch: str
    params: tuple

    def __post_init__(self):
        if self.workload not in WORKLOADS:
            raise ValueError(f'workload must be one of {tuple(WORKLOADS)}, got {self.workload!r}')
        if self.arch not in ARCHES:
            raise ValueError(f'arch must be one of {ARCHES}, got {self.arch!r}')
        names = WORKLOADS[self.workload][1]
        if len(self.params) != len(names) or any(not isinstance(x, int) or x <= 0 for x in self.params):
            raise ValueError(f'{self.workload} takes {len(names)} positive integers {",".join(names)}')

    @classmethod
    def parse(cls, workload, arch, params):
        """Case from command-line strings; params is comma-separated, e.g. '256,512,1024'."""
        return cls(workload, arch, tuple(int(x) for x in params.split(',')))

    def __str__(self):
        names = WORKLOADS[self.workload][1]
        return f'{self.workload}({",".join(f"{k}={v}" for k, v in zip(names, self.params))})@{self.arch}'


DEFAULT_CASE = Case('glu', 'tpu_v4i', (256, 512, 1024))

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
from accelforge.mapper.FFM._pareto_df.df_convention import capacity_excluded2col  # noqa: E402
from accelforge.mapper.FFM._make_pmappings.make_pmappings import (  # noqa: E402
    get_rank_variable_bounds_for_all_einsums,
)

EL = af.Metrics.ENERGY | af.Metrics.LATENCY
LATENCY = 'Total<SEP>latency'
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
    # macOS reports bytes; Linux reports KiB. Output is GiB on both systems.
    divisor = 2**30 if sys.platform == 'darwin' else 2**20
    own = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    child = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return {'main': own / divisor, 'largest_worker': child / divisor}


def clear_switches():
    for k in [k for k in os.environ if k.startswith(SWITCH_PREFIX)]:
        del os.environ[k]


def effective_config(case=DEFAULT_CASE, **extra):
    """Code version and settings of a run. Call before set_jobs(1), which forbids subprocesses."""
    def git(*args):
        try:
            return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True,
                                  text=True, check=True).stdout.strip()
        except Exception as e:
            return f'unavailable: {type(e).__name__}'
    spec = build(case, 1, EL)
    return {'commit': git('rev-parse', 'HEAD'),
            'dirty': bool(git('status', '--porcelain', '--', 'accelforge', 'research')),
            'max_pmapping_templates_per_einsum': str(spec.mapper.ffm.max_pmapping_templates_per_einsum),
            'inherited_switches': sorted(k for k in os.environ if k.startswith(SWITCH_PREFIX)),
            **extra}


def build(case, cap_mib, metrics, gb_latency_scale=1.0):
    """Spec of `case` with exactly cap_mib MiB of GlobalBuffer, searching for `metrics`.

    gb_latency_scale multiplies every GlobalBuffer action latency (0.5 = twice the
    bandwidth); it is the per-component latency_scale of the architecture.
    """
    path, names = WORKLOADS[case.workload]
    spec = af.Spec.from_yaml(ROOT/f'examples/arches/{case.arch}.yaml', ROOT/path,
                             jinja_parse_data=dict(zip(names, case.params)))
    spec.arch.find('GlobalBuffer').size = cap_mib * 1024 * 1024 * 8
    if gb_latency_scale != 1:
        spec.arch.find('GlobalBuffer').latency_scale = gb_latency_scale
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


def capacity_fractions_env(caps):
    """Generation switch telling a search at max(caps) its target capacities, so the
    min-usage fallback is applied per target (see AF_GENERATION_CAPACITY_FRACTIONS)."""
    maxcap = max(caps)
    return {'AF_GENERATION_CAPACITY_FRACTIONS': 'GlobalBuffer:' + ','.join(repr(c / maxcap) for c in caps),
            'AF_GENERATION_CAPACITY_BITS': 'GlobalBuffer:' + ','.join(str(math.floor(c * 2**23)) for c in caps)}


def rows_for_capacity(data, cap, maxcap):
    """Rows of a shared search at maxcap that belong to the search at `cap`: they fit
    its GlobalBuffer and every pmapping was kept by that target's enumeration."""
    raw = 'reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right'
    if 'capacity_reference_bits<SEP>GlobalBuffer' in data and raw not in data:
        raise ValueError('exact capacity query requires absolute-bit reservations')
    rows = data[data[raw] <= math.floor(cap * 2**23)] if raw in data else data[data[GB] <= cap / maxcap * (1 + 1e-12)]
    from accelforge.mapper.FFM._pareto_df.capacity_membership import is_membership_col, membership_for_target
    if any(is_membership_col(c) for c in rows):
        return rows[membership_for_target(rows, 'GlobalBuffer', cap / maxcap)]
    excluded = capacity_excluded2col('GlobalBuffer', cap / maxcap)
    if excluded not in data:
        # Shared searches always run with AF_GENERATION_CAPACITY_FRACTIONS. Filtering
        # by capacity alone would return candidates the target's own search removed.
        raise ValueError(f'shared search result lacks target membership column {excluded!r}')
    return rows[rows[excluded] == 0]


def validate_capacity_picks(case, caps, data):
    """Validate one completed search, including selection/reconstruction failures."""
    records = []
    for cap in caps:
        try:
            row = best_row(rows_for_capacity(data, cap, max(caps)))
            if row is None:
                raise ValueError('no feasible target mapping')
            records.append(check_pick(case, cap, row))
        except Exception as error:
            records.append(dict(cap_mib=cap, ok=False, error=f'{type(error).__name__}: {error}'))
    return records


def run_variant(variant, case, caps, ablations=None):
    """Yield (cap, data, stats) per capacity; shared variants search once at max(caps)."""
    maxcap = max(caps)
    if variant == 'indep':
        for cap in caps:
            res, st = search(build(case, cap, EL), ablations=ablations)
            yield cap, res.data, st
    elif variant in ('var', 'push'):
        gen_env = capacity_fractions_env(caps)
        if variant == 'push':
            gen_env['AF_GENERATION_VARIABLE_RESOURCES'] = 'GlobalBuffer'
        res, st = search(build(case, maxcap, RU), gen_env, {'AF_VARIABLE_RESOURCES': 'GlobalBuffer'},
                         ablations=ablations)
        for cap in caps:
            yield cap, rows_for_capacity(res.data, cap, maxcap), st
    else:
        raise ValueError(f'unknown variant {variant}')


TIE_REL = 1e-6  # tied optima: within float32 cost precision and check_pick rel_tol
MAX_TIES = 64   # rebuild at most this many tied rows to break the tie


def best_row(data, latency_col=LATENCY):
    """Row with the lowest EDP (energy times `latency_col`), or None if no row fits.

    Several different mappings can tie for the lowest EDP, and the joined row order
    depends on parallel scheduling. Ties are therefore broken deterministically by the
    smallest mapping_identity of the tied rows, so the same configuration yields the
    same mapping in every run. row.attrs['tied_optima'] is the number of distinct
    tied mappings (None if the tie could not be broken, e.g. unbuildable rows).
    """
    if data.empty:
        return None
    # Match capacity_breakpoints: multiply in float64, not the input's float32 or
    # fixed-width integer dtype. Use positions because joined indices may repeat.
    energy = data['Total<SEP>energy'].to_numpy(dtype=np.float64)
    latency = data[latency_col].to_numpy(dtype=np.float64)
    edp = energy * latency
    if any(not np.isfinite(a).all() or (a < 0).any() for a in (energy, latency, edp)):
        raise ValueError('candidate costs must be finite and nonnegative')
    tied = np.flatnonzero(edp <= edp.min() * (1 + TIE_REL))[:MAX_TIES]
    best, count = int(edp.argmin()), None
    if len(tied) > 1:
        try:
            ids = {mapping_identity(data.iloc[int(i)]['Total<SEP>mapping']()): int(i) for i in tied}
            best, count = ids[min(ids)], len(ids)
        except Exception:
            pass  # keep argmin; the tie is reported as unknown
    else:
        count = 1
    row = data.iloc[best].copy()
    row.attrs['tied_optima'] = count
    return row


def strict_evaluate(case, cap_mib, mapping, gb_latency_scale=1.0):
    """Re-evaluate `mapping` on the architecture with exactly `cap_mib` of GlobalBuffer.

    Returns energy, latency, edp and every reservation column, or raises if the mapping
    does not fit or the evaluation does not produce exactly one row.
    """
    spec = build(case, cap_mib, RU, gb_latency_scale)
    spec.model.metrics = RU
    spec.mapping = copy.deepcopy(mapping)
    clear_switches()
    ev = evaluate_mapping(spec).data
    if len(ev) != 1:
        raise ValueError(f're-evaluation returned {len(ev)} rows')
    e, l = float(ev['Total<SEP>energy'].iloc[0]), float(ev['Total<SEP>latency'].iloc[0])
    reservations = {c: float(ev[c].iloc[0]) for c in ev.columns if c.startswith('reservation<SEP>')}
    # evaluate_mapping can report an infeasible single-Einsum mapping without
    # passing through a pairwise Join's capacity filter. Check every returned
    # lifetime/branch, including fixed memories, before certifying the pick.
    invalid = {c: usage for c, usage in reservations.items()
               if not math.isfinite(usage) or not 0 <= usage <= 1}
    exact_reservations = {}
    for c in ev:
        if c.startswith('reservation_bits<SEP>'):
            value = ev[c].iloc[0]
            memory = c.split('<SEP>')[1]
            bound = ev['capacity_reference_bits<SEP>' + memory].iloc[0]
            if not math.isfinite(value) or value != int(value) or not 0 <= value <= bound:
                invalid[c] = float(value)
            exact_reservations[c] = int(value)
    if invalid:
        raise ValueError(f'invalid or over-capacity Reservations: {invalid}')
    return {'energy': e, 'latency': l, 'edp': e * l, 'reservations': reservations,
            'reservation_bits': exact_reservations}


def spatial_usage_shortfalls(case, mapping):
    """Spatial fanout dimensions whose usage in `mapping` is below their min_usage.

    Independent of the mapper: along each path to a Compute node, a spatial loop uses
    (enclosing tile of its rank variable) / (its tile shape) instances of its fanout
    dimension; usage = product over that dimension's loops / fanout.
    """
    spec = build(case, 1, EL)
    bounds = get_rank_variable_bounds_for_all_einsums(spec)  # rank variable -> bound, shared
    found = []

    def check(compute, loops):
        einsum = compute.einsum
        evaluated = spec._spec_eval_expressions(einsum_name=einsum)
        path = evaluated._get_flattened_architecture(compute_node=compute.component)
        dimensions = {(node.name, dim.name): dim for node in path for dim in node.spatial}
        size = dict(bounds)
        used = collections.defaultdict(lambda: 1.0)
        for loop in loops:
            rv, tile = loop.rank_variable, loop.tile_shape
            if rv not in size or not isinstance(tile, numbers.Number) or not math.isfinite(tile) or tile <= 0:
                raise ValueError(f'cannot check loop {rv!r} with tile {tile!r}')
            count = size[rv] / tile
            size[rv] = tile
            if isinstance(loop, Spatial):
                if (loop.component, loop.name) not in dimensions:
                    raise ValueError(f'spatial dimension outside compute path: {loop.component}/{loop.name}')
                used[(loop.component, loop.name)] *= count
        # A missing spatial loop still uses one instance, not the whole fanout.
        # Iterate the active architecture path, including dimensions omitted by
        # loop beautification. Other compute branches must not be checked here.
        for (component, name), dim in dimensions.items():
            n = used[(component, name)]
            # Match run_model's objective, which includes the architecture's scale.
            usage = n / float(dim.fanout) * float(dim.usage_scale)
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
                check(n, loops)

    walk(list(mapping.nodes), [])
    return found


def mapping_identity(mapping):
    """Stable fingerprint of a mapping's structure: node types, components, tensors,
    loop rank variables and tile shapes, spatial dimensions and nesting, in order.

    Built from these fields rather than str(mapping): node sets (e.g. backing tensors)
    print in hash-seed-dependent order, and component objects are irrelevant. Equal
    identities mean the same mapping; costs are not part of it, so one mapping keeps
    its identity across bandwidths and capacities.
    """
    def norm(x):
        if isinstance(x, (set, frozenset)):
            return sorted(map(str, x))
        if isinstance(x, (list, tuple)):
            return [str(v) for v in x]
        return str(x) if x is not None else None

    def node(n):
        fields = {'type': type(n).__name__}
        for name in ('component', 'tensors', 'rank_variable', 'tile_shape', 'initial_tile_shape',
                     'name', 'einsum', 'purposes', 'resource', 'persistent'):
            if hasattr(n, name):
                fields[name] = norm(getattr(n, name))
        if hasattr(n, 'nodes') and not isinstance(n, (Loop,)):
            fields['nodes'] = [node(c) for c in n.nodes]
        return fields

    import hashlib
    import json as _json
    blob = _json.dumps([node(n) for n in mapping.nodes], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _finite_nonnegative(*xs):
    return all(isinstance(x, numbers.Number) and math.isfinite(x) and x >= 0 for x in xs)


def check_pick(case, cap_mib, row, rel_tol=1e-6, latency_col=LATENCY, gb_latency_scale=1.0):
    """Strictly validate a picked row. Returns a record with 'ok' set.

    ok requires finite nonnegative reported and re-evaluated costs, a successful
    re-evaluation at exactly cap_mib, and energy and latency matching within rel_tol.
    Spatial min_usage shortfalls are reported in 'min_usage_shortfall' but do not
    affect ok (see module docstring). A checker error does invalidate the audit:
    an unavailable check must not be mistaken for a completed check.

    The reported latency is read from `latency_col` and compared with a re-evaluation
    on the architecture whose GlobalBuffer latency is scaled by gb_latency_scale.
    """
    energy, latency = float(row['Total<SEP>energy']), float(row[latency_col])
    rec = {'cap_mib': cap_mib, 'edp': energy * latency,
           'energy': energy, 'latency': latency}
    if GB in row.index:
        rec['reported_gb_mib_fraction'] = float(row[GB])
    if not _finite_nonnegative(rec['energy'], rec['latency'], rec['edp']):
        rec.update(ok=False, error='reported cost is not finite and nonnegative')
        return rec
    rec['tied_optima'] = getattr(row, 'attrs', {}).get('tied_optima')
    try:
        mapping = row['Total<SEP>mapping']()
        try:
            rec['mapping_id'] = mapping_identity(mapping)
        except Exception:  # record only; does not affect validity
            rec['mapping_id'] = None
        ev = strict_evaluate(case, cap_mib, mapping, gb_latency_scale)
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
        rec['min_usage_shortfall'] = spatial_usage_shortfalls(case, mapping)
    except Exception as e:
        rec['min_usage_shortfall_error'] = f'{type(e).__name__}: {str(e)[:200]}'
        rec['ok'] = False
        rec.setdefault('error', 'spatial min_usage check did not complete')
    return rec


def distinct_optimal_mappings(history):
    """Per variant: how many different mappings its picks use across all configurations
    (last repeat), and each configuration's mapping identity."""
    out = {}
    for v, by_key in history.items():
        ids = {str(k): recs[-1].get('mapping_id') for k, recs in by_key.items() if recs}
        out[v] = {'distinct': len({i for i in ids.values() if i}), 'by_configuration': ids}
    return out


def summarize_quality(history, variants, caps, monotone=False, fits=None):
    """Per-capacity quality over every repeat; see capacity_audit.py for the fields.

    history[variant][cap] is the list of check_pick records of all repeats. A variant is
    invalid at a capacity if any repeat's pick was invalid, so a later success never
    hides an earlier failure. Returns (quality, any_invalid, all_consistent).

    By default compare picks only at the same configuration. Capacity-dependent
    min_usage fallback makes the enumerated Mapspaces non-nested: fitting a larger
    memory does not prove membership in that target's search. monotone=True or an
    explicit fits(c, key) is only valid when the caller has established candidate
    membership and unchanged cost across those configurations.

    EDPs are compared as re-evaluated at the target capacity when available. FFM's own
    reported cost may differ from the model by up to check_pick's rel_tol and from run
    to run (observed: 7e-8 relative for the same mapping cost on matmuls@tpu_v4i), so
    it is kept in 'reported_edp' but does not decide consistency or optimality.
    """
    def verified(rec):
        return rec['ok'] and not rec.get('min_usage_shortfall_error')

    def true_edp(rec):
        return rec['reevaluated']['edp'] if 'reevaluated' in rec else rec.get('edp')

    def same(xs):
        xs = [x for x in xs if x is not None]
        return all(abs(x - xs[0]) <= 1e-9 * abs(xs[0]) for x in xs)

    if fits is None:
        fits = (lambda c, key: c <= key) if monotone else (lambda c, key: c == key)

    quality = {}
    for cap in caps:
        valid_edps = [true_edp(rec) for v in variants for c in caps if fits(c, cap)
                      for rec in history[v][c] if verified(rec)]
        best = min(valid_edps) if valid_edps else None
        q = {'edp': {}, 'reported_edp': {}, 'consistent_across_repeats': {}, 'invalid': [], 'suboptimal': [],
             'min_usage_shortfall': [], 'min_usage_check_error': [], 'best_valid_edp': best}
        for v in variants:
            recs = history[v][cap]
            edps = [true_edp(rec) for rec in recs]
            q['edp'][v] = edps[-1]
            q['reported_edp'][v] = recs[-1].get('edp')
            q['consistent_across_repeats'][v] = same(edps)
            if not all(verified(rec) for rec in recs):
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
