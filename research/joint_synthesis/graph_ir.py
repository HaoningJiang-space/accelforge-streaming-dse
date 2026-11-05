"""Closed 2mm computation graph and immutable normalized model parameters."""
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


@dataclass(frozen=True)
class CostModel:
    mac_energy: int=1
    sram_byte_energy: int=1
    dram_byte_energy: int=8
    burst_setup_cycles: int=1

    def __post_init__(self):
        if any(type(v) is not int or v<0 for v in self.__dict__.values()):
            raise ValueError('nonnegative integer model coefficients required')
