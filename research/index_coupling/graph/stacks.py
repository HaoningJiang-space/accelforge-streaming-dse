"""Ordered stack controls using the existing serial einsum abstractions.

Feature ranks at different layer boundaries are distinct even when their
extents agree. Training executes all forwards, then backwards in reverse layer
order; concatenating complete forward/backward blocks would violate gradients.
Attention uses externally supplied K/V, as in model.attention; these are not
complete Transformer implementations and softmax remains elementwise here.
"""
from .model import Graph


def ffn_stack(layers, m=2, d=2, f=2, training=False):
    if layers < 1 or min(m, d, f) < 1:
        raise ValueError('positive layers and dimensions required')
    sizes = dict(M=m, **{f'D{i}': d for i in range(layers + 1)},
                 **{f'F{i}': f for i in range(layers)})
    ops = []
    for i in range(layers):
        di, fi, do = f'D{i}', f'F{i}', f'D{i+1}'
        ops.extend([
            (f'EH{i}', {f'X{i}': ('M', di), f'W1_{i}': (di, fi), f'H{i}': ('M', fi)}),
            (f'EZ{i}', {f'H{i}': ('M', fi), f'Z{i}': ('M', fi)}),
            (f'EY{i}', {f'Z{i}': ('M', fi), f'W2_{i}': (fi, do), f'X{i+1}': ('M', do)}),
        ])
    if training:
        for i in reversed(range(layers)):
            di, fi, do = f'D{i}', f'F{i}', f'D{i+1}'
            ops.extend([
                (f'EdW2_{i}', {f'Z{i}': ('M', fi), f'G{i+1}': ('M', do), f'dW2_{i}': (fi, do)}),
                (f'EdZ{i}', {f'G{i+1}': ('M', do), f'W2_{i}': (fi, do), f'dZ{i}': ('M', fi)}),
                (f'EdH{i}', {f'dZ{i}': ('M', fi), f'H{i}': ('M', fi), f'dH{i}': ('M', fi)}),
                (f'EdW1_{i}', {f'X{i}': ('M', di), f'dH{i}': ('M', fi), f'dW1_{i}': (di, fi)}),
                (f'EdX{i}', {f'dH{i}': ('M', fi), f'W1_{i}': (di, fi), f'G{i}': ('M', di)}),
            ])
    return Graph(sizes, ops)


def attention_stack(layers, m=2, p=2, d=2):
    if layers < 1 or min(m, p, d) < 1:
        raise ValueError('positive layers and dimensions required')
    sizes = dict(M=m, **{f'D{i}': d for i in range(layers + 1)},
                 **{f'P{i}': p for i in range(layers)})
    ops = []
    for i in range(layers):
        di, pi, do = f'D{i}', f'P{i}', f'D{i+1}'
        ops.extend([
            (f'ES{i}', {f'X{i}': ('M', di), f'K{i}': (pi, di), f'S{i}': ('M', pi)}),
            (f'ESoft{i}', {f'S{i}': ('M', pi), f'A{i}': ('M', pi)}),
            (f'EO{i}', {f'A{i}': ('M', pi), f'V{i}': (pi, do), f'X{i+1}': ('M', do)}),
        ])
    return Graph(sizes, ops)
