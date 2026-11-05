"""Closed-form rules, separate from the scalar allocation/access Oracle."""
from dataclasses import dataclass
from fractions import Fraction
from .graph_ir import CompletePlan


def bursts(rows,cols,height,width,layout):
    """Contiguous DRAM runs for row-ordered logical rectangle transfers."""
    if layout=='row':
        return 1 if width==cols else height
    return 1 if rows==1 or width==1 else height*width


@dataclass(frozen=True)
class KernelDemand:
    plan: object
    pe_x: int
    pe_y: int
    workspace: int  # excludes borrowed input, includes owned output
    energy: int
    cycles: int
    traffic: int
    macs: int
    sram_bytes: int
    dram_bursts: int

    @property
    def vector(self):
        return self.pe_x,self.pe_y,self.workspace,self.energy,self.cycles,self.traffic


@dataclass(frozen=True)
class ConversionDemand:
    peak: int
    energy: int
    cycles: int
    traffic: int


@dataclass(frozen=True)
class Demand:
    pe_x: int
    pe_y: int
    peak: int
    energy: int
    cycles: int
    traffic: int
    plan: CompletePlan

    @property
    def vector(self):
        return self.pe_x,self.pe_y,self.peak,self.energy,self.cycles,self.traffic

    def latency(self,bandwidth):
        if bandwidth<=0:
            raise ValueError('positive bandwidth required')
        return self.cycles+Fraction(self.traffic,bandwidth)


def summarize(plan,model):
    op,s=plan.op,plan.schedule
    r,k,c=op.left.rows,op.left.cols,op.output.cols
    ni,nj,nk=r//s.ti,c//s.tj,k//s.tk
    a_loads=ni*nk if s.order=='ikj' else ni*nj*nk
    b_loads=nj*nk if s.order=='jki' else ni*nj*nk
    a_dram=plan.required.location=='dram'
    out_dram=plan.delivered.location=='dram'
    w=op.left.word_bytes
    reads=(a_loads*s.ti*s.tk if a_dram else 0)+b_loads*s.tk*s.tj
    writes=r*c if out_dram else 0
    traffic=(reads+writes)*w
    nb=(a_loads*bursts(r,k,s.ti,s.tk,plan.required.layout) if a_dram else 0)
    nb+=b_loads*bursts(k,c,s.tk,s.tj,'row')
    nb+=ni*nj*bursts(r,c,s.ti,s.tj,plan.delivered.layout) if out_dram else 0
    accumulator={'ijk':s.ti*s.tj,'ikj':s.ti*c,'jki':r*s.tj}[s.order] if out_dram else 0
    workspace=(accumulator+(s.ti*s.tk if a_dram else 0)+s.tk*s.tj)*w+plan.delivered.live_bytes
    macs=r*k*c
    sram_bytes=4*macs*w+r*c*w+traffic
    energy=macs*model.mac_energy+sram_bytes*model.sram_byte_energy+traffic*model.dram_byte_energy
    cycles=(r//s.ti)*(c//s.tj)*k+nb*model.burst_setup_cycles
    return KernelDemand(plan,s.ti,s.tj,workspace,energy,cycles,traffic,macs,sram_bytes,nb)


def conversion(source,target,model):
    if source.tensor!=target.tensor:
        raise ValueError('conversion cannot change logical values/version/shape/width')
    size=source.tensor.nbytes
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


def compose(left,right,model):
    plan=CompletePlan(left.plan,right.plan)
    bridge=conversion(left.plan.delivered,right.plan.required,model)
    if ((left.plan.required.location,left.plan.required.layout)!=('dram','row')
            or (right.plan.delivered.location,right.plan.delivered.layout)!=('dram','row')):
        raise ValueError('composition gate requires row-major external DRAM input and final output')
    return Demand(max(left.pe_x,right.pe_x),max(left.pe_y,right.pe_y),
        max(left.workspace,bridge.peak,right.plan.required.live_bytes+right.workspace),
        left.energy+bridge.energy+right.energy,left.cycles+bridge.cycles+right.cycles,
        left.traffic+bridge.traffic+right.traffic,plan)
