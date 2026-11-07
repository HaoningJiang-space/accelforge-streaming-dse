"""Audit an LP envelope against complete native reference frontiers."""
import argparse
from dataclasses import asdict
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import time

from research.tracking_audit.common import Case
from research.joint_budget.protocol import Hardware
from .native import NativeEnvelope


def run(reference,output):
    source = json.loads(reference.read_text(encoding='utf-8'))
    case = Case(**source['case'])
    case = Case(case.workload,case.arch,tuple(case.params))
    if source['status'] != 'complete' or len(source['points']) != len(source['domain']):
        raise ValueError('complete exhaustive native reference required')
    points = [Hardware(**p) for p in source['domain']]
    report = dict(status='running',case=asdict(case),points=[],
                  reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),
                  role='diagnostic only; reference cannot seed real search')
    started = time.perf_counter()
    envelope = NativeEnvelope(case)
    try:
        for point,row in zip(points,source['points']):
            bound = envelope.bound(point)
            if bound['infeasible'] and row['vectors']:
                raise AssertionError('LP declares native feasible hardware infeasible')
            if not bound['infeasible']:
                for v in row['vectors']:
                    if F.from_float(v['Total<SEP>energy']) < bound['energy'] or F.from_float(v['Total<SEP>latency']) < bound['latency']:
                        raise AssertionError(f'LP lower bound violation: {point}: {bound} vs {v}')
            record = dict(architecture=asdict(point),bound=bound,checked_vectors=len(row['vectors']))
            report['points'].append(record)
            print(json.dumps(dict(architecture=asdict(point),energy=float(bound.get('energy',0)),
                latency=float(bound.get('latency',0)),elapsed_s=time.perf_counter()-started,
                stats=envelope.stats)),flush=True)
        report.update(status='complete',elapsed_s=time.perf_counter()-started,
                      stats=envelope.stats,unsupported=envelope.unsupported,
                      duals=envelope.serialize_duals(),all_finite_reference_bounds_admissible=True,
                      models=envelope.serialize_models(),infeasibility=envelope.infeasibility,
                      sota_acceptance=False)
    except Exception as error:
        report.update(status='failed',error=f'{type(error).__name__}: {error}',elapsed_s=time.perf_counter()-started,
                      stats=envelope.stats,unsupported=envelope.unsupported)
        raise
    finally:
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,default=str,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    run(args.reference,args.output)


if __name__ == '__main__':
    main()
