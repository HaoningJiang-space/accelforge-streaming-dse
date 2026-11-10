"""Freeze direct conditional-interface predictions without importing a solver."""
import argparse
import hashlib
import json
from math import isfinite
from pathlib import Path
import subprocess

from .two_contraction_response import solve_response, group_response

HERE = Path(__file__).parent
SHAPES = ((1,1,1),(1,6,4),(6,1,5),(4,6,1),(3,6,5),(4,9,2),
          (6,10,3),(5,12,4),(8,6,9),(2,15,7),(7,8,3),(12,15,8),(8,2,8))
SOURCES = ('two_contraction_response.py','freeze_two_contraction_interfaces.py',
           'TWO_CONTRACTION_INTERFACES.md','graph/curve.py','graph/model.py',
           'graph/analysis.py','simulate_nest.py','test_scalar_bridge.py','test_streamed_bridge.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    rows = []
    for shape in SHAPES:
        for p,q in ((False,False),(True,False),(False,True),(True,True)):
            for domain in ('halving','divisors'):
                for entry,fn in (('solve',solve_response),('group',group_response)):
                    for capacity in range(max(4,sum(shape)+1)+1):
                        value = fn(*shape,capacity,p,q,domain)
                        rows.append(dict(shape=shape,resident_in=p,resident_out=q,domain=domain,
                                         entry=entry,capacity=capacity,extra=value if isfinite(value) else None))
    result = dict(base_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        protocol='TWO_CONTRACTION_INTERFACES.md',
        source_sha256={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in SOURCES},
        scope='Prospective direct interface checks; two-contraction root normal forms were already known.',
        cases=len(SHAPES)*16,points=len(rows),predictions=rows)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(cases=result['cases'],points=result['points'])))


if __name__ == '__main__':
    main()
