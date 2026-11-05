"""Independent integer max-affine interpreter for a CLOSED prepared scope only.

This is a trace-program model, not an arbitrary Fusion or physical-plan IR.
No native Join/resource/Pareto implementation is called here.
"""
from dataclasses import dataclass

LIMIT=(1<<62)-1


class Unsupported(ValueError):
    pass


def parse(column):
    parts=column.split('<SEP>')
    if len(parts)!=4 or parts[0]!='reservation' or parts[3]not in ('left','right'):
        return None
    try:level=int(parts[2])
    except ValueError:return None
    return parts[1],level,parts[3]


def exact(value):
    number=int(value)
    if value!=number or number<0 or number>LIMIT:
        raise Unsupported('nonnegative exact bounded resource required')
    return number


def canonical(terms):
    terms=tuple(sorted(set(terms)))
    if not terms or len(terms)>128:
        raise Unsupported('max-affine term budget')
    return tuple(t for t in terms if not any(t!=u and t[1]<=u[1]and
        all(a<=b for a,b in zip(t[0],u[0]))for u in terms))


def plus(a,b):
    return canonical((tuple(x+y for x,y in zip(c,d)),v+w)for c,v in a for d,w in b)


@dataclass(frozen=True)
class ClosedEffect:
    variables:tuple
    outputs:tuple

    def evaluate(self,coordinates):
        values=tuple(exact(coordinates[c])for c in self.variables)
        def identity(c):
            role,_,column=c.rpartition('::')
            return role,parse(column)
        for role,resource in {(identity(c)[0],identity(c)[1][0])for c in self.variables}:
            ordered=sorted((identity(c)[1][1],coordinates[c])for c in self.variables
                if identity(c)[0]==role and identity(c)[1][0]==resource)
            if any(x[1]>y[1]for x,y in zip(ordered,ordered[1:])):
                raise Unsupported('consumer prefixes are not nested')
        result={c:max(v+sum(k*x for k,x in zip(coeff,values))for coeff,v in terms)
            for c,terms in self.outputs}
        if any(v>LIMIT for v in result.values()):
            raise Unsupported('effect result exceeds exact range')
        return result

    def record(self):
        return dict(variables=list(self.variables),outputs={c:[dict(coefficients=list(a),intercept=b)
            for a,b in terms]for c,terms in self.outputs})


def namespaced(effect,role):
    if any('::'in c for c in effect.variables):raise Unsupported('effect already namespaced')
    return ClosedEffect(tuple(role+'::'+c for c in effect.variables),effect.outputs)


def chain_root_max(previous,right_columns,role):
    """Only a root barrier: empty add program, no alloc/free/alias, RHS level 0.

    Scope preparation renames prior root right -> root left; closing then takes
    max of it and the next stage's root. No native implementation is invoked.
    """
    right_columns=tuple(sorted(right_columns))
    if any(parse(c)is None or parse(c)[1:]!=(0,'right')for c in right_columns):
        raise Unsupported('root-only sequential barrier required')
    variables=previous.variables+tuple(role+'::'+c for c in right_columns)
    if len(set(variables))!=len(variables):raise Unsupported('variable namespace collision')
    env={c:tuple((a+(0,)*len(right_columns),b)for a,b in terms)for c,terms in previous.outputs}
    for i,c in enumerate(right_columns):
        term=(tuple(int(j==len(previous.variables)+i)for j in range(len(variables))),0)
        env[c]=canonical((*env.get(c,()),term))
    return ClosedEffect(variables,tuple(sorted(env.items())))


def compile_closed(left,right_columns,operations):
    """Input is already prepared. Caller rejects alloc/free/alias adjustments."""
    left={c:exact(v)for c,v in left.items()if parse(c)is not None}
    variables=tuple(sorted(c for c in right_columns if parse(c)is not None))
    if len(variables)>16 or any(parse(c)[1]<0 for c in (*left,*variables)):
        raise Unsupported('unsupported variable arity/persistent scope')
    if any(parse(c)[2]!='right'for c in variables):
        raise Unsupported('consumer has left reservations')
    const=lambda v:(((0,)*len(variables),v),)
    env={c:const(v)for c,v in left.items()}
    for i,c in enumerate(variables):
        dest=c+'_RIGHT_MERGE'if c in left else c
        env[dest]=((tuple(int(i==j)for j in range(len(variables))),0),)
    for target,source in operations:
        if parse(target)is None:
            continue
        if source not in env:
            raise Unsupported('missing resource source')
        env[target]=plus(env.get(target,const(0)),env[source])
    env={c:v for c,v in env.items()if not c.endswith('_RIGHT_MERGE')}
    for resource in sorted({parse(c)[0]for c in env}):
        lhs=[c for c in env if parse(c)[0]==resource and parse(c)[2]=='left']
        rhs=sorted((c for c in env if parse(c)[0]==resource and parse(c)[2]=='right'
            and parse(c)[1]>=1),key=lambda c:parse(c)[1])
        selected=lhs+rhs[-1:]
        target=f'reservation<SEP>{resource}<SEP>0<SEP>right'
        if selected:
            if target in env:selected.append(target)
            new=canonical(t for c in selected for t in env[c])
            for c in lhs+rhs:env.pop(c,None)
            env[target]=new
    if any(parse(c)[1:]!=(0,'right')for c in env):
        raise Unsupported('scope did not close')
    return ClosedEffect(variables,tuple(sorted(env.items())))


def concrete_oracle(left,right,operations):
    """Separate scalar interpreter, with no expression/algebra helper calls."""
    state=dict(left)
    for name,value in right.items():
        state[name+'_RIGHT_MERGE'if name in left else name]=value
    for destination,source in operations:
        if destination.startswith('reservation<SEP>'):
            state[destination]=state.get(destination,0)+state[source]
    state={c:v for c,v in state.items()if not c.endswith('_RIGHT_MERGE')}
    resources={c.split('<SEP>')[1]for c in state}
    answer={}
    for resource in resources:
        values=[];deepest=None
        for name,value in state.items():
            _,r,level,side=name.split('<SEP>')
            if r!=resource:continue
            if side=='left' or int(level)==0:values.append(value)
            elif deepest is None or int(level)>deepest[0]:deepest=(int(level),value)
        if deepest is not None:values.append(deepest[1])
        answer[f'reservation<SEP>{resource}<SEP>0<SEP>right']=max(values)
    return answer
