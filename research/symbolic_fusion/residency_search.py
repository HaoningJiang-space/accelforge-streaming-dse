"""Bounded conditional vectors over four real (shape, backing) environments.

This is a controlled experiment against ordinary per-environment DP, not a
claim of an automatic Physical IR compiler or arbitrary continuation algebra.
"""
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
import sympy as sp
from .model import Family,Plan


SHAPES=((32,192),(64,96)) # reuse_input (j), reuse_output (k)
CONTEXTS=('gb','dram')
ENVS=tuple(product(SHAPES,CONTEXTS))


def weak(a,b):return all(x<=y for x,y in zip(a,b))
def add(a,b):return max(a[0],b[0]),a[1]+b[1],a[2]+b[2]


def numeric_frontier(entries):
    result=[]
    for vector,plan in entries:
        if any(weak(v,vector)for v,_ in result):continue
        result=[(v,p)for v,p in result if not weak(vector,v)]
        result.append((vector,plan))
    return result


class Factors:
    def __init__(self,n=256,stripes=(64,128,256),tiles=(32,64),shapes=SHAPES):
        self.base=Family(n,stripes,tiles)
        self.n=n;self.stripes=tuple(stripes);self.tiles=tuple(tiles);self.shapes=tuple(shapes)
        self.envs=tuple(product(self.shapes,CONTEXTS));self.cache={};self.evaluations=0
        N,s,k,j=self.base.symbols;V=N**3
        counts=[list(c)for c in self.base.counts]
        # Explicit copy/drain counts, derived from the frozen physical loops.
        counts[1][0]+=N**2*(N/k-1);counts[1][1]+=V/k
        counts[1][2]+=V/k;counts[1][3]+=N**2*(N/k-1)
        counts[2][0]+=V/j;counts[2][3]+=V/j
        peaks=(N*s+N*k+k*j,N*s+N*j+k*j,N*k+N*j+k*j)
        self.dram=[sp.lambdify(self.base.symbols,(*c,p),'math',cse=True)for c,p in zip(counts,peaks)]
        self.dram_formulas=[dict(counts=[str(e)for e in c],peak=str(p))for c,p in zip(counts,peaks)]

    def options(self,stage,stripe,shape=None):
        for k,j in self.base.legal_tiles(stage,stripe):
            if any(j<=a and k<=b for a,b in ((shape,)if shape else self.shapes)):
                yield k,j

    def get(self,stage,stripe,tile):
        k,j=tile;key=self.base.factor_key(stage,stripe,k,j)
        if key not in self.cache:
            gb=self.base.factor(stage,stripe,k,j).vector
            raw=self.dram[stage](self.n,stripe,k,j)
            if any(int(v)!=v or v<0 or v>=2**53 for v in raw):raise AssertionError('inexact count')
            dr,dw,gr,gw,mac,cycles,peak=map(int,raw)
            energy=(dr+dw)*56240+gr*1992+gw*2344+mac*84
            time=max(Fraction(cycles),Fraction((dr+dw)*5,192),Fraction(gr,512),Fraction(gw,128))
            self.cache[key]=(gb,(peak,energy,time));self.evaluations+=1
        return self.cache[key]

    def local(self,stage,stripe,tile):
        metrics=self.get(stage,stripe,tile);k,j=tile
        return Node(tuple((i,metrics[CONTEXTS.index(c)])for i,(shape,c)in enumerate(self.envs)
                          if j<=shape[0] and k<=shape[1]),(tile,))


@dataclass(frozen=True)
class Node:
    outcomes:tuple  # (environment index, correlated (P,E,T))
    tiles:tuple


def covers(a,b):
    outcomes=dict(a.outcomes)
    return all(i in outcomes and weak(outcomes[i],v)for i,v in b.outcomes)


def conditional_frontier(nodes):
    result=[]
    for node in nodes:
        if any(covers(old,node)for old in result):continue
        result=[old for old in result if not covers(node,old)]
        result.append(node)
    return result


def compile_search(factors,mode):
    if mode not in ('cached_flat','grounded','conditional'):raise ValueError(mode)
    envs=factors.envs;roots={i:[]for i in range(len(envs))}
    stats=dict(partial_objects=0,environment_combines=0,root_objects=0,root_environment_rows=0,
               peak_frontier_objects=0,retained_outcome_rows=0,separator_trace=[])
    if mode=='grounded':
        for env,(shape,context)in enumerate(envs):
            ci=CONTEXTS.index(context)
            for stripe in factors.stripes:
                partial=[((0,0,Fraction(0)),())]
                for stage in range(3):
                    local=numeric_frontier((factors.get(stage,stripe,t)[ci],(t,))for t in factors.options(stage,stripe,shape))
                    candidates=[(add(a,b),ta+tb)for (a,ta),(b,tb)in product(partial,local)]
                    stats['partial_objects']+=len(candidates);stats['environment_combines']+=len(candidates)
                    if stage==2:stats['root_objects']+=len(candidates);stats['root_environment_rows']+=len(candidates)
                    partial=numeric_frontier(candidates)
                    stats['peak_frontier_objects']=max(stats['peak_frontier_objects'],len(partial))
                    stats['separator_trace'].append(dict(env=env,stripe=stripe,stage=stage,kept=len(partial)))
                roots[env].extend((v,Plan(stripe,tiles))for v,tiles in partial)
    else:
        for stripe in factors.stripes:
            partial=[Node(tuple((i,(0,0,Fraction(0)))for i in range(len(envs))),())]
            for stage in range(3):
                local=[factors.local(stage,stripe,t)for t in factors.options(stage,stripe)]
                if mode=='conditional':local=conditional_frontier(local)
                candidates=[]
                for a,b in product(partial,local):
                    right=dict(b.outcomes)
                    outcomes=tuple((i,add(v,right[i]))for i,v in a.outcomes if i in right)
                    if not outcomes:continue
                    stats['environment_combines']+=len(outcomes);stats['partial_objects']+=1
                    if stage==2:stats['root_objects']+=1;stats['root_environment_rows']+=len(outcomes)
                    candidates.append(Node(outcomes,a.tiles+b.tiles))
                partial=conditional_frontier(candidates)if mode=='conditional' else candidates
                stats['peak_frontier_objects']=max(stats['peak_frontier_objects'],len(partial))
                stats['separator_trace'].append(dict(stripe=stripe,stage=stage,kept=len(partial),
                    outcome_rows=sum(len(n.outcomes)for n in partial)))
            for node in partial:
                for env,value in node.outcomes:roots[env].append((value,Plan(stripe,node.tiles)))
    stats['retained_outcome_rows']=sum(len(v)for v in roots.values())
    result={i:numeric_frontier(rows)for i,rows in roots.items()}
    stats['factor_pairs']=factors.evaluations;stats['context_factor_evaluations']=2*factors.evaluations
    return result,stats


def queries(result,factors,capacities=(128*1024,132*1024)):
    # Every baseline receives exactly this precompiled result/query interface.
    answer={}
    for cap in capacities:
        for shape in factors.shapes:
            entries=[(v,(shape,c,p))for i,(s,c)in enumerate(factors.envs)if s==shape
                     for v,p in result[i]if v[0]<=cap]
            answer[(shape,cap)]=numeric_frontier(entries)
    return answer
