"""Operator graphs: einsums over named rank variables, and the graphs studied here.

A graph is an ordered list of einsums. Each einsum maps tensor names to the rank
variables they index; the output tensor is listed last. A tensor's dimensions
are named by the ranks they index, so a slice size depends only on which ranks
are sliced.
"""
from math import prod


class Graph:
    def __init__(self, sizes, ops):
        # ops: list of (name, {tensor: (rank variables, ...)}); output listed last.
        self.sizes = sizes
        self.ops = tuple(name for name, _ in ops)
        self.access = {name: acc for name, acc in ops}

    def tensors(self, ops):
        return {t for op in ops for t in self.access[op]}

    def dims(self, tensor):
        for op in self.ops:
            if tensor in self.access[op]:
                return self.access[op][tensor]
        raise KeyError(tensor)

    def size(self, tensor, sliced):
        # Each projection is a list of distinct rank variables; sizes come from them.
        return prod(self.sizes[v] for v in self.dims(tensor) if v not in sliced)

    def rank_vars(self, ops):
        return {v for op in ops for dims in self.access[op].values() for v in dims}

    def output(self, op):
        return list(self.access[op])[-1]

    def produced(self):
        return {self.output(op) for op in self.ops}

    def consumed(self):
        return {t for op in self.ops for t in list(self.access[op])[:-1]}

    def consumers(self, tensor):
        return [op for op in self.ops if tensor in self.access[op] and self.output(op) != tensor]


def coupling(ni, nj, nk, nl, cross):
    # X = AB feeds U = XC and V, which contracts K (same) or I (cross).
    ev = {'D': ('L', 'I'), 'X': ('I', 'K'), 'V': ('L', 'K')} if cross else \
         {'X': ('I', 'K'), 'D': ('K', 'L'), 'V': ('I', 'L')}
    return Graph(dict(I=ni, J=nj, K=nk, L=nl), [
        ('EX', {'A': ('I', 'J'), 'B': ('J', 'K'), 'X': ('I', 'K')}),
        ('EU', {'X': ('I', 'K'), 'C': ('K', 'L'), 'U': ('I', 'L')}),
        ('EV', ev),
    ])


def fork(ni, nj, nk, nl, roles):
    # X = AB feeds one consumer per character of roles: 'k' contracts K
    # (U_c = X C_c, U_c is I x L), 'i' contracts I (V_c = D_c X, V_c is L x K).
    ops = [('EX', {'A': ('I', 'J'), 'B': ('J', 'K'), 'X': ('I', 'K')})]
    for c, role in enumerate(roles):
        ops.append((f'E{c}', {'X': ('I', 'K'), f'C{c}': ('K', 'L'), f'U{c}': ('I', 'L')} if role == 'k' else
                    {f'D{c}': ('L', 'I'), 'X': ('I', 'K'), f'V{c}': ('L', 'K')}))
    return Graph(dict(I=ni, J=nj, K=nk, L=nl), ops)


def ffn(m, d, f):
    # Copy einsums are modeled as aliases sharing one reservation with their source
    # (AccelForge deduplicates same-memory aliases); their position in the einsum
    # order is ignored, which can underestimate lifetimes (see REVIEW_NOTES.md). X, W1, W2
    # and dY are inputs read once, kept whole by the cross-group rule when needed.
    ops = [
        ('EH', {'X': ('M', 'D'), 'W1': ('D', 'F'), 'H': ('M', 'F')}),
        ('EZ', {'H': ('M', 'F'), 'Z': ('M', 'F')}),
        ('EY', {'Z': ('M', 'F'), 'W2': ('F', 'E'), 'Y': ('M', 'E')}),
        ('EdW2', {'Z': ('M', 'F'), 'dY': ('M', 'E'), 'dW2': ('F', 'E')}),
        ('EdZ', {'dY': ('M', 'E'), 'W2': ('F', 'E'), 'dZ': ('M', 'F')}),
        ('EdH', {'dZ': ('M', 'F'), 'H': ('M', 'F'), 'dH': ('M', 'F')}),
        ('EdW1', {'X': ('M', 'D'), 'dH': ('M', 'F'), 'dW1': ('D', 'F')}),
        ('EdX', {'dH': ('M', 'F'), 'W1': ('D', 'F'), 'dX': ('M', 'D')}),
    ]
    return Graph(dict(M=m, D=d, F=f, E=d), ops)


def attention(m, p, e, f):
    # One head of attention core: S = Q K^T, P = softmax(S), O = P V. Softmax is
    # modeled elementwise (online softmax makes streaming over keys legal).
    return Graph(dict(M=m, P=p, E=e, F=f), [
        ('ES', {'Q': ('M', 'E'), 'K': ('P', 'E'), 'S': ('M', 'P')}),
        ('ESoft', {'S': ('M', 'P'), 'A': ('M', 'P')}),
        ('EO', {'A': ('M', 'P'), 'V': ('P', 'F'), 'O': ('M', 'F')}),
    ])


def residual(ni, nk, nl, depth=8, reads_x=False):
    """X = copy(R); H; Z = H_last + X (depth + 2 operators).

    H starts with two contractions I,K -> I,L -> I,K, then elementwise
    operations. In the control H reads an independent D with X's shape;
    in the residual case its first operation reads X. Addition has the same
    access/traffic semantics as an elementwise product in the curve grammar.
    """
    if min(ni, nk, nl) < 1 or depth < 2:
        raise ValueError('positive dimensions and depth >= 2 required')
    source = 'X' if reads_x else 'D'
    ops = [
        ('EX', {'R': ('I', 'K'), 'X': ('I', 'K')}),
        ('EH0', {source: ('I', 'K'), 'W0': ('K', 'L'), 'H0': ('I', 'L')}),
        ('EH1', {'H0': ('I', 'L'), 'W1': ('L', 'K'), 'H1': ('I', 'K')}),
    ]
    for j in range(2, depth):
        ops.append((f'EH{j}', {f'H{j-1}': ('I', 'K'), f'W{j}': ('I', 'K'),
                                f'H{j}': ('I', 'K')}))
    ops.append(('EAdd', {f'H{depth-1}': ('I', 'K'), 'X': ('I', 'K'), 'Z': ('I', 'K')}))
    return Graph(dict(I=ni, K=nk, L=nl), ops)
