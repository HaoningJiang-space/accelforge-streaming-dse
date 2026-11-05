"""Physical interfaces, execution choices and reconstructable source plans."""
from dataclasses import dataclass
from .graph_ir import Tensor, MatMul


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
class CompletePlan:
    producer: KernelPlan
    consumer: KernelPlan
    enforcer: str='direct'

    def __post_init__(self):
        if self.producer.op.output!=self.consumer.op.left:
            raise ValueError('different logical boundary tensors cannot be converted')
        a,b=self.producer.op,self.consumer.op
        if len({a.left.name,a.right.name,a.output.name,b.right.name,b.output.name})!=5:
            raise ValueError('only the explicit intermediate may be shared across this cut')
        if self.enforcer not in ('direct','spill_reload'):
            raise ValueError('unknown physical enforcer')
        if self.enforcer=='spill_reload' and not (
                self.producer.delivered.location==self.consumer.required.location=='sram'
                and self.producer.delivered.layout!=self.consumer.required.layout):
            raise ValueError('spill/reload is modeled only for distinct SRAM layouts')


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
