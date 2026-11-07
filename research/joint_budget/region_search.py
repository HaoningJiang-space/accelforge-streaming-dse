"""On-demand native Event oracle with global EDP hardware-region pruning.

The events control uses the identical order, oracle, cross-shape cache and witness
validation. Neither search reads reference results; verification happens afterward.
EDP cuts do NOT preserve the full global E/T Pareto front.
"""
import argparse
from dataclasses import asdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.enumeration_reuse import EnumerationReuse
from accelforge.mapper.FFM._pareto_df.capacity_membership import is_membership_col
from accelforge.mapper.FFM._pareto_df.df_convention import col_used_in_pareto
from accelforge.mapper.FFM._pareto_df.pareto import makepareto
from research.joint_search.validation import WorkCounter, frontier
from research.joint_search.ffm_backend import tiles
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, validate_pick
from .analytic_bounds import lower_bound, check_frozen_inputs, factor_domain, factor_budgets, audit_vectors
from .protocol import Domain, Hardware, ResourceBudget, registered_domain, registered_budgets


def source_digest():
    tree = hashlib.sha256()
    for root in ('accelforge','research/tracking_audit','research/joint_search','research/joint_budget'):
        for path in sorted(Path(root).rglob('*.py')):
            tree.update(path.as_posix().encode()+b'\0'+path.read_bytes())
    return tree.hexdigest()


class EventOracle:
    """Same Event+Bitset+global EnumerationReuse used by the strongest control."""
    def __init__(self, case):
        self.case = case
        self.outputs = {}
        self.details = []

    def solve(self, shape, points, reuse):
        largest = max(p.capacity_bytes for p in points)
        caps = [p.capacity_bytes for p in points]
        env = {'AF_TARGET_ENUMERATION': 'events', 'AF_CAPACITY_MEMBERSHIP': 'bitset',
               'AF_GENERATION_CAPACITY_FRACTIONS': 'GlobalBuffer:'+','.join(repr(c/largest) for c in caps),
               'AF_GENERATION_CAPACITY_BITS': 'GlobalBuffer:'+','.join(str(c*8) for c in caps)}
        started = time.perf_counter()
        with reuse.target(shape), WorkCounter() as counter:
            result, timing = common.search(build(self.case, shape, largest, common.RU), env)
            for point in points:
                data = common.rows_for_capacity(result.data, point.capacity_bytes/2**20, largest/2**20).copy()
                data = data.drop(columns=[c for c in data if is_membership_col(c)])
                data['capacity_reference_bits<SEP>GlobalBuffer'] = point.capacity_bytes*8
                for c in data:
                    if c.startswith('reservation<SEP>GlobalBuffer<SEP>'):
                        data[c] = data[c.replace('reservation<SEP>', 'reservation_bits<SEP>')]/(point.capacity_bytes*8)
                columns = [c for c in data.select_dtypes(include='number') if col_used_in_pareto(c)]
                self.outputs[point] = makepareto(data, columns=columns)
        self.details.append(dict(shape=shape, capacities=caps, oracle_s=time.perf_counter()-started,
                                 timing=timing, work=counter.counts))


def search(case, domain, budgets, method='shape', progress=None):
    if method not in ('events', 'configured', 'shape'):
        raise ValueError('events/configured/shape method required')
    if tiles.IMPERFECT or tiles.pareto_module.TOLERANCE != 0:
        raise ValueError('bound derivation requires perfect tiles and zero Pareto tolerance')
    common.clear_switches()
    common.af.set_n_parallel_jobs(1)
    started = time.perf_counter()
    check_frozen_inputs()
    oracle = EventOracle(case)
    grouped = {shape: [p for p in domain.points if (p.px, p.py) == shape]
               for shape in sorted({(p.px, p.py) for p in domain.points})}
    # Same deterministic geometry order in every ablation. No known winner seed.
    shapes = sorted(grouped, key=lambda s: (
        lower_bound(case, grouped[s][0], 'shape').latency,
        max(s)/min(s), s))
    incumbents = [None] * len(budgets)
    certificates, trajectory = [], []
    with EnumerationReuse() as reuse:
        for shape in shapes:
            points = grouped[shape]
            bound = lower_bound(case, points[0], 'configured' if method == 'configured' else 'shape')
            affected = [i for i, b in enumerate(budgets) if any(b.admits(p) for p in points)]
            can_cut = method != 'events' and all(
                incumbents[i] is not None and bound.edp >= incumbents[i]['cutoff_edp'] for i in affected)
            if can_cut:
                certificates.append(dict(shape=shape, hardware=[asdict(p) for p in points],
                    elapsed_s=time.perf_counter()-started,
                    bound=bound.record(), budget_witnesses=[dict(budget_index=i,
                        witness_index=incumbents[i]['witness_index'],
                        architecture=incumbents[i]['architecture'], mapping_id=incumbents[i]['witness']['mapping_id'],
                        reported_edp=incumbents[i]['reported_edp'],
                        exact_cutoff_edp=str(incumbents[i]['cutoff_edp'])) for i in affected],
                    theorem='nonnegative E,T; L_E*L_T >= feasible incumbent EDP for every affected budget',
                    certified_before_finite_reference_audit=False))
            else:
                oracle.solve(shape, points, reuse)
                for point in points:
                    row = common.best_row(oracle.outputs[point])
                    if row is None:
                        continue
                    energy, latency = float(row['Total<SEP>energy']), float(row[common.LATENCY])
                    edp = energy*latency
                    updates = [i for i, b in enumerate(budgets) if b.admits(point) and
                               (incumbents[i] is None or edp < incumbents[i]['reported_edp'])]
                    if not updates:
                        continue
                    witness = validate_pick(case, shape, point.capacity_bytes, row)
                    if not witness['ok'] or not witness['feasible']:
                        raise AssertionError('incumbent reconstruction failed')
                    # Upward allowance makes cuts conservative with respect to
                    # both reported and independently reconstructed objectives.
                    cutoff = (Fraction.from_float(max(energy, witness['energy'])) *
                              Fraction.from_float(max(latency, witness['latency'])) * Fraction(1000001, 1000000)**2)
                    record = dict(architecture=asdict(point), reported_energy=energy,
                        reported_latency=latency, reported_edp=edp, cutoff_edp=cutoff, witness=witness,
                        witness_index=len(trajectory))
                    for i in updates:
                        incumbents[i] = record
                    trajectory.append(dict(elapsed_s=time.perf_counter()-started, architecture=asdict(point),
                        budget_indices=updates, reported_edp=edp, mapping_id=witness['mapping_id'],
                        reported_energy=energy, reported_latency=latency,
                        exact_cutoff_edp=str(cutoff), witness=witness))
            if progress:
                progress(dict(shape=shape, cut=can_cut, native_solves=len(oracle.details),
                              pruned_regions=len(certificates), elapsed_s=time.perf_counter()-started))
        cache = dict(reuse.stats)
    elapsed = time.perf_counter()-started
    return oracle.outputs, dict(method=method, search_s=elapsed, oracle_details=oracle.details,
        cache=cache, native_solves=len(oracle.details), pruned_regions=len(certificates),
        pruned_hardware=sum(len(c['hardware']) for c in certificates), certificates=certificates,
        trajectory=trajectory, budget_selections=[dict(budget=asdict(b), **{
            k: v for k, v in winner.items() if k != 'cutoff_edp'}) if winner else dict(budget=asdict(b), feasible=False)
            for b, winner in zip(budgets, incumbents)],
        objective='global EDP only', full_global_pareto_preserved=False,
        physical_mapspace_optimality=False, external_sota_acceptance=False,
        new_algorithm_novelty_claim=False,
        peak_rss_gib_before_validation=common.peak_rss_gb())


def run(method, domain_name, output, reference_path=None, workload='3mm'):
    if workload == '3mm':
        case = common.Case('matmuls', 'nvdla', (3, 256, 256))
        domain = registered_domain() if domain_name == 'original12' else factor_domain()
        budgets = registered_budgets() if domain_name == 'original12' else factor_budgets()
    elif workload == 'attention':
        case = common.Case('attention', 'nvdla', (128,1,64))
        capacities = (4096,8192,16384,32768)
        domain = factor_domain(capacities=capacities) if domain_name == 'factors96' else Domain(tuple(
            Hardware(x,y,c) for x,y in ((16,384),(32,192),(64,96)) for c in capacities))
        budgets = tuple(ResourceBudget(6144,c) for c in capacities)
    else:
        raise ValueError('3mm/attention workload required')
    report = dict(status='running', domain_name=domain_name, case=asdict(case),
        domain=[asdict(p) for p in domain.points], method=method, workers=1,
        python=sys.version, platform=platform.platform(),
        timing_scope='all preparation, lower bounds, native generation, Join, cache, queries, improving-witness reevaluation',
        reference_read_before_search=False, points=[])
    report['source_tree_sha256_before_search'] = source_digest()
    def save():
        output.parent.mkdir(parents=True, exist_ok=True)
        tmp = output.with_suffix(output.suffix+'.tmp')
        tmp.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        tmp.replace(output)
    save()
    try:
        outputs, result = search(case, domain, budgets, method, lambda r: print(json.dumps(r), flush=True))
        report.update(result)
        for point in domain.points:
            if point in outputs:
                report['points'].append(dict(architecture=asdict(point),
                    vectors=frontier(outputs[point]).to_dict('records'), source_rows=len(outputs[point])))
        if reference_path:
            frozen = json.loads(reference_path.read_text(encoding='utf-8'))
            if frozen['status'] != 'complete' or frozen['domain'] != report['domain'] or len(frozen['points']) != len(domain.points):
                raise ValueError('complete exhaustive reference on identical domain required')
            if frozen.get('case') and frozen['case'] != json.loads(json.dumps(asdict(case))):
                raise ValueError('reference workload differs')
            audits = audit_vectors(case, domain, frozen['points'], 'configured' if method == 'configured' else 'shape')
            report['bound_audit'] = audits
            lookup = {tuple(p['architecture'].values()): p for p in frozen['points']}
            for actual in report['points']:
                expected = lookup[tuple(actual['architecture'].values())]
                if actual['vectors'] != expected['vectors']:
                    raise AssertionError('visited full native frontier changed')
            for selected, budget in zip(report['budget_selections'], budgets):
                vectors = [v for point, record in zip(domain.points, frozen['points']) if budget.admits(point)
                           for v in record['vectors']]
                expected = min(v['Total<SEP>energy']*v['Total<SEP>latency'] for v in vectors)
                if selected['reported_edp'] != expected:
                    raise AssertionError(f'global EDP differs: {selected["reported_edp"]} != {expected}')
            # Independently replay every arithmetic cut; reject missing witnesses.
            for cert in report['certificates']:
                point = next(p for p in domain.points if (p.px, p.py) == tuple(cert['shape']))
                bound = lower_bound(case, point, 'configured' if method == 'configured' else 'shape')
                for witness in cert['budget_witnesses']:
                    found = report['trajectory'][witness['witness_index']]
                    index = witness['budget_index']
                    if (found['architecture'] != witness['architecture'] or
                        found['mapping_id'] != witness['mapping_id'] or
                        found['elapsed_s'] > cert['elapsed_s'] or
                        index not in found['budget_indices'] or
                        not budgets[index].admits(type(point)(**found['architecture'])) or
                        not found['witness']['ok'] or not found['witness']['feasible'] or
                        found['exact_cutoff_edp'] != witness['exact_cutoff_edp']):
                        raise AssertionError('cut witness provenance fails')
                    if bound.edp < Fraction(witness['exact_cutoff_edp']):
                        raise AssertionError('cut arithmetic fails')
                cert['finite_reference_audit_passed'] = True
            report['verification'] = dict(global_edp_exact=True, all_visited_frontiers_exact=True,
                all_pruned_native_frontiers_bound_checked=True, arithmetic_cuts_replayed=True,
                scope='finite declared native-policy domain, not all physical mappings')
            report['reference_sha256'] = hashlib.sha256(reference_path.read_bytes()).hexdigest()
        report['source_sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in Path('research/joint_budget').glob('*.py')}
        report['source_tree_sha256'] = source_digest()
        if report['source_tree_sha256'] != report['source_tree_sha256_before_search']:
            raise AssertionError('source files changed during experiment; result is not a frozen-code repetition')
        report['status'] = 'complete'
        save()
        print(json.dumps({k: report[k] for k in ('status','method','search_s','native_solves','pruned_regions')}), flush=True)
    except Exception as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
        save()
        raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method', choices=('events','configured','shape'), required=True)
    parser.add_argument('--domain', choices=('original12','factors96'), default='original12')
    parser.add_argument('--workload', choices=('3mm','attention'), default='3mm')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference', type=Path)
    args = parser.parse_args()
    run(args.method, args.domain, args.output, args.reference, args.workload)


if __name__ == '__main__':
    main()
