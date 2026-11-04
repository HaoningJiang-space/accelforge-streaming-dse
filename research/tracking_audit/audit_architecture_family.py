"""Prove a synthetic family using two corners; enumerate only for post-audit."""
import argparse
from dataclasses import asdict
from fractions import Fraction
import hashlib
from itertools import product
import json
from pathlib import Path

from research.tracking_audit.architecture_family_certificate import ArchitectureBox, certify_family
from research.tracking_audit.graph_cut_bound import Architecture, Branch, Model, branch_bound, complete_cost


def run(output):
    model = Model(128,192,1,4)
    box = ArchitectureBox(((2,3),(4,6),(32,36),(2,3)))
    seed, branch = Branch('stream',4,2,0,False),Branch('barrier',64,24,0,True)
    extras = (0,1,13,27)
    # The certificate has no query points: exactly two corner evaluations.
    proof = certify_family(model,box,branch,seed,0)
    if proof['status'] != 'certified' or proof['corner_evaluations'] != 2:
        raise AssertionError('expected a nontrivial full-box proof')
    checked=[]
    # Post-hoc exhaustive verification is deliberately outside the proof.
    for point in product(*(range(lo,hi+1) for lo,hi in box.ranges)):
        arch = Architecture(*point)
        upper = complete_cost(model,arch,seed,0)
        lower = branch_bound(model,arch,branch)
        alternatives = [complete_cost(model,arch,branch,x) for x in extras]
        if upper is None or lower is None or not upper <= lower <= min(alternatives):
            raise AssertionError('family certificate failed its exhaustive check')
        checked.append(dict(architecture=point,seed_cost=str(upper),branch_lower=str(lower),
                            best_enumerated_completion=str(min(alternatives))))
    if len(checked)!=box.count:
        raise AssertionError('incomplete post-hoc architecture enumeration')
    root=Path(__file__).parent
    names=('audit_architecture_family.py','architecture_family_certificate.py','graph_cut_bound.py',
           'test_architecture_family_certificate.py')
    report=dict(scope='synthetic fixed-cost monotone model; not an FFM architecture certificate',
        model=asdict(model),box=box.ranges,seed=asdict(seed),branch=asdict(branch),extras=extras,
        proof=proof,post_audit_architectures=len(checked),post_audit=checked,
        source_sha256={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names})
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(proof=proof,post_audit_architectures=len(checked))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output)
