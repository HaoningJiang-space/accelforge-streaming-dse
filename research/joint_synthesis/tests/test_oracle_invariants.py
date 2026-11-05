"""Adversarial execution inputs, independent of legal schedule generation."""
from dataclasses import replace

import pytest

from research.joint_synthesis.graph_ir import CostModel, IntegerPrecision, SignedInteger, Tensor, TwoMM
from research.joint_synthesis.physical_plan import Property
from research.joint_synthesis.exhaustive_oracle import Runtime, View, convert, multiply


@pytest.mark.parametrize('layout',['row','col'])
def test_access_is_bounded_by_view_not_just_its_owner(layout):
    r=Runtime(CostModel())
    owner=r.alloc(2,2,'sram',layout,[[1,2],[3,4]])
    view=View(owner,0,0,1,1)
    assert r.read(view,0,0)==1
    before=r.vector
    for i,j in ((0,1),(1,0),(-1,0),(0,-1),(True,0),(0,0.0)):
        with pytest.raises(AssertionError,match='access outside view'):r.read(view,i,j)
        with pytest.raises(AssertionError,match='access outside view'):r.write(view,i,j,9)
    assert r.vector==before
    assert r.logical(owner)==[[1,2],[3,4]]


@pytest.mark.parametrize('extent',[
    (-1,0,1,1),(0,-1,1,1),(0,0,3,1),(0,0,1,3),
    (1,1,2,2),(0,0,0,1),(0,0,1,-1),(False,0,1,1),(0,0,1.0,1),
])
def test_whole_view_must_fit_even_when_accessed_element_would_fit(extent):
    r=Runtime(CostModel());owner=r.alloc(2,2,'dram',data=[[1,2],[3,4]])
    v=View(owner,*extent)
    with pytest.raises(AssertionError,match='invalid view extent'):r.address(v,0,0)
    with pytest.raises(AssertionError,match='invalid view extent'):r.fill(v)


def test_subview_addressing_and_released_copy_identity():
    r=Runtime(CostModel());owner=r.alloc(3,4,'dram','col',[[i*4+j for j in range(4)]for i in range(3)])
    v=View(owner,1,1,2,2)
    assert r.address(v,1,1)==(2*3+2)*2
    assert r.read(v,1,1)==10
    r.free(owner)
    for operation in (lambda:r.address(v,0,0),lambda:r.full(owner),lambda:r.free(owner)):
        with pytest.raises(AssertionError,match='unknown or released'):operation()


@pytest.mark.parametrize('rows,cols,location,layout,data',[
    (0,1,'sram','row',None),(-1,1,'sram','row',None),
    (1,False,'sram','row',None),(1.0,1,'sram','row',None),
    (1,1,'register','row',None),(1,1,'dram','diagonal',None),
    (2,2,'sram','row',[[1,2]]),(1,2,'sram','row',[[1,2,3]]),
    (2,2,'dram','col',[[1,2],[3]]),(1,1,'dram','row',[1]),
    (1,1,'sram','row','1'),
])
def test_invalid_allocation_is_rejected_without_partial_state(rows,cols,location,layout,data):
    r=Runtime(CostModel())
    with pytest.raises(ValueError):r.alloc(rows,cols,location,layout,data)
    assert (r.serial,r.copies,r.current,r.peak)==(0,{},0,0)
    assert r.vector==(1,1,0,0,0,0)


@pytest.mark.parametrize('value',[-32769,32768,1.0,True,None])
def test_initial_values_and_executed_writes_have_same_strict_precision(value):
    r=Runtime(CostModel())
    with pytest.raises(AssertionError,match='declared precision'):
        r.alloc(1,1,'sram',data=[[value]])
    assert r.copies=={} and r.serial==0 and r.current==r.peak==0
    owner=r.alloc(1,1,'sram',data=[[0]])
    before=r.vector
    with pytest.raises(AssertionError,match='declared precision'):r.write(r.full(owner),0,0,value)
    assert r.vector==before and r.logical(owner)==[[0]]


def test_initialization_is_validated_but_is_not_a_memory_action_or_host_alias():
    values=[[-32768,32767]];r=Runtime(CostModel())
    owner=r.alloc(1,2,'sram','col',values)
    values[0][0]=0
    assert r.logical(owner)==[[-32768,32767]]
    assert r.vector==(1,1,4,0,0,0)
    uninitialized=r.alloc(1,1,'dram')
    before=r.vector
    with pytest.raises(AssertionError,match='read before production'):r.read(r.full(uninitialized),0,0)
    assert r.vector==before


def dot_runtime(a,b,word_bytes=2):
    r=Runtime(CostModel(),word_bytes)
    left=r.alloc(1,len(a),'sram',data=[a])
    right=r.alloc(len(b),1,'sram',data=[[x]for x in b])
    out=r.alloc(1,1,'sram',data=[[0]])
    return r,left,right,out


@pytest.mark.parametrize('a,b',[
    ([32767,-32767],[2,2]), # Mathematical result 0, but the first MAC is 65534.
    ([20000,20000,-20000],[1,1,1]), # Only an intermediate sum overflows.
])
def test_each_mac_rejects_overflow_even_if_final_output_would_fit(a,b):
    assert -32768<=multiply([a],[[x]for x in b])[0][0]<=32767
    r,left,right,out=dot_runtime(a,b)
    with pytest.raises(AssertionError,match='declared precision'):
        r.compute(r.full(left),r.full(right),r.full(out),1,1)


@pytest.mark.parametrize('value',[-32768,32767])
def test_signed_limits_are_legal_for_mac_storage_and_output(value):
    r,left,right,out=dot_runtime([value],[1])
    r.compute(r.full(left),r.full(right),r.full(out),1,1)
    assert r.logical(out)==[[value]] and r.macs==1


def test_precision_roles_and_overflow_contract_are_explicit():
    precision=TwoMM().operators[0].precision
    assert precision.operand_dtype==precision.accumulator_dtype==precision.output_dtype==SignedInteger(2)
    assert precision.overflow=='reject'
    with pytest.raises(ValueError,match='uniform-width'):
        replace(precision,accumulator_dtype=SignedInteger(4))
    with pytest.raises(ValueError,match='uniform-width'):replace(precision,overflow='wrap')
    with pytest.raises(ValueError,match='copy width'):Runtime(CostModel(),1,precision)
    with pytest.raises(ValueError):Runtime(CostModel(),True)
    # The declared uniform-width rule also applies to the standalone 8-bit Runtime.
    r,left,right,out=dot_runtime([64],[2],word_bytes=1)
    with pytest.raises(AssertionError,match='declared precision'):
        r.compute(r.full(left),r.full(right),r.full(out),1,1)


def test_invalid_copy_or_mac_views_are_not_silently_empty_operations():
    r,left,right,out=dot_runtime([1],[2])
    bad=View(left,0,0,0,1)
    before=r.vector
    with pytest.raises(AssertionError,match='invalid view extent'):r.transfer(bad,r.full(out))
    with pytest.raises(AssertionError,match='invalid view extent'):
        r.compute(bad,r.full(right),r.full(out),1,1)
    with pytest.raises(ValueError,match='spatial extents'):
        r.compute(r.full(left),r.full(right),r.full(out),0,1)
    assert r.vector==before


@pytest.mark.parametrize('source,target',[
    (Property(Tensor('X',1,1),'row','dram'),Property(Tensor('X',1,1),'row','dram')),
    (Property(Tensor('X',1,1),'col','sram'),Property(Tensor('X',1,1),'col','sram')),
    (Property(Tensor('X',1,2),'row','sram'),Property(Tensor('X',1,2),'row','sram')),
    (Property(Tensor('X',1,1,1),'row','sram'),Property(Tensor('X',1,1,1),'row','sram')),
    (Property(Tensor('X',1,1),'col','sram'),Property(Tensor('X',1,1),'row','dram')),
])
def test_conversion_checks_physical_source_even_for_identity(source,target):
    r=Runtime(CostModel());ident=r.alloc(1,1,'sram','row',[[3]])
    before=r.vector
    with pytest.raises(AssertionError,match='declared conversion source'):
        convert(r,ident,source,target)
    assert r.logical(ident)==[[3]] and r.vector==before and r.serial==1


def test_identity_conversion_requires_live_owner_and_preserves_a_valid_copy():
    r=Runtime(CostModel());ident=r.alloc(1,1,'sram','row',[[3]])
    prop=Property(Tensor('X',1,1),'row','sram');before=r.vector
    assert convert(r,ident,prop,prop)==ident and r.vector==before
    r.free(ident)
    with pytest.raises(AssertionError,match='unknown or released'):convert(r,ident,prop,prop)


@pytest.mark.parametrize('output',['left','right','disjoint_subview'])
def test_mac_rejects_input_output_owner_alias_before_actions(output):
    r=Runtime(CostModel());left=r.alloc(1,2,'sram',data=[[2,0]])
    right=r.alloc(1,1,'sram',data=[[3]])
    a,b=View(left,0,0,1,1),r.full(right)
    c=a if output=='left' else b if output=='right' else View(left,0,1,1,1)
    before=r.vector
    with pytest.raises(ValueError,match='input/output aliasing'):r.compute(a,b,c,1,1)
    assert r.vector==before and r.logical(left)==[[2,0]] and r.logical(right)==[[3]]
