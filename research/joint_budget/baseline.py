"""Native reference for Chat's 3mm protocol, not an implementation of BCGE.

Run one baseline per fresh process. Serialize full numeric fronts, actual work,
and selected physical witnesses; select one global hardware under each budget.
Frozen per-point reference comparisons are for verification only, outside timers.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import validate_pick
from research.joint_search.validation import reference, capacity_events, frontier
from .protocol import registered_domain, registered_budgets


def run(method, output, reference_path=None):
    common.clear_switches()
    common.af.set_n_parallel_jobs(1)
    domain = registered_domain()
    case = common.Case('matmuls', 'nvdla', (3, 256, 256))
    report = dict(status='running', method=method, workload=str(case),
        python=sys.version, platform=platform.platform(),
        domain=[asdict(p) for p in domain.points], points=[],
        budget_kind='explicit PE/SRAM ceilings; uncalibrated chip area',
        bcge_implemented=False, sota_acceptance=False,
        timing_scope='spec preparation, generation, Join, queries and cache scope; imports excluded',
        verification_scope='complete numeric frontier, selected physical witness per point',
        workers=1)
    output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        temporary.replace(output)

    save()
    try:
        started = time.perf_counter()
        if method == 'events':
            outputs, details, cache = capacity_events(case, domain)
        else:
            outputs, records, _, cache = reference(case, domain, cached=method == 'cached')
            details = [dict(architecture=asdict(p), **records[p]) for p in domain.points]
        report['search_s'] = time.perf_counter() - started
        report['peak_rss_gib_before_validation'] = common.peak_rss_gb()
        report['search_details'] = details
        report['cache'] = cache
        frozen = json.loads(reference_path.read_text(encoding='utf-8')) if reference_path else None
        if frozen is not None and (frozen['status'] != 'complete'
                                   or frozen['domain'] != report['domain']):
            raise ValueError('complete reference on the identical frozen domain required')
        for index, point in enumerate(domain.points):
            data = outputs[point]
            vectors = frontier(data).to_dict('records')
            if frozen is not None and vectors != frozen['points'][index]['vectors']:
                raise AssertionError(f'complete numeric frontier differs at {point}')
            best = common.best_row(data)
            witness = validate_pick(case, (point.px, point.py), point.capacity_bytes, best)
            report['points'].append(dict(architecture=asdict(point), vectors=vectors,
                source_rows=len(data), witness=witness,
                full_frontier_equal_to_reference=True if frozen is not None else None))
            save()
        report['budget_selections'] = []
        for budget in registered_budgets():
            eligible = [record for point, record in zip(domain.points, report['points'])
                        if budget.admits(point) and record['witness']['feasible']]
            winner = min(eligible, key=lambda r: r['witness']['edp']) if eligible else None
            report['budget_selections'].append(dict(budget=asdict(budget),
                architecture=winner['architecture'] if winner else None,
                edp=winner['witness']['edp'] if winner else None,
                mapping_id=winner['witness']['mapping_id'] if winner else None))
        if reference_path:
            report['reference_sha256'] = hashlib.sha256(reference_path.read_bytes()).hexdigest()
        report['source_sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for directory in ('research/joint_budget', 'research/joint_search')
            for p in Path(directory).glob('*.py')}
        tree = hashlib.sha256()
        for root in ('accelforge', 'research/tracking_audit', 'research/joint_search', 'research/joint_budget'):
            for path in sorted(Path(root).rglob('*.py')):
                tree.update(path.as_posix().encode() + b'\0' + path.read_bytes())
        report['source_tree_sha256'] = tree.hexdigest()
        report['status'] = 'complete'
        save()
        print(json.dumps(dict(status='complete', method=method, search_s=report['search_s'],
                              selections=report['budget_selections'])), flush=True)
        return report
    except Exception as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method', choices=('independent', 'cached', 'events'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference', type=Path)
    args = parser.parse_args()
    run(args.method, args.output, args.reference)


if __name__ == '__main__':
    main()
