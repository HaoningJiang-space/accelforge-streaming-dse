"""Cross-shape, nondefault-cost differential checks after Oracle hardening."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from random import Random

from .graph_ir import TwoMM, CostModel
from .validate import audit


def review_cases():
    # Fixed seeds make these positive random coefficients reproducible.
    # Shapes exercise row/column degeneracy and unrelated tile divisors.
    for name,graph,seed in (
        ('row_intermediate',TwoMM(1,2,4,3),20261105),
        ('column_intermediate',TwoMM(3,2,1,2),20261106),
        ('asymmetric',TwoMM(2,3,4,5),20261107),
    ):
        rng=Random(seed)
        model=CostModel(*(rng.randint(1,11) for _ in range(4)))
        yield name,graph,model,seed


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.parent.mkdir(parents=True,exist_ok=True)
    report=dict(status='in_progress',cases=[])
    for name,graph,model,seed in review_cases():
        try:r=audit(graph,model)
        except Exception as exc:
            report.update(status='failed',failure_case=name,error=str(exc))
            args.output.write_text(json.dumps(report,indent=2)+'\n');raise
        r.update(name=name,cost_seed=seed)
        report['cases'].append(r)
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(dict(name=name,graph=asdict(graph),model=asdict(model),
            local_checks=r['local_summaries_checked'],complete_checks=r['composition_summaries_checked'],
            root_states=len(r['root_frontier']),queries=r['architecture_queries_checked'])),flush=True)
    report.update(status='complete',speedup_claim=False)
    report['source_sha256']={str(f):hashlib.sha256(f.read_bytes()).hexdigest()
        for f in Path(__file__).parent.glob('*.py')}
    args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
