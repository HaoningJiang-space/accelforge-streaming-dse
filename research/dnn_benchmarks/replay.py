"""Resource-witness replay with the extracted pointwise operator semantics.

Synthetic deterministic inputs exercise execution, not pretrained accuracy.
The untiled reference uses a separate topological traversal. Unit tests also
compare a linear+bias graph with native PyTorch on the same input values.
"""
from collections import Counter
import math

from research.index_coupling.simulate_nest import (Specification,Machine,
    parse_witness,events,require,input_value)


def evaluate(kind,values,meta):
    if kind=='product':return math.prod(values)
    if kind=='add':return sum(values)
    if kind=='relu':return max(values[0],0.)
    if kind=='gelu':
        x=values[0]
        if meta.get('approximate')=='tanh':
            return .5*x*(1+math.tanh(math.sqrt(2/math.pi)*(x+.044715*x**3)))
        return .5*x*(1+math.erf(x/math.sqrt(2)))
    if kind=='batchnorm_eval':
        x,mean,var,weight,bias=values
        return (x-mean)/math.sqrt(var+meta['eps'])*weight+bias
    raise ValueError(kind)


class DNNMachine(Machine):
    def __init__(self,spec,semantics):
        super().__init__(spec,False)
        self.semantics=semantics

    def step(self,op,iteration):
        require(iteration in self.expected[op] and iteration not in self.seen[op],'invalid arithmetic iteration')
        accesses=self.spec.accesses(op,iteration)
        values=[]
        for cell in accesses[:-1]:
            values.append(self.load(cell));self.future_reads[cell]-=1
        meta=self.semantics[op]
        term=evaluate(meta['kind'],values,meta)
        out=accesses[-1]
        self.values[out]=self.load(out,accumulator=True)+term
        self.done[out]+=1;self.dirty.add(out);self.seen[op].add(iteration);self.steps+=1

    def finish(self):
        require(not self.buffer and not self.values,'leaked reservation')
        require(all(self.seen[o]==self.expected[o] for o in self.spec.ops),'missing iterations')
        require(self.done==self.required,'unfinished reductions')
        require(all(n==0 for n in self.future_reads.values()),'missing input accesses')
        ref={c:input_value(c) for c in self.spec.cells(self.spec.inputs,self.spec.bounds)}
        for op in self.spec.ops:
            meta=self.semantics[op]
            for iteration in self.spec.iterations(op,self.spec.bounds):
                accesses=self.spec.accesses(op,iteration)
                term=evaluate(meta['kind'],[ref[c] for c in accesses[:-1]],meta)
                out=accesses[-1];ref[out]=ref.get(out,0)+term
        outputs=self.spec.cells(self.spec.outputs,self.spec.bounds)
        require(all(c in self.dram and math.isclose(self.dram[c][0],ref[c],rel_tol=1e-9,abs_tol=1e-9) for c in outputs),'incorrect outputs')
        return dict(valid=True,peak=self.peak,traffic=sum(self.reads.values())+sum(self.writes.values()),
            reads=dict(self.reads),writes=dict(self.writes),partial_reads=dict(self.partial_reads),
            partial_writes=dict(self.partial_writes),steps=self.steps,outputs_checked=len(outputs),
            peak_by_tensor=dict(Counter(t for t,_ in self.peak_cells)))


def replay(graph,semantics,witness,scalar_leaf):
    spec=Specification(graph);root=parse_witness(spec,witness,scalar_leaf)
    machine=DNNMachine(spec,semantics)
    for kind,payload in events(spec,root):
        if kind=='step':machine.step(*payload)
        elif kind=='allocate':machine.allocate(payload)
        elif kind=='release':machine.release(payload)
        else:raise ValueError(kind)
    return machine.finish()
