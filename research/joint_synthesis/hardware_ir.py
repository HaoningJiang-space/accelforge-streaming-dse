"""Immutable global hardware/budget data, shared with the independent Oracle."""
from dataclasses import dataclass


@dataclass(frozen=True)
class GridAxis:
    minimum: int
    maximum: int
    step: int=1

    def __post_init__(self):
        if any(type(v) is not int or v<1 for v in (self.minimum,self.maximum,self.step)) or self.minimum>self.maximum:
            raise ValueError('positive integer nonempty hardware axis required')


@dataclass(frozen=True,order=True)
class Hardware:
    px: int
    py: int
    sram_bytes: int
    bandwidth: int

    def __post_init__(self):
        if any(type(v) is not int or v<1 for v in self.__dict__.values()):
            raise ValueError('positive integer global hardware coordinates required')


@dataclass(frozen=True)
class HardwareEnvelope:
    px: GridAxis
    py: GridAxis
    sram_bytes: GridAxis
    bandwidth: GridAxis

    def __post_init__(self):
        if any(type(v) is not GridAxis for v in self.__dict__.values()):
            raise ValueError('four integer hardware axes required')


@dataclass(frozen=True)
class NormalizedPrices:
    pe: int=4
    sram_byte: int=1
    bandwidth: int=3

    def __post_init__(self):
        if any(type(v) is not int or v<1 for v in self.__dict__.values()):
            raise ValueError('strictly positive integer normalized prices required')
