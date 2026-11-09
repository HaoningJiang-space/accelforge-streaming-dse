"""Apply the nest model at real sizes: plateau buffer and resident set.

Plateau = minimum on-chip buffer for zero extra DRAM traffic (every input read
once, every output written once). Real sizes cannot be checked with FFM here;
the model was validated only at small sizes (README).
"""
from research.index_coupling.nest_model import attention, ffn, plateau

BYTES = 2  # bf16


def summary(graph):
    value, nest = plateau(graph, witness=True)
    (_, _, (_, top)), = nest[1] if nest[0] == 'groups' and len(nest[1]) == 1 else [(None, None, (None, nest))]
    if top and top[0] == 'loop':
        return value, f'outer loop {top[1]}, resident {sorted(top[2])}'
    return value, 'multi-phase nest'


def mib(elements):
    return elements * BYTES / 2**20


if __name__ == '__main__':
    print('GPT-3 6.7B FFN training step (D=4096, F=16384), bf16')
    for m in (512, 2048, 8192, 16384, 32768):
        value, how = summary(ffn(m, 4096, 16384))
        print(f'  tokens {m:6}: plateau {mib(value):9.1f} MiB  ({how})')
    print('Attention core, one head (E=F=128), bf16')
    for label, (m, p) in [('prefill 2048', (2048, 2048)), ('prefill 8192', (8192, 8192)),
                          ('decode 1 query, 2048 keys', (1, 2048)), ('decode 1 query, 32768 keys', (1, 32768)),
                          ('decode 64 queries, 32768 keys', (64, 32768))]:
        value, how = summary(attention(m, p, 128, 128))
        print(f'  {label:30s}: plateau {mib(value):9.3f} MiB  ({how})')
