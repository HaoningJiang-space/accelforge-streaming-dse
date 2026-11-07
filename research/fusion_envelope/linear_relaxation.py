"""Discrete exponential LP relaxation with exact rational dual checking.

Native perfect tiles are powers of two. For integer z, the line
2**k * (z-k+1) <= 2**z holds for every integer k. These lines produce an LP
containing every integer-log native assignment, without enumerating tile tuples.
Negative monomials use the chord over their complete exponent range instead.
"""
from dataclasses import dataclass
from fractions import Fraction as F

import numpy as np
from scipy.optimize import linprog
import sympy as sp


@dataclass
class Affine:
    constant: F
    terms: dict

    def scale(self, factor):
        return Affine(self.constant*factor, {k:v*factor for k,v in self.terms.items()})

    def plus(self, other):
        terms = dict(self.terms)
        for k,v in other.terms.items():
            terms[k] = terms.get(k,F())+v
        return Affine(self.constant+other.constant, {k:v for k,v in terms.items() if v})


def fraction(value):
    if isinstance(value, (sp.Integer, sp.Rational)):
        return F(int(value.p), int(value.q))
    if isinstance(value, sp.Float):
        return F(float(value))
    return F(value)


def power_two(exponent):
    return F(2**exponent) if exponent >= 0 else F(1,2**(-exponent))


def floor_log_two(value):
    value = F(value)
    if value <= 0:
        raise ValueError('positive logarithm argument required')
    result = value.numerator.bit_length()-value.denominator.bit_length()
    return result-1 if power_two(result) > value else result


class Relaxation:
    def __init__(self, symbols, bounds):
        self.symbols = tuple(symbols)
        self.indices = {s:i for i,s in enumerate(self.symbols)}
        self.upper = [F(floor_log_two(bounds[s])) for s in self.symbols]
        self.rows, self.rhs, self.monomials = [], [], {}
        self.finished = False

    def variable(self, upper):
        index = len(self.upper)
        self.upper.append(F(upper))
        return Affine(F(), {index:F(1)})

    def constrain(self, affine, rhs, parameter=None):
        """affine <= rhs; optional RHS supplied by target architecture."""
        if self.finished:
            raise RuntimeError('LP already finalized')
        maximum = max([F(1)] + [abs(v) for v in affine.terms.values()])
        exponent = floor_log_two(maximum)
        scale = power_two(exponent if power_two(exponent)==maximum else exponent+1)
        self.rows.append({i:v/scale for i,v in affine.terms.items()})
        self.rhs.append((F(rhs)-affine.constant, scale, parameter))

    def monomial(self, exponent):
        if exponent in self.monomials:
            return self.monomials[exponent]
        lo = sum(min(0,e*u) for e,u in zip(exponent,self.upper[:len(self.symbols)]))
        hi = sum(max(0,e*u) for e,u in zip(exponent,self.upper[:len(self.symbols)]))
        lo,hi = int(lo),int(hi)
        if hi-lo > 128:
            raise ValueError('exponent range exceeds prototype limit')
        # Normalize the epigraph variable to [0,1]. This improves conditioning.
        result = self.variable(1)
        z = Affine(F(), {i:F(e) for i,e in enumerate(exponent) if e})
        for k in range(lo,hi+1):
            line = z.plus(Affine(F(1-k),{})).scale(power_two(k-hi))
            self.constrain(line.plus(result.scale(-1)), 0)
        result = result.scale(power_two(hi))
        self.monomials[exponent] = result
        return result

    def parse_terms(self, expression):
        terms = []
        for term in sp.Add.make_args(sp.expand(expression)):
            powers = term.as_powers_dict()
            exponents = []
            product = sp.Integer(1)
            for symbol in self.symbols:
                exponent = powers.get(symbol,0)
                if not sp.sympify(exponent).is_Integer:
                    raise ValueError('integer Laurent exponents required')
                exponents.append(int(exponent))
                product *= symbol**exponent
            coefficient = sp.cancel(term/product)
            if coefficient.free_symbols or not coefficient.is_Number:
                raise ValueError(f'unsupported symbolic term: {term}')
            terms.append((fraction(coefficient), tuple(exponents)))
        return terms

    def lower(self, expression, scale=F(1)):
        expression = sp.sympify(expression)
        if expression.func.__name__ == 'Max':
            if max(self.interval_lower(arg) for arg in expression.args)<0:
                raise ValueError('nonnegative Max auxiliary is not proved for this expression')
            branches = [self.lower(arg, scale) for arg in expression.args]
            upper = max(self.interval_upper(arg)*scale for arg in expression.args)
            result = self.variable(max(0,upper))
            for branch in branches:
                self.constrain(branch.plus(result.scale(-1)),0)
            return result
        result = Affine(F(),{})
        for coefficient, exponent in self.parse_terms(expression):
            coefficient *= scale
            if not any(exponent):
                result.constant += coefficient
            elif coefficient > 0:
                result = result.plus(self.monomial(exponent).scale(coefficient))
            elif coefficient < 0:
                lo = int(sum(min(0,e*u) for e,u in zip(exponent,self.upper)))
                hi = int(sum(max(0,e*u) for e,u in zip(exponent,self.upper)))
                if lo == hi:
                    result.constant += coefficient*power_two(lo)
                else:
                    slope = (power_two(hi)-power_two(lo))/(hi-lo)
                    chord = Affine(power_two(lo)-lo*slope,
                                   {i:F(e)*slope for i,e in enumerate(exponent) if e})
                    result = result.plus(chord.scale(coefficient))
        return result

    def interval_upper(self, expression):
        expression = sp.sympify(expression)
        if expression.func.__name__ == 'Max':
            return max(self.interval_upper(arg) for arg in expression.args)
        value = F()
        for c, exponent in self.parse_terms(expression):
            bound = int(sum((max if c>=0 else min)(0,e*u) for e,u in zip(exponent,self.upper)))
            value += c*power_two(bound)
        return value

    def interval_lower(self, expression):
        expression = sp.sympify(expression)
        if expression.func.__name__=='Max':
            return max(self.interval_lower(arg) for arg in expression.args)
        value = F()
        for c,exponent in self.parse_terms(expression):
            bound = int(sum((min if c>=0 else max)(0,e*u) for e,u in zip(exponent,self.upper)))
            value += c*power_two(bound)
        return value

    def relation(self, outer, inner):
        def logarithm(value):
            if value in self.indices:
                return Affine(F(),{self.indices[value]:F(1)})
            if power_two(floor_log_two(int(value))) != int(value):
                raise ValueError('power-of-two constant relation required')
            return Affine(F(floor_log_two(int(value))),{})
        self.constrain(logarithm(inner).plus(logarithm(outer).scale(-1)),0)

    def spatial(self, expression, reference_fanout, name):
        terms = self.parse_terms(expression*reference_fanout)
        if len(terms) != 1:
            raise ValueError('one spatial monomial required')
        coefficient, exponent = terms[0]
        self.constrain(Affine(F(),{i:F(e) for i,e in enumerate(exponent) if e}),0,
                       parameter=('spatial',name,coefficient))

    def finalize(self):
        for i,upper in enumerate(self.upper):
            self.constrain(Affine(F(),{i:F(1)}),upper)
        self.finished = True
        self.matrix = np.zeros((len(self.rows),len(self.upper)))
        for r,row in enumerate(self.rows):
            for i,value in row.items():
                self.matrix[r,i] = float(value)

    def target_rhs(self, point):
        values = []
        for constant,scale,parameter in self.rhs:
            if parameter is None:
                rhs = constant
            elif parameter[0] == 'memory':
                rhs = F(point.capacity_bytes*8 if parameter[1]=='GlobalBuffer' else 8)+constant
            elif parameter[0] == 'spatial':
                fanout = point.px if parameter[1]=='reuse_input' else point.py
                rhs = F(floor_log_two(F(fanout)/parameter[2]))+constant
            else:
                raise ValueError('unknown RHS parameter')
            values.append(rhs/scale)
        return values

    def check_dual(self, objective, dual, point):
        """Rational residual correction; solver status/tolerance is not a proof."""
        function = self.compile_dual(objective,dual)
        return self.evaluate_dual(function,point),function[2]

    def compile_dual(self, objective, dual):
        if len(dual) != len(self.rows) or any(y>0 for y in dual):
            raise ValueError('invalid inequality dual')
        coefficients = [F() for _ in self.upper]
        for row,y in zip(self.rows,dual):
            for i,a in row.items():
                coefficients[i] += a*y
        residual = sum(max(F(), a-objective.terms.get(i,F()))*upper
                       for i,(a,upper) in enumerate(zip(coefficients,self.upper)))
        bias = objective.constant-residual
        parameters = {}
        for (constant,scale,parameter),y in zip(self.rhs,dual):
            bias += constant*y/scale
            if parameter is not None:
                parameters[parameter] = parameters.get(parameter,F())+y/scale
        return bias,{k:v for k,v in parameters.items() if v},residual

    @staticmethod
    def evaluate_dual(function,point):
        bias,parameters,_ = function
        value = bias
        for parameter,coefficient in parameters.items():
            if parameter[0]=='memory':
                rhs = point.capacity_bytes*8 if parameter[1]=='GlobalBuffer' else 8
            elif parameter[0]=='spatial':
                fanout = point.px if parameter[1]=='reuse_input' else point.py
                rhs = floor_log_two(F(fanout)/parameter[2])
            value += rhs*coefficient
        return value

    def solve(self, objective, point):
        if not self.finished:
            self.finalize()
        if not self.upper:
            rhs = self.target_rhs(point)
            violating = next((i for i,b in enumerate(rhs) if b<0),None)
            dual = tuple(F(-1) if i==violating else F() for i in range(len(rhs)))
            if violating is not None:
                return dict(bound=None,dual=dual,residual=F(),infeasible=True,
                            contradiction=-rhs[violating],solver_status=0)
            return dict(bound=objective.constant,dual=dual,residual=F(),infeasible=False,solver_status=0)
        c = np.zeros(len(self.upper))
        for i,value in objective.terms.items():
            c[i] = float(value)
        result = linprog(c,A_ub=self.matrix,b_ub=[float(b) for b in self.target_rhs(point)],method='highs',options={'threads':1})
        if result.success:
            dual = tuple(min(F(),F(round(float(y)*2**40),2**40)) for y in result.ineqlin.marginals)
            bound,residual = self.check_dual(objective,dual,point)
            return dict(bound=bound, dual=dual, residual=residual, infeasible=False,
                        solver_status=int(result.status))
        # Numerical infeasibility alone never deletes a template. Search a
        # phase-I dual and verify an exact contradiction for t=0 instead.
        phase = linprog(np.r_[np.zeros(len(c)),1.],
            A_ub=np.column_stack((self.matrix,-np.ones(len(self.rows)))),
            b_ub=[float(b) for b in self.target_rhs(point)],method='highs',options={'threads':1})
        if phase.success:
            dual = tuple(min(F(),F(round(float(y)*2**40),2**40)) for y in phase.ineqlin.marginals)
            contradiction,residual = self.check_dual(Affine(F(),{}),dual,point)
            if contradiction > 0:
                return dict(bound=None, dual=dual, residual=residual, infeasible=True,
                            contradiction=contradiction,solver_status=int(result.status))
        return dict(bound=F(),dual=tuple(F() for _ in self.rows),residual=F(),infeasible=False,
                    solver_status=int(result.status),unknown=True)
