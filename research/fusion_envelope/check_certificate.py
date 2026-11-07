"""Standalone rational replay. Uses no SciPy, SymPy, NumPy or native mapper.

Checks the serialized LP proof, aggregation, cut witnesses and complete finite
reference vectors. Native-to-relaxation inclusion remains a separate model proof.
"""
import argparse
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from research.joint_budget.analytic_bounds import lower_bound
from research.joint_budget.protocol import Hardware, ResourceBudget
from .correlated import minimum_product


def log2_floor(value):
    value = F(value)
    result = value.numerator.bit_length()-value.denominator.bit_length()
    power = F(2**result) if result>=0 else F(1,2**(-result))
    return result-1 if power>value else result


def affine(model,kind,weights):
    c0 = F(model['objectives'][0]['constant'])
    c = {int(i):F(v) for i,v in model['objectives'][0]['terms'].items()}
    if kind==0:
        return c0,c
    t0 = F(model['objectives'][1]['constant'])
    t = {int(i):F(v) for i,v in model['objectives'][1]['terms'].items()}
    if kind==1:
        return t0,t
    weight = weights[kind-2]
    for i,v in t.items():
        c[i] = c.get(i,F())+weight*v
    return c0+weight*t0,c


def checked_function(model,constant,c,dual):
    dual = [F(v) for v in dual]
    if len(dual)!=len(model['rows']) or any(v>0 for v in dual):
        raise AssertionError('bad LP dual sign or length')
    at = [F() for _ in model['upper']]
    for row,y in zip(model['rows'],dual):
        for i,a in row.items():
            at[int(i)] += F(a)*y
    residual = sum(max(F(),a-c.get(i,F()))*F(u) for i,(a,u) in enumerate(zip(at,model['upper'])))
    bias,parameters = constant-residual,{}
    for (rhs,scale,parameter),y in zip(model['rhs'],dual):
        bias += F(rhs)*y/F(scale)
        if parameter is not None:
            key = tuple(parameter)
            parameters[key] = parameters.get(key,F())+y/F(scale)
    return bias,parameters


def evaluate(function,point):
    value,parameters = function
    for parameter,coefficient in parameters.items():
        if parameter[0]=='memory':
            rhs = point.capacity_bytes*8 if parameter[1]=='GlobalBuffer' else 8
        else:
            fanout = point.px if parameter[1]=='reuse_input' else point.py
            rhs = log2_floor(F(fanout)/F(parameter[2]))
        value += coefficient*rhs
    return value


def verify(path,reference_path):
    report = json.loads(path.read_text(encoding='utf-8'))
    ref = json.loads(reference_path.read_text(encoding='utf-8'))
    if report['status']!='complete' or ref['status']!='complete' or report['domain']!=ref['domain']:
        raise AssertionError('complete reports on identical domain required')
    if report['reference_sha256']!=hashlib.sha256(reference_path.read_bytes()).hexdigest():
        raise AssertionError('reference fingerprint changed')
    case = SimpleNamespace(**report['case'])
    weights = [F(w) for w in report.get('lp_weights',[])]
    functions,impossible = {},{}
    dual_count = 0
    for label,duals in report.get('duals',{}).items():
        key,kind = label.rsplit(':',1)
        model = report['models'][key]
        constant,c = affine(model,int(kind),weights)
        functions[(key,int(kind))] = [checked_function(model,constant,c,dual) for dual in duals]
        dual_count += len(duals)
    for cert in report.get('infeasibility',[]):
        model = report['models'][cert['key']]
        function = checked_function(model,F(),{},cert['dual'])
        if evaluate(function,Hardware(**cert['architecture'])) <= 0:
            raise AssertionError('invalid exact infeasibility contradiction')
        impossible.setdefault(cert['key'],[]).append(function)
    catalogs = {tuple(c['shape']):c['operators'] for c in report.get('catalogs',[])}
    for saved in report['bounds']:
        point = Hardware(**saved['architecture'])
        analytic = lower_bound(case,point)
        total = [F()]*(2+len(weights))
        is_impossible = False
        if catalogs:
            for name,keys in catalogs[(point.px,point.py)].items():
                rows = []
                for key in keys:
                    if any(evaluate(f,point)>0 for f in impossible.get(key,[])):
                        continue
                    rows.append([max([F()]+[evaluate(f,point) for f in functions.get((key,k),[])])
                                 for k in range(len(total))])
                if not rows:
                    is_impossible = True
                    break
                for k in range(len(total)):
                    total[k] += min(row[k] for row in rows)
        if saved['infeasible']:
            if not is_impossible:
                raise AssertionError('unsupported hardware infeasibility assertion')
            continue
        if not is_impossible:
            energy = max(analytic.energy,total[0]/10**6*F(99,100))
            latency = max(analytic.latency,total[1]/10**6*F(99,100))
            lines = [(w,v/10**6*F(99,100)) for w,v in zip(weights,total[2:])]
            bound,_,_ = minimum_product(energy,latency,lines)
            if energy<F(saved['energy']) or latency<F(saved['latency']) or bound<F(saved['edp']):
                raise AssertionError('saved lower bound exceeds independently reconstructed proof')
    lookup = {tuple(r['architecture'].values()):r['vectors'] for r in ref['points']}
    vectors = 0
    for saved in report['bounds']:
        rows = lookup[tuple(saved['architecture'].values())]
        if saved['infeasible'] and rows:
            raise AssertionError('infeasible region contains native reference vectors')
        for row in rows:
            e,t = F.from_float(row['Total<SEP>energy']),F.from_float(row['Total<SEP>latency'])
            if e<F(saved['energy']) or t<F(saved['latency']) or e*t<F(saved['edp']):
                raise AssertionError('reference violates saved lower bound')
            for w,v in saved.get('weighted_bounds',[]):
                if e+F(w)*t<F(v):
                    raise AssertionError('reference violates correlated support line')
            vectors += 1
    for cert in report['certificates']:
        saved = report['bounds'][cert['bound_index']]
        if saved['architecture']!=cert['architecture']:
            raise AssertionError('cut bound refers to another hardware')
        for w in cert['witnesses']:
            found = report['trajectory'][w['witness_index']]
            budget = ResourceBudget(**report['budgets'][w['budget_index']])
            if (found['elapsed_s']>cert['elapsed_s'] or not budget.admits(Hardware(**found['architecture']))
                or F(found['cutoff'])!=F(w['cutoff']) or F(saved['edp'])<F(w['cutoff'])
                or not found['witness']['feasible'] or not found['witness']['ok']):
                raise AssertionError('invalid physical-incumbent cut')
    for budget,selected in zip(report['budgets'],report['budget_selections']):
        budget = ResourceBudget(**budget)
        best = min(v['Total<SEP>energy']*v['Total<SEP>latency']
                   for p,r in zip(report['domain'],ref['points']) if budget.admits(Hardware(**p)) for v in r['vectors'])
        if best!=selected['edp']:
            raise AssertionError('global EDP changed')
    return dict(status='verified',dual_functions=dual_count,hardware_bounds=len(report['bounds']),
        full_native_vectors=vectors,physical_incumbent_cuts=len(report['certificates']),
        global_edp_exact=True,scope='finite native-policy experiment; model inclusion proof remains separate')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    result = verify(args.report,args.reference)
    if args.output:
        args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':
    main()
