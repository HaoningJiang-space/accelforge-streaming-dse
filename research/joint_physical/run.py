"""Validate direct joint generation against the complete broader-policy reference."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

from research.fusion_envelope.search import problem,digest as base_digest
from research.joint_budget.analytic_bounds import lower_bound
from research.joint_budget.protocol import Domain
from research.joint_search.validation import WorkCounter,frontier
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import validate_pick
from .generator import search
from .replay import encode


def source_digest():
    value = hashlib.sha256(base_digest().encode())
    for path in sorted(Path('research/joint_physical').glob('*.py')):
        value.update(path.as_posix().encode()+b'\0'+path.read_bytes())
    return value.hexdigest()


def run(workload,domain_name,output,reference_path,collect_differences=False,method='direct',rounds=1,seed_wave=False):
    case,domain,budgets = problem(workload,domain_name)
    report = dict(status='running',case=asdict(case),domain=[asdict(p) for p in domain.points],
        method=method+' joint physical generation',policy='relaxed',points=[],workers=1,
        external_sota_acceptance=False,physical_mapspace_optimality=False,
        reference_read_before_search=False,frontier_differences=[],source_before=source_digest(),
        timing_scope='all symbolic preparation, LP proposals, integer feasibility/ranking, selected-row materialization, native Join, architecture queries and final budget witness reevaluation')
    def save():
        output.parent.mkdir(parents=True,exist_ok=True)
        temporary = output.with_suffix(output.suffix+'.tmp')
        temporary.write_text(json.dumps(report,allow_nan=False,separators=(',',':'))+'\n',encoding='utf-8')
        temporary.replace(output)
    save()
    try:
        started = time.perf_counter()
        search_fn = search
        if method=='demand':
            from .demand import search as demand_search
            search_fn = lambda c,d:demand_search(c,d,rounds=rounds)
        seed_details = None
        with WorkCounter() as counter:
            if seed_wave:
                if method!='demand':
                    raise ValueError('seed wave is defined only for the demand generator')
                anchor = min(domain.points,key=lambda p:(lower_bound(case,p).latency,
                    max(p.px,p.py)/min(p.px,p.py),p))
                seed_domain = Domain(tuple(p for p in domain.points if (p.px,p.py)==(anchor.px,anchor.py)))
                seed_outputs,seed_details = search_fn(case,seed_domain)
                seed_rows = {p:common.best_row(d) for p,d in seed_outputs.items()}
                seeds = []
                for budget in budgets:
                    eligible = [(p,r) for p,r in seed_rows.items() if budget.admits(p) and r is not None]
                    if not eligible:
                        seeds.append(None)
                        continue
                    p,row = min(eligible,key=lambda pair:float(pair[1]['Total<SEP>energy'])*float(pair[1][common.LATENCY]))
                    witness = validate_pick(case,(p.px,p.py),p.capacity_bytes,row)
                    witness['mapping'] = encode(row['Total<SEP>mapping']())
                    seeds.append(dict(architecture=asdict(p),budget=asdict(budget),witness=witness,
                                      elapsed_s=time.perf_counter()-started))
                report['seed_budget_selections'] = seeds
                report['seed_details'] = seed_details
                print(json.dumps(dict(stage='seed_complete',elapsed_s=time.perf_counter()-started,
                    canonical_edp=[r['witness']['edp'] if r else None for r in seeds])),flush=True)
            outputs,details = search_fn(case,domain)
        selected_rows = {point:common.best_row(data) for point,data in outputs.items()}
        winners = []
        for budget in budgets:
            eligible = [(point,row) for point,row in selected_rows.items() if budget.admits(point) and row is not None]
            if not eligible:
                raise AssertionError('no feasible proposed design under a declared budget')
            point,row = min(eligible,key=lambda pair:float(pair[1]['Total<SEP>energy'])*float(pair[1][common.LATENCY]))
            witness = validate_pick(case,(point.px,point.py),point.capacity_bytes,row)
            if not witness['ok'] or not witness['feasible']:
                raise AssertionError('final physical budget witness failed')
            witness['mapping'] = encode(row['Total<SEP>mapping']())
            winners.append((point,row,witness))
        report.update(search_s=time.perf_counter()-started,details=details,
            work=dict(counter.counts),peak_rss_gib_before_validation=common.peak_rss_gb())
        report['work']['model_rows'] = details.get('model_rows',details.get('proposer',{}).get('materialized_rows',0))
        report['work']['model_templates'] = len(details['enumeration']) if 'enumeration' in details else details['proposer']['symbolic_models']
        if seed_details:
            report['work']['model_rows'] += seed_details['proposer']['materialized_rows']
            report['work']['model_templates'] += seed_details['proposer']['symbolic_models']
        frozen = json.loads(reference_path.read_text(encoding='utf-8'))
        if frozen['status']!='complete' or frozen['domain']!=report['domain']:
            raise ValueError('complete same-domain reference required')
        for point,row in zip(domain.points,frozen['points']):
            data = outputs[point]
            vectors = frontier(data).to_dict('records')
            if vectors!=row['vectors']:
                report['frontier_differences'].append(dict(architecture=asdict(point),
                    expected_rows=len(row['vectors']),actual_rows=len(vectors)))
                if not collect_differences and method!='demand':
                    raise AssertionError(f'complete native relaxed-policy frontier differs: {point}')
            selected = selected_rows[point]
            witness = validate_pick(case,(point.px,point.py),point.capacity_bytes,selected)
            if not witness['ok'] or (not witness['feasible'] and method!='demand'):
                raise AssertionError('physical source reconstruction failed')
            if selected is not None:
                witness['mapping'] = encode(selected['Total<SEP>mapping']())
            report['points'].append(dict(architecture=asdict(point),vectors=vectors,witness=witness))
        report['budget_selections'] = []
        for budget_index,budget in enumerate(budgets):
            point,row,winning_witness = winners[budget_index]
            baseline_edp = min(v['Total<SEP>energy']*v[common.LATENCY]
                for p,r in zip(domain.points,frozen['points']) if budget.admits(p) for v in r['vectors'])
            canonical = winning_witness['edp']
            if 'budget_selections' in frozen:
                baseline_canonical = frozen['budget_selections'][budget_index]['witness']['edp']
            else:
                baseline_canonical = frozen['global_selections'][budget_index]['winner']['witness']['edp']
            report['budget_selections'].append(dict(budget=asdict(budget),architecture=asdict(point),
                reported_edp=float(row['Total<SEP>energy'])*float(row[common.LATENCY]),reference_edp=baseline_edp,
                canonical_edp=canonical,reference_canonical_edp=baseline_canonical,witness=winning_witness))
        report['quality_gate_passed'] = all(b['canonical_edp']<=b['reference_canonical_edp'] for b in report['budget_selections'])
        report['quality_comparison'] = 'canonical native physical reevaluation; raw float32 reported values retained separately'
        report.update(status='complete',all_declared_full_frontiers_exact=not report['frontier_differences'],
            all_selected_physical_sources_valid=True,reference_sha256=hashlib.sha256(reference_path.read_bytes()).hexdigest())
        report['source_after'] = source_digest()
        if report['source_before']!=report['source_after']:
            raise AssertionError('source changed during experiment')
        save()
        print(json.dumps(dict(status='complete',search_s=report['search_s'],work=report['work'],
                              canonical_edp=[b['canonical_edp'] for b in report['budget_selections']])),flush=True)
    except Exception as error:
        report.update(status='failed',error=f'{type(error).__name__}: {error}')
        save()
        raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workload',choices=('3mm','attention','attention256','attention512'),default='attention')
    parser.add_argument('--domain',choices=('original12','factors96'),default='factors96')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--collect-differences',action='store_true')
    parser.add_argument('--method',choices=('direct','demand'),default='direct')
    parser.add_argument('--rounds',type=int,choices=(1,2),default=1)
    parser.add_argument('--seed-wave',action='store_true')
    args = parser.parse_args()
    run(args.workload,args.domain,args.output,args.reference,args.collect_differences,args.method,args.rounds,args.seed_wave)


if __name__=='__main__':
    main()
