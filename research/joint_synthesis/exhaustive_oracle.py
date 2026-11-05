"""Independent scalar copy/MAC interpreter; no summary or DP imports.

The Oracle owns allocations and physical addresses. Closed-form demand rules
are not used to compute its peak, action counts, numeric output or service time.
"""
from dataclasses import dataclass
from itertools import product
from .graph_ir import IntegerPrecision, SignedInteger
from .physical_plan import Property, Schedule, KernelPlan, CompletePlan


@dataclass
class Copy:
    rows: int
    cols: int
    location: str
    layout: str
    data: list


@dataclass(frozen=True)
class View:
    owner: int
    row: int
    col: int
    rows: int
    cols: int


def matrix(rows,cols,seed):
    return [[(i*5+j*3+i*j+seed)%7-3 for j in range(cols)] for i in range(rows)]


def multiply(a,b):
    return [[sum(a[i][k]*b[k][j]for k in range(len(b))) for j in range(len(b[0]))]
            for i in range(len(a))]


class Runtime:
    def __init__(self,model,word_bytes=2,precision=None):
        dtype=SignedInteger(word_bytes)
        if precision is None:precision=IntegerPrecision(dtype,dtype,dtype)
        if not isinstance(precision,IntegerPrecision) or precision.operand_dtype!=dtype:
            raise ValueError('runtime copy width must match the explicit MAC precision')
        self.precision=precision
        self.model,self.word=model,word_bytes
        self.copies={};self.serial=0
        self.current=self.peak=self.macs=self.sram_bytes=self.dram_bytes=self.bursts=self.cycles=0
        self.pe_x=self.pe_y=1

    def alloc(self,rows,cols,location,layout='row',data=None):
        # Validate before assigning an ID or changing occupancy. Host-side
        # initialization is not an executed memory action, but is still typed.
        if any(type(n) is not int or n<1 for n in (rows,cols)):
            raise ValueError('allocation dimensions must be positive integers')
        if location not in ('sram','dram') or layout not in ('row','col'):
            raise ValueError('unsupported allocation location or layout')
        if data is not None:
            if (not isinstance(data,(list,tuple)) or len(data)!=rows or
                    any(not isinstance(row,(list,tuple)) or len(row)!=cols for row in data)):
                raise ValueError('initial data must have the exact allocation shape')
            for row in data:
                for value in row:self.check_value(value)
        physical=[None]*(rows*cols)
        if data is not None:
            for i,j in product(range(rows),range(cols)):
                physical[i*cols+j if layout=='row' else j*rows+i]=data[i][j]
        ident=self.serial;self.serial+=1
        self.copies[ident]=Copy(rows,cols,location,layout,physical)
        if location=='sram':
            self.current+=rows*cols*self.word;self.peak=max(self.peak,self.current)
        return ident

    def check_value(self,value):
        if type(value) is not int or not -(1<<(8*self.word-1))<=value<(1<<(8*self.word-1)):
            raise AssertionError('integer value outside declared precision')

    def copy_for(self,ident):
        if type(ident) is not int or ident not in self.copies:
            raise AssertionError('unknown or released physical copy')
        return self.copies[ident]

    def free(self,ident):
        self.copy_for(ident)
        c=self.copies.pop(ident)
        if c.location=='sram':
            self.current-=c.rows*c.cols*self.word
        if self.current<0:
            raise AssertionError('negative occupancy')

    def full(self,ident):
        c=self.copy_for(ident)
        return View(ident,0,0,c.rows,c.cols)

    def validate_view(self,v):
        if not isinstance(v,View):raise AssertionError('a bounded View is required')
        c=self.copy_for(v.owner)
        if (any(type(n) is not int for n in (v.row,v.col,v.rows,v.cols)) or
                v.row<0 or v.col<0 or v.rows<1 or v.cols<1 or
                v.row+v.rows>c.rows or v.col+v.cols>c.cols):
            raise AssertionError('invalid view extent')
        return c

    def address(self,v,i,j):
        c=self.validate_view(v)
        if type(i) is not int or type(j) is not int or not 0<=i<v.rows or not 0<=j<v.cols:
            raise AssertionError('access outside view')
        r,s=v.row+i,v.col+j
        return (r*c.cols+s if c.layout=='row' else s*c.rows+r)*self.word

    def read(self,v,i,j):
        address=self.address(v,i,j)
        c=self.copies[v.owner]
        value=c.data[address//self.word]
        if value is None:raise AssertionError('read before production')
        if c.location=='sram':self.sram_bytes+=self.word
        else:self.dram_bytes+=self.word
        return value

    def write(self,v,i,j,value):
        address=self.address(v,i,j)
        self.check_value(value)
        c=self.copies[v.owner]
        if c.location=='sram':self.sram_bytes+=self.word
        else:self.dram_bytes+=self.word
        c.data[address//self.word]=value

    def logical(self,ident):
        """Unpack for external validation; this is not an executed memory action."""
        c=self.copy_for(ident);v=self.full(ident)
        return [[c.data[self.address(v,i,j)//self.word]for j in range(c.cols)]for i in range(c.rows)]

    def fill(self,v):
        self.validate_view(v)
        for i,j in product(range(v.rows),range(v.cols)):
            self.write(v,i,j,0)

    def transfer(self,source,target):
        self.validate_view(source);self.validate_view(target)
        if source.owner==target.owner:
            raise ValueError('in-place conversion is outside the copy grammar')
        if (source.rows,source.cols)!=(target.rows,target.cols):
            raise AssertionError('copy changes logical shape')
        previous={source.owner:None,target.owner:None}
        for i,j in product(range(source.rows),range(source.cols)):
            for v in (source,target):
                if self.copies[v.owner].location=='dram':
                    address=self.address(v,i,j)
                    if previous[v.owner] is None or address!=previous[v.owner]+self.word:
                        self.bursts+=1
                    previous[v.owner]=address
            self.write(target,i,j,self.read(source,i,j))

    def compute(self,a,b,c,u,v):
        for view in (a,b,c):self.validate_view(view)
        if any(type(n) is not int or n<1 for n in (u,v)):
            raise ValueError('positive integer spatial extents required')
        if (a.rows,b.cols,a.cols)!=(c.rows,c.cols,b.rows):
            raise AssertionError('incompatible MAC views')
        if any(self.copies[x.owner].location!='sram'for x in (a,b,c)):
            raise AssertionError('MAC operands must be SRAM copies/views')
        if c.owner in (a.owner,b.owner):
            raise ValueError('MAC input/output aliasing is outside the grammar')
        self.pe_x=max(self.pe_x,u);self.pe_y=max(self.pe_y,v)
        # Count actual spatial waves; no analytical kernel cycle formula.
        for base_i,base_j in product(range(0,c.rows,u),range(0,c.cols,v)):
            for k in range(a.cols):
                self.cycles+=1
                for i,j in product(range(base_i,min(base_i+u,c.rows)),range(base_j,min(base_j+v,c.cols))):
                    value=self.read(c,i,j)+self.read(a,i,k)*self.read(b,k,j)
                    self.write(c,i,j,value);self.macs+=1

    @property
    def vector(self):
        e=self.macs*self.model.mac_energy+self.sram_bytes*self.model.sram_byte_energy+self.dram_bytes*self.model.dram_byte_energy
        c=self.cycles+self.bursts*self.model.burst_setup_cycles
        return self.pe_x,self.pe_y,self.peak,e,c,self.dram_bytes


def kernel(runtime,plan,a,b):
    """Execute one schedule using owned copies and bounded subviews."""
    r,k,c=plan.op.left.rows,plan.op.left.cols,plan.op.output.cols
    s=plan.schedule;i_values=range(0,r,s.ti);j_values=range(0,c,s.tj);k_values=range(0,k,s.tk)
    output=runtime.alloc(r,c,plan.delivered.location,plan.delivered.layout)
    if plan.delivered.location=='sram':runtime.fill(runtime.full(output))

    def get_a(i,kk):
        source=View(a,i,kk,s.ti,s.tk)
        if runtime.copies[a].location=='sram':return source,None
        ident=runtime.alloc(s.ti,s.tk,'sram')
        runtime.transfer(source,runtime.full(ident))
        return runtime.full(ident),ident

    def get_b(kk,j):
        ident=runtime.alloc(s.tk,s.tj,'sram')
        runtime.transfer(View(b,kk,j,s.tk,s.tj),runtime.full(ident))
        return runtime.full(ident),ident

    def accumulator(rows,cols):
        if plan.delivered.location=='sram':return None
        ident=runtime.alloc(rows,cols,'sram');runtime.fill(runtime.full(ident))
        return ident

    def cv(ident,i,j,base_i,base_j):
        return View(output,i,j,s.ti,s.tj) if ident is None else View(ident,i-base_i,j-base_j,s.ti,s.tj)

    def store(ident,i,j,base_i,base_j):
        if ident is not None:
            runtime.transfer(cv(ident,i,j,base_i,base_j),View(output,i,j,s.ti,s.tj))

    if s.order=='ijk':
        for i,j in product(i_values,j_values):
            acc=accumulator(s.ti,s.tj)
            for kk in k_values:
                av,ai=get_a(i,kk);bv,bi=get_b(kk,j)
                runtime.compute(av,bv,cv(acc,i,j,i,j),s.ti,s.tj)
                if ai is not None:runtime.free(ai)
                runtime.free(bi)
            store(acc,i,j,i,j)
            if acc is not None:runtime.free(acc)
    elif s.order=='ikj':
        for i in i_values:
            acc=accumulator(s.ti,c)
            for kk in k_values:
                av,ai=get_a(i,kk)
                for j in j_values:
                    bv,bi=get_b(kk,j)
                    runtime.compute(av,bv,cv(acc,i,j,i,0),s.ti,s.tj);runtime.free(bi)
                if ai is not None:runtime.free(ai)
            for j in j_values:store(acc,i,j,i,0)
            if acc is not None:runtime.free(acc)
    elif s.order=='jki':
        for j in j_values:
            acc=accumulator(r,s.tj)
            for kk in k_values:
                bv,bi=get_b(kk,j)
                for i in i_values:
                    av,ai=get_a(i,kk)
                    runtime.compute(av,bv,cv(acc,i,j,0,j),s.ti,s.tj)
                    if ai is not None:runtime.free(ai)
                runtime.free(bi)
            for i in i_values:store(acc,i,j,0,j)
            if acc is not None:runtime.free(acc)
    else:raise ValueError('unknown execution order')
    return output


def convert(runtime,ident,source,target,enforcer='direct'):
    if source.tensor!=target.tensor:raise ValueError('not the same logical data')
    copy=runtime.copy_for(ident);shape=source.tensor
    if ((copy.rows,copy.cols,copy.location,copy.layout,runtime.word)!=
            (shape.rows,shape.cols,source.location,source.layout,shape.word_bytes)):
        raise AssertionError('physical copy does not match declared conversion source')
    if enforcer not in ('direct','spill_reload'):
        raise ValueError('unknown physical enforcer')
    if enforcer=='spill_reload':
        if not (source.location==target.location=='sram' and source.layout!=target.layout):
            raise ValueError('spill/reload requires distinct SRAM layouts')
        # Execute both transfers; do not call production conversion summaries.
        temporary=runtime.alloc(shape.rows,shape.cols,'dram','row')
        runtime.transfer(runtime.full(ident),runtime.full(temporary))
        runtime.free(ident)
        result=runtime.alloc(shape.rows,shape.cols,'sram',target.layout)
        runtime.transfer(runtime.full(temporary),runtime.full(result))
        runtime.free(temporary)
        return result
    if source==target:return ident
    if source.location==target.location=='dram':
        temporary=runtime.alloc(shape.rows,shape.cols,'sram')
        runtime.transfer(runtime.full(ident),runtime.full(temporary))
        result=runtime.alloc(shape.rows,shape.cols,'dram',target.layout)
        runtime.transfer(runtime.full(temporary),runtime.full(result))
        runtime.free(temporary)
    else:
        result=runtime.alloc(shape.rows,shape.cols,target.location,target.layout)
        runtime.transfer(runtime.full(ident),runtime.full(result))
    runtime.free(ident)
    return result


def trace_local(plan,model):
    runtime=Runtime(model,plan.op.left.word_bytes,plan.op.precision)
    a_values=matrix(plan.op.left.rows,plan.op.left.cols,0)
    b_values=matrix(plan.op.right.rows,plan.op.right.cols,1)
    a=runtime.alloc(plan.op.left.rows,plan.op.left.cols,plan.required.location,plan.required.layout,a_values)
    b=runtime.alloc(plan.op.right.rows,plan.op.right.cols,'dram','row',b_values)
    out=kernel(runtime,plan,a,b)
    if runtime.logical(out)!=multiply(a_values,b_values):raise AssertionError('incorrect local matrix result')
    if runtime.current!=plan.required.live_bytes+plan.delivered.live_bytes:raise AssertionError('leaked local scratch copy')
    return runtime


def trace_complete(plan,model,seed=0):
    runtime=Runtime(model,plan.producer.op.left.word_bytes,plan.producer.op.precision)
    a_shape,b_shape=plan.producer.op.left,plan.producer.op.right
    w_shape=plan.consumer.op.right
    av,bv,wv=matrix(a_shape.rows,a_shape.cols,seed),matrix(b_shape.rows,b_shape.cols,seed+1),matrix(w_shape.rows,w_shape.cols,seed+2)
    a=runtime.alloc(a_shape.rows,a_shape.cols,'dram','row',av)
    b=runtime.alloc(b_shape.rows,b_shape.cols,'dram','row',bv)
    w=runtime.alloc(w_shape.rows,w_shape.cols,'dram','row',wv)
    x=kernel(runtime,plan.producer,a,b)
    x=convert(runtime,x,plan.producer.delivered,plan.consumer.required,plan.enforcer)
    y=kernel(runtime,plan.consumer,x,w)
    runtime.free(x)
    if runtime.current:raise AssertionError('leaked complete-plan SRAM copy')
    if runtime.logical(y)!=multiply(multiply(av,bv),wv):raise AssertionError('incorrect 2mm matrix result')
    return runtime


def enumerate_plans(graph):
    """Independent grammar enumeration: scan integers, do not call schedule_rules."""
    a,b=graph.operators
    plans=[]
    for op in (a,b):
        alternatives=[]
        for ti,tj,tk in product(range(1,op.left.rows+1),range(1,op.output.cols+1),range(1,op.left.cols+1)):
            if op.left.rows%ti or op.output.cols%tj or op.left.cols%tk:continue
            for order,layout,location in product(('ijk','ikj','jki'),('row','col'),('sram','dram')):
                boundary=Property(a.output,layout,location)
                required=Property(a.left,'row','dram') if op==a else boundary
                delivered=boundary if op==a else Property(b.output,'row','dram')
                alternatives.append(KernelPlan(op,Schedule(ti,tj,tk,order),required,delivered))
        plans.append(tuple(alternatives))
    return tuple(plans)


def enumerate_complete(first,second):
    """Independent enforcer grammar; never import production choices/rules."""
    for a,b in product(first,second):
        yield CompletePlan(a,b,'direct')
        if (a.delivered.location=='sram' and b.required.location=='sram'
                and a.delivered.layout!=b.required.layout):
            yield CompletePlan(a,b,'spill_reload')


def exhaustive(graph,model,inspect=None):
    first,second=enumerate_plans(graph)
    observations={}
    counts=dict(direct=0,spill_reload=0)
    for plan in enumerate_complete(first,second):
        vector=trace_complete(plan,model).vector
        counts[plan.enforcer]+=1
        if inspect is not None:inspect(plan,vector)
        observations.setdefault(vector,plan)
    return observations,dict(complete_plans_traced=sum(counts.values()),
        kernel_pairs_traced=len(first)*len(second),complete_plans_by_enforcer=counts,
        unique_observed_vectors=len(observations),numeric_results_verified=True,
        allocations_and_accesses_interpreted=True,ffm_search_calls=0)
