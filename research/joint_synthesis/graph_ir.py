"""Closed 2mm computation graph and immutable normalized model parameters."""
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class SignedInteger:
    word_bytes: int=2

    def __post_init__(self):
        if type(self.word_bytes) is not int or self.word_bytes<1:
            raise ValueError('positive integer byte width required')


@dataclass(frozen=True)
class IntegerPrecision:
    """Explicit MAC roles in the current uniform-width, checked grammar.

    Wider accumulators require different storage/action rules and are not
    silently interpreted as uniform-width copies. Overflow never wraps/clips.
    """
    operand_dtype: SignedInteger=SignedInteger()
    accumulator_dtype: SignedInteger=SignedInteger()
    output_dtype: SignedInteger=SignedInteger()
    overflow: str='reject'

    def __post_init__(self):
        roles=(self.operand_dtype,self.accumulator_dtype,self.output_dtype)
        if any(not isinstance(t,SignedInteger) for t in roles):
            raise ValueError('signed integer dtypes required for all MAC roles')
        if len(set(roles))!=1 or self.overflow!='reject':
            raise ValueError('only uniform-width MACs with checked overflow are modeled')


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

    @property
    def dtype(self):
        return SignedInteger(self.word_bytes)


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

    @property
    def precision(self):
        return IntegerPrecision(self.left.dtype,self.output.dtype,self.output.dtype)


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
