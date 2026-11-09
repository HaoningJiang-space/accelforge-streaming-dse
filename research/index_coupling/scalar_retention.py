"""Two-scope scalar-X construction and exact search inside six strip families.

See SCALAR_RETENTION_PROOF.md. No reference-model/table access occurs here.
"""
from dataclasses import dataclass, asdict

from .constructive_fork import Plan, ceildiv, frontier
from .tiled_fork import TiledPlan


@dataclass(frozen=True)
class ScalarPlan:
    shape: tuple
    cross: bool
    outer: str
    tile: int

    def __post_init__(self):
        if len(self.shape)!=4 or any(type(n) is not int or n<1 for n in self.shape):
            raise ValueError('four positive integer extents required')
        if self.outer not in ('I','K') or type(self.cross) is not bool:
            raise ValueError('invalid interface or pattern')
        n=self.shape[0 if self.outer=='I' else 2]
        if type(self.tile) is not int or not 1<=self.tile<=n:
            raise ValueError('invalid strip width')

    def metrics(self):
        i,j,k,l=self.shape; b=self.tile
        if self.outer=='I':
            p=ceildiv(i,b)
            reads=dict(A=i*j,B=p*j*k,C=p*k*l,D=i*l if self.cross else p*k*l)
            writes=dict(U=i*l,V=p*k*l if self.cross else i*l)
            if self.cross and p>1: reads['V']=(p-1)*k*l
        else:
            p=ceildiv(k,b)
            reads=dict(A=p*i*j,B=j*k,C=k*l,D=p*i*l if self.cross else k*l)
            writes=dict(U=p*i*l,V=k*l if self.cross else p*i*l)
            if p>1:
                reads['U']=(p-1)*i*l
                if not self.cross: reads['V']=(p-1)*i*l
        return dict(peak=(b+1)*(j+2*l)+1,traffic=sum(reads.values())+sum(writes.values()),
                    reads=dict(sorted(reads.items())),writes=dict(sorted(writes.items())))

    def record(self):
        return dict(asdict(self),kind='scalar_retention',**self.metrics())


def widths(n,all_tiles=False):
    return range(1,n+1) if all_tiles else sorted({n}|{1<<b for b in range(n.bit_length())})


def candidates(shape,cross,all_tiles=False):
    for outer,n in (('I',shape[0]),('K',shape[2])):
        for b in widths(n,all_tiles):
            yield ScalarPlan(tuple(shape),cross,outer,b)


def representations(shape,cross,outer,b):
    if outer=='I':
        return (Plan(tuple(shape),cross,'rows',b),
                TiledPlan(tuple(shape),cross,'I',b,1,('A','U','D' if cross else 'V')),
                ScalarPlan(tuple(shape),cross,'I',b))
    return (Plan(tuple(shape),cross,'cols',b),
            TiledPlan(tuple(shape),cross,'K',1,b,('B','C','V' if cross else 'D')),
            ScalarPlan(tuple(shape),cross,'K',b))


def best_representation(shape,cross,outer,b):
    # Theorem: costs are identical; compare three affine peak formulas only.
    _,j,_,l=shape; n=shape[2 if outer=='I' else 0]; h=j+2*l
    peaks=(b*(n+1)+1,b*(h+1)+1,(b+1)*h+1)
    chosen=min(range(3),key=peaks.__getitem__)
    if chosen==0: return Plan(tuple(shape),cross,'rows' if outer=='I' else 'cols',b)
    if chosen==1:
        return (TiledPlan(tuple(shape),cross,'I',b,1,('A','U','D' if cross else 'V')) if outer=='I'
                else TiledPlan(tuple(shape),cross,'K',1,b,('B','C','V' if cross else 'D')))
    return ScalarPlan(tuple(shape),cross,outer,b)


def query(shape,cross,capacity,all_tiles=True):
    if type(capacity) is not int or capacity<0: raise ValueError('nonnegative integer capacity')
    ScalarPlan(tuple(shape),cross,'I',1)  # validate dimensions/pattern
    i,j,k,l=shape; h=j+2*l; kept=[]
    for outer,n,other in (('I',i,k),('K',k,i)):
        b=min(n,max((capacity-1)//(other+1),(capacity-1)//(h+1),(capacity-1)//h-1))
        if b<1: continue
        if not all_tiles and b!=n: b=1<<(b.bit_length()-1)
        p=ceildiv(n,b); low=ceildiv(n,p)
        if not all_tiles: low=min(n,1<<((low-1).bit_length()))
        kept.append(best_representation(shape,cross,outer,low))
    return min(kept,key=lambda p:(p.metrics()['traffic'],p.metrics()['peak'])) if kept else None


def quotient_starts(n):
    b=1
    while b<=n:
        yield b
        p=ceildiv(n,b)
        if p==1: break
        b=(n-1)//(p-1)+1


def compile_frontier(shape,cross,all_tiles=True):
    plans=[]
    for outer,n in (('I',shape[0]),('K',shape[2])):
        for b in (quotient_starts(n) if all_tiles else widths(n)):
            plans.append(best_representation(shape,cross,outer,b))
    return frontier(plans),len(plans)


def execute(plan):
    """Independent cell events: no metrics(), traffic formula or reference model."""
    from .nest_model import coupling
    from .simulate_nest import Specification,Machine
    spec=Specification(coupling(*plan.shape,plan.cross)); machine=Machine(spec)
    left=('A','U','D' if plan.cross else 'V')
    right=('B','C','V' if plan.cross else 'D')
    outer=plan.outer; inner='K' if outer=='I' else 'I'
    held,local=(left,right) if outer=='I' else (right,left)
    bounds=spec.bounds
    for start in range(0,len(bounds[outer]),plan.tile):
        ob=dict(bounds,**{outer:range(start,min(start+plan.tile,len(bounds[outer])))})
        persisted=spec.cells(held,ob); machine.allocate(persisted)
        for u in bounds[inner]:
            ib=dict(ob,**{inner:range(u,u+1)})
            streamed=spec.cells(local,ib); machine.allocate(streamed)
            for v in ob[outer]:
                cb=dict(ib,**{outer:range(v,v+1)})
                x=spec.cells(('X',),cb); machine.allocate(x)
                for op in spec.ops:
                    for it in spec.iterations(op,cb): machine.step(op,it)
                machine.release(x)
            machine.release(streamed)
        machine.release(persisted)
    return machine.finish()
