"""Parametric native-cost LP envelope driving real hardware/mapping search.

This controller also supplies identical-order Event and geometry-only controls.
Capacity-specific cuts can shrink the cohort passed to the native Event oracle.
Reference frontiers are opened only after the complete search finishes.
"""
import argparse
from dataclasses import asdict
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
from unittest.mock import patch

from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.enumeration_reuse import EnumerationReuse
from research.joint_budget.analytic_bounds import factor_domain, lower_bound, check_frozen_inputs
from research.joint_budget.protocol import Domain, Hardware, ResourceBudget, registered_domain, registered_budgets
from research.joint_budget.region_search import EventOracle
from research.joint_budget import region_search as oracle_module
from research.joint_search.validation import frontier
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import validate_pick
from .native import NativeEnvelope


class PolicyOracle(EventOracle):
    def __init__(self,case,policy):
        super().__init__(case)
        self.policy = policy

    def solve(self,*args):
        if self.policy=='original':
            return super().solve(*args)
        original_build = oracle_module.build
        def relaxed_build(*pos,**kw):
            spec = original_build(*pos,**kw)
            for dim in spec.arch.find('ArrayFanout').spatial:
                dim.min_usage = 0
            return spec
        with patch.object(oracle_module,'build',relaxed_build):
            return super().solve(*args)


def digest():
    value = hashlib.sha256()
    for root in ('accelforge','research/tracking_audit','research/joint_search','research/joint_budget','research/fusion_envelope'):
        for path in sorted(Path(root).rglob('*.py')):
            value.update(path.as_posix().encode()+b'\0'+path.read_bytes())
    return value.hexdigest()


def problem(workload,domain_name):
    if workload == '3mm':
        case = common.Case('matmuls','nvdla',(3,256,256))
        domain = registered_domain() if domain_name=='original12' else factor_domain()
        budgets = registered_budgets()
    else:
        case = common.Case('attention','nvdla',(128,1,64))
        capacities = (4096,8192,16384,32768)
        domain = factor_domain(capacities=capacities)
        if domain_name=='original12':
            domain = Domain(tuple(p for p in domain.points if (p.px,p.py) in ((16,384),(32,192),(64,96))))
        budgets = tuple(ResourceBudget(6144,c) for c in capacities)
    return case,domain,budgets


def run(method,workload,domain_name,output,reference_path=None,policy='original'):
    case,domain,budgets = problem(workload,domain_name)
    report = dict(status='running',method=method,policy=policy,case=asdict(case),domain=[asdict(p) for p in domain.points],
        budgets=[asdict(b) for b in budgets],workers=1,python=sys.version,platform=platform.platform(),
        source_before=digest(),reference_read_before_search=False,points=[],bounds=[],certificates=[],trajectory=[],
        external_sota_acceptance=False,physical_mapspace_optimality=False,full_global_pareto_preserved=False,
        objective='global EDP',timing_scope='all native/symbolic preparation, LP solves/dual checks, oracle work, queries and improving witness reconstruction')
    def save():
        output.parent.mkdir(parents=True,exist_ok=True)
        temp = output.with_suffix(output.suffix+'.tmp')
        temp.write_text(json.dumps(report,default=str,allow_nan=False,separators=(',',':'))+'\n',encoding='utf-8')
        temp.replace(output)
    save()
    try:
        common.clear_switches()
        common.af.set_n_parallel_jobs(1)
        started = time.perf_counter()
        check_frozen_inputs()
        envelope = NativeEnvelope(case,correlated=method=='correlated') if method in ('lp','correlated') else None
        oracle = PolicyOracle(case,policy)
        incumbents = [None]*len(budgets)
        shapes = sorted({(p.px,p.py) for p in domain.points},key=lambda shape:(
            lower_bound(case,Hardware(*shape,1)).latency,max(shape)/min(shape),shape))
        with EnumerationReuse() as reuse:
            for shape_index,shape in enumerate(shapes):
                points = [p for p in domain.points if (p.px,p.py)==shape]
                needed = []
                for point in points:
                    analytic = lower_bound(case,point)
                    bound = envelope.bound(point,solve=True if shape_index==0 else 'missing') if envelope else dict(
                        infeasible=False,energy=analytic.energy,latency=analytic.latency,edp=analytic.edp,
                        analytic_edp=analytic.edp)
                    affected = [i for i,b in enumerate(budgets) if b.admits(point)]
                    # Separate only a near-competitive unproved cell. The ratio
                    # and anchor order are frozen without reading reference data.
                    if (envelope and shape_index>0 and not bound['infeasible'] and
                        all(incumbents[i] is not None for i in affected)):
                        cutoff = max(incumbents[i]['cutoff'] for i in affected)
                        if F(2,3)*cutoff <= bound['edp'] < cutoff:
                            bound = envelope.bound(point,solve=True)
                    can_cut = method!='events' and (bound['infeasible'] or all(
                        incumbents[i] is not None and bound['edp'] >= incumbents[i]['cutoff'] for i in affected))
                    index = len(report['bounds'])
                    report['bounds'].append(dict(architecture=asdict(point),**bound))
                    if can_cut:
                        report['certificates'].append(dict(architecture=asdict(point),bound_index=index,
                            elapsed_s=time.perf_counter()-started,infeasible=bound['infeasible'],
                            witnesses=[] if bound['infeasible'] else [dict(budget_index=i,
                                witness_index=incumbents[i]['witness_index'],cutoff=str(incumbents[i]['cutoff']))
                                for i in affected]))
                    else:
                        needed.append(point)
                if needed:
                    oracle.solve(shape,needed,reuse)
                    for point in needed:
                        row = common.best_row(oracle.outputs[point])
                        if row is None:
                            continue
                        e,t = float(row['Total<SEP>energy']),float(row[common.LATENCY])
                        edp = e*t
                        updates = [i for i,b in enumerate(budgets) if b.admits(point) and
                                   (incumbents[i] is None or edp<incumbents[i]['edp'])]
                        if not updates:
                            continue
                        witness = validate_pick(case,shape,point.capacity_bytes,row)
                        if not witness['ok'] or not witness['feasible']:
                            raise AssertionError('physical incumbent validation failed')
                        cutoff = F.from_float(max(e,witness['energy']))*F.from_float(max(t,witness['latency']))*F(1000001,1000000)**2
                        record = dict(architecture=asdict(point),energy=e,latency=t,edp=edp,
                            cutoff=cutoff,witness=witness,witness_index=len(report['trajectory']))
                        for i in updates:
                            incumbents[i] = record
                        report['trajectory'].append(dict(**record,budget_indices=updates,
                            elapsed_s=time.perf_counter()-started))
                print(json.dumps(dict(shape=shape,needed_capacities=[p.capacity_bytes for p in needed],
                    native_solves=len(oracle.details),pruned_hardware=len(report['certificates']),
                    elapsed_s=time.perf_counter()-started,lp=envelope.stats if envelope else None)),flush=True)
            cache = dict(reuse.stats)
        report.update(search_s=time.perf_counter()-started,native_solves=len(oracle.details),
            pruned_hardware=len(report['certificates']),oracle_details=oracle.details,cache=cache,
            budget_selections=[dict(budget=asdict(b),**{k:v for k,v in selected.items() if k!='cutoff'})
                               for b,selected in zip(budgets,incumbents)],
            peak_rss_gib_before_validation=common.peak_rss_gb())
        if envelope:
            report['lp_stats'] = envelope.stats
            report['lp_weights'] = envelope.weights
            report['unsupported'] = envelope.unsupported
            report['models'] = envelope.serialize_models()
            report['duals'] = envelope.serialize_duals()
            report['infeasibility'] = envelope.infeasibility
            report['catalogs'] = [{'shape':shape,'operators':cat} for shape,cat in envelope.catalogs.items()]
        for point in domain.points:
            if point in oracle.outputs:
                report['points'].append(dict(architecture=asdict(point),
                    vectors=frontier(oracle.outputs[point]).to_dict('records')))
        if reference_path:
            frozen = json.loads(reference_path.read_text(encoding='utf-8'))
            if frozen['status']!='complete' or frozen['domain']!=report['domain'] or len(frozen['points'])!=len(domain.points):
                raise ValueError('full native reference on identical domain required')
            if frozen['case'] != json.loads(json.dumps(asdict(case))):
                raise ValueError('reference workload differs')
            if frozen.get('policy','original')!=policy:
                raise ValueError('reference mapping policy differs')
            lookup = {tuple(p['architecture'].values()):p for p in frozen['points']}
            for checked in report['bounds']:
                rows = lookup[tuple(checked['architecture'].values())]['vectors']
                if checked['infeasible'] and rows:
                    raise AssertionError('false hardware infeasibility certificate')
                for v in rows:
                    if F.from_float(v['Total<SEP>energy'])<checked['energy'] or F.from_float(v[common.LATENCY])<checked['latency']:
                        raise AssertionError('native full frontier violates LP/analytic bound')
                    e,t = F.from_float(v['Total<SEP>energy']),F.from_float(v[common.LATENCY])
                    for weight,value in checked.get('weighted_bounds',[]):
                        if e+weight*t<value:
                            raise AssertionError('native full frontier violates correlated support line')
                    if e*t<checked['edp']:
                        raise AssertionError('native full frontier violates correlated product bound')
            for actual in report['points']:
                if actual['vectors'] != lookup[tuple(actual['architecture'].values())]['vectors']:
                    raise AssertionError('visited full native frontier changed')
            for budget,selected in zip(budgets,report['budget_selections']):
                best = min(v['Total<SEP>energy']*v[common.LATENCY]
                    for p,r in zip(domain.points,frozen['points']) if budget.admits(p) for v in r['vectors'])
                if best != selected['edp']:
                    raise AssertionError('global EDP differs from exhaustive native reference')
            for cert in report['certificates']:
                bound = report['bounds'][cert['bound_index']]
                for w in cert['witnesses']:
                    witness = report['trajectory'][w['witness_index']]
                    if (w['budget_index'] not in witness['budget_indices'] or
                        witness['elapsed_s']>cert['elapsed_s'] or
                        not budgets[w['budget_index']].admits(Hardware(**witness['architecture'])) or
                        witness['cutoff'] != F(w['cutoff']) or bound['edp'] < F(w['cutoff'])):
                        raise AssertionError('invalid global cut witness')
            report['verification'] = dict(global_edp_exact=True,visited_full_frontiers_exact=True,
                every_full_reference_vector_bound_checked=True,all_cuts_replayed=True)
            report['reference_sha256'] = hashlib.sha256(reference_path.read_bytes()).hexdigest()
        report['source_after'] = digest()
        if report['source_after']!=report['source_before']:
            raise AssertionError('source changed during experiment')
        report['status'] = 'complete'
        save()
        print(json.dumps({k:report[k] for k in ('status','method','search_s','native_solves','pruned_hardware')}),flush=True)
    except Exception as error:
        report.update(status='failed',error=f'{type(error).__name__}: {error}')
        save()
        raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method',choices=('events','shape','lp','correlated'),required=True)
    parser.add_argument('--workload',choices=('3mm','attention'),default='attention')
    parser.add_argument('--domain',choices=('original12','factors96'),default='factors96')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--policy',choices=('original','relaxed'),default='original')
    args = parser.parse_args()
    run(args.method,args.workload,args.domain,args.output,args.reference,args.policy)


if __name__=='__main__':
    main()
