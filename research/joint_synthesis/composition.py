"""Executable materialized-cut conversion and resource-composition law."""
from dataclasses import dataclass
from .physical_plan import CompletePlan
from .resource_demand import Demand, bursts


@dataclass(frozen=True)
class ConversionDemand:
    peak: int
    energy: int
    cycles: int
    traffic: int


def enforcer_choices(source,target):
    if source.tensor!=target.tensor:
        raise ValueError('conversion cannot change logical values/version/shape/width')
    if source.location==target.location=='sram' and source.layout!=target.layout:
        return 'direct','spill_reload'
    return ('direct',)


def conversion(source,target,model,enforcer='direct'):
    if enforcer not in enforcer_choices(source,target):
        raise ValueError('enforcer is not supported for these physical interfaces')
    size=source.tensor.nbytes
    if enforcer=='spill_reload':
        # Full row-major DRAM staging; release the old SRAM owner before
        # allocating the target. Both transfers have one contiguous DRAM run.
        return ConversionDemand(size,2*size*(model.sram_byte_energy+model.dram_byte_energy),
                                2*model.burst_setup_cycles,2*size)
    if source==target:
        return ConversionDemand(source.live_bytes,0,0,0)
    src_dram=source.location=='dram';dst_dram=target.location=='dram'
    traffic=size*(src_dram+dst_dram)
    sram_bytes=2*size if src_dram==dst_dram else size
    shape=source.tensor
    nbursts=(bursts(shape.rows,shape.cols,shape.rows,shape.cols,source.layout) if src_dram else 0)
    nbursts+=bursts(shape.rows,shape.cols,shape.rows,shape.cols,target.layout) if dst_dram else 0
    peak=2*size if not src_dram and not dst_dram else size
    return ConversionDemand(peak,sram_bytes*model.sram_byte_energy+traffic*model.dram_byte_energy,
                            nbursts*model.burst_setup_cycles,traffic)


def compose(left,right,model,enforcer='direct'):
    plan=CompletePlan(left.plan,right.plan,enforcer)
    bridge=conversion(left.plan.delivered,right.plan.required,model,enforcer)
    if ((left.plan.required.location,left.plan.required.layout)!=('dram','row')
            or (right.plan.delivered.location,right.plan.delivered.layout)!=('dram','row')):
        raise ValueError('composition gate requires row-major external DRAM input and final output')
    return Demand(max(left.pe_x,right.pe_x),max(left.pe_y,right.pe_y),
        max(left.workspace,bridge.peak,right.plan.required.live_bytes+right.workspace),
        left.energy+bridge.energy+right.energy,left.cycles+bridge.cycles+right.cycles,
        left.traffic+bridge.traffic+right.traffic,plan)
