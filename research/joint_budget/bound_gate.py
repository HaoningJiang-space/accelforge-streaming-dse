"""A0/A1: admissibility and oracle-incumbent ceiling, never used by search."""
import argparse
from dataclasses import asdict
from fractions import Fraction
import json
from pathlib import Path

from research.tracking_audit.common import Case
from .analytic_bounds import audit_vectors, check_frozen_inputs, lower_bound
from .protocol import Domain, Hardware, registered_budgets


def audit(path):
    check_frozen_inputs()
    report = json.loads(path.read_text(encoding='utf-8'))
    if report['status'] != 'complete':
        raise ValueError('complete native result required')
    domain = Domain(tuple(Hardware(**p) for p in report['domain']))
    case = Case('matmuls', 'nvdla', (3, 256, 256))
    result = dict(reference=str(path), scope='diagnostic upper limit, forbidden as a search seed', modes={})
    for mode in ('configured', 'shape'):
        checks = audit_vectors(case, domain, report['points'], mode)
        ceilings = []
        for budget in registered_budgets():
            edp = min(v['Total<SEP>energy']*v['Total<SEP>latency']
                for p, record in zip(domain.points, report['points']) if budget.admits(p)
                for v in record['vectors'])
            prunable = [asdict(p) for p in domain.points if budget.admits(p)
                        and lower_bound(case, p, mode).edp > Fraction.from_float(edp)]
            ceilings.append(dict(budget=asdict(budget), oracle_edp=edp, prunable=prunable))
        result['modes'][mode] = dict(admissibility=checks, oracle_ceiling=ceilings)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.reference)
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({mode:[len(c['prunable']) for c in row['oracle_ceiling']]
                      for mode, row in result['modes'].items()}))


if __name__ == '__main__':
    main()
