"""Closed 2mm graph and explicit physical execution grammar data."""
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Tensor:
    name: str
    rows: int
    cols: int
    word_bytes: int = 2
    version: int = 0

    def __post_init__(self):
        if not self.name or any(type(x) is not int or x < 1 for x in (self.rows,self.cols,self.word_bytes)):
            raise ValueError('named positive integer tensor dimensions/width required')
        if self.version != 0:
            raise ValueError('this grammar has one immutable logical version')

    @property
    def nbytes(self):
        return self.rows*self.cols*self.word_bytes


@dataclass(frozen=True, order=True)
class Property:
    tensor: Tensor
    layout: str
    location: str

    def __post_init__(self):
        if self.layout not in ('row','col') or self.location not in ('sram','dram'):
            raise ValueError('unsupported layout or location')

    @property
    def live_bytes(self):
        return self.tensor.nbytes if self.location=='sram' else 0


@dataclass(frozen=True, order=True)
class MatMul:
    name: str
    left: Tensor
    right: Tensor
    output: Tensor

    def __post_init__(self):
        if len({self.left.name,self.right.name,self.output.name})!=3:
            raise ValueError('implicit tensor aliasing is outside this grammar')
        if (self.left.cols!=self.right.rows or self.output.rows!=self.left.rows
                or self.output.cols!=self.right.cols or len({self.left.word_bytes,self.right.word_bytes,self.output.word_bytes})!=1):
            raise ValueError('incompatible MatMul dimensions or precision')


@dataclass(frozen=True)
class TwoMM:
    m: int=2
    k: int=2
    n: int=2
    p: int=2

    def __post_init__(self):
        if any(type(x) is not int or x<1 for x in (self.m,self.k,self.n,self.p)):
            raise ValueError('positive integer dimensions required')

    @property
    def operators(self):
        a,b,x,w,y=(Tensor('A',self.m,self.k),Tensor('B',self.k,self.n),
                   Tensor('X',self.m,self.n),Tensor('W',self.n,self.p),Tensor('Y',self.m,self.p))
        return MatMul('produce',a,b,x),MatMul('consume',x,w,y)


@dataclass(frozen=True, order=True)
class Schedule:
    ti: int
    tj: int
    tk: int
    order: str

    def __post_init__(self):
        if any(type(x) is not int or x<1 for x in (self.ti,self.tj,self.tk)) or self.order not in ('ijk','ikj','jki'):
            raise ValueError('unsupported schedule')


@dataclass(frozen=True, order=True)
class KernelPlan:
    op: MatMul
    schedule: Schedule
    required: Property
    delivered: Property

    def __post_init__(self):
        if self.required.tensor!=self.op.left or self.delivered.tensor!=self.op.output:
            raise ValueError('property names/version/shape must match the operator')
        s=self.schedule
        if self.op.left.rows%s.ti or self.op.output.cols%s.tj or self.op.left.cols%s.tk:
            raise ValueError('this grammar supports divisor tiles only')


@dataclass(frozen=True)
class CostModel:
    mac_energy: int=1
    sram_byte_energy: int=1
    dram_byte_energy: int=8
    burst_setup_cycles: int=1

    def __post_init__(self):
        if any(type(v) is not int or v<0 for v in self.__dict__.values()):
            raise ValueError('nonnegative integer model coefficients required')


@dataclass(frozen=True)
class CompletePlan:
    producer: KernelPlan
    consumer: KernelPlan

    def __post_init__(self):
        if self.producer.op.output!=self.consumer.op.left:
            raise ValueError('different logical boundary tensors cannot be converted')
        a,b=self.producer.op,self.consumer.op
        if len({a.left.name,a.right.name,a.output.name,b.right.name,b.output.name})!=5:
            raise ValueError('only the explicit intermediate may be shared across this cut')


def restore_plan(payload):
    """Restore an execution witness; unknown fields are rejected, not discarded."""
    def prop(data):
        values=dict(data);values['tensor']=Tensor(**values['tensor'])
        return Property(**values)
    def kernel(data):
        values=dict(data);op=dict(values['op'])
        for name in ('left','right','output'):op[name]=Tensor(**op[name])
        values['op']=MatMul(**op)
        values['schedule']=Schedule(**values['schedule'])
        for name in ('required','delivered'):values[name]=prop(values[name])
        return KernelPlan(**values)
    values=dict(payload)
    for name in ('producer','consumer'):values[name]=kernel(values[name])
    return CompletePlan(**values)
