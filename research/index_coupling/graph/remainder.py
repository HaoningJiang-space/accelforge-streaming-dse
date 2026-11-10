"""Exact ordered-remainder reuse: invariant buckets plus verified bijections.

WL refinement is only a rejection/filtering device, never an equality test.
Representatives are invocation-local. A bounded alias LRU avoids retaining a
second unbounded copy of all raw states. Matching-budget exhaustion declines
reuse; it cannot merge non-isomorphic states.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from time import perf_counter


class InfeasibleGroups:
    def __init__(self, graph, names):
        self.graph = graph
        self.bits = {v: 1 << i for i,v in enumerate(names)}
        self.masks = {t: sum(self.bits[v] for v in graph.dims(t)) for t in graph.tensors(graph.ops)}
        self.domains = {o: sum(self.bits[v] for v in graph.rank_vars((o,))) for o in graph.ops}
        self.metadata = lru_cache(maxsize=None)(self._metadata)

    def _metadata(self, ops, active):
        graph = self.graph
        tensors = graph.tensors(ops)
        made = {graph.output(o) for o in ops}
        read = {t for o in ops for t in list(graph.access[o])[:-1]}
        common = active
        for o in ops:
            common &= self.domains[o]
        return (frozenset(t for t in tensors if self.masks[t] & active), common,
                tuple((t,self.masks[t]) for t in sorted(made & read)))

    def empty(self, ops, ext, external):
        active = sum(1 << i for i,e in enumerate(ext) if e > 1)
        nonscalar, admitted, internal = self.metadata(tuple(ops),active)
        if nonscalar <= external:
            return False  # Resident private tensors can change the scalar leaf.
        for t,mask in internal:
            if t not in external:
                admitted &= mask
        return not admitted


@dataclass
class Remainder:
    state: tuple
    ranks: tuple
    tensors: tuple
    rank_labels: tuple
    tensor_labels: tuple
    incidence: tuple
    colors: tuple
    bucket: tuple


class RemainderNames:
    def __init__(self, graph, names, *, alias_limit=4096, match_budget=10000, measure=False):
        self.graph, self.names = graph, tuple(names)
        self.produced, self.consumed = graph.produced(), graph.consumed()
        self.consumers = {t: len(graph.consumers(t)) for t in graph.tensors(graph.ops)}
        self.buckets = defaultdict(list)
        self.match_budget, self.measure = match_budget, measure
        self.counts = Counter()
        self.seconds = 0.
        self.lookup = lru_cache(maxsize=alias_limit)(self._lookup)

    def describe(self, stage, ops, ext, external, owned):
        graph = self.graph
        domains = tuple(graph.rank_vars((o,)) for o in ops)
        ranks = tuple(sorted(set.union(*domains)))
        ri = {v:i for i,v in enumerate(ranks)}
        sizes = dict(zip(self.names,ext))
        tensors = tuple(sorted(graph.tensors(ops)-external))
        rank_labels = tuple(('r',graph.sizes[v],sizes[v],
                             sum(1 << i for i,d in enumerate(domains) if v in d)) for v in ranks)
        tensor_labels = tuple(('t',sum(1 << i for i,o in enumerate(ops) if t in graph.access[o]),
                               next((i for i,o in enumerate(ops) if graph.output(o)==t),-1),
                               t in self.produced,t in self.consumed,self.consumers[t],t in owned,
                               len(graph.dims(t))) for t in tensors)
        incidence = tuple(frozenset(ri[v] for v in graph.dims(t)) for t in tensors)
        initial = rank_labels + tensor_labels
        palette = {x:i for i,x in enumerate(sorted(set(initial)))}
        colors = tuple(palette[x] for x in initial)
        adjacent = [list() for _ in initial]
        nr = len(ranks)
        for j,ds in enumerate(incidence):
            for i in ds:
                adjacent[i].append(nr+j)
                adjacent[nr+j].append(i)
        neighborhood = tuple(sorted(Counter(
            (initial[i],tuple(sorted(initial[j] for j in ns))) for i,ns in enumerate(adjacent)).items()))
        for _ in range(3):
            labels = tuple((colors[i],tuple(sorted(colors[j] for j in ns))) for i,ns in enumerate(adjacent))
            palette = {x:i for i,x in enumerate(sorted(set(labels)))}
            colors = tuple(palette[x] for x in labels)
        # Initial labels are retained: per-graph integer color IDs alone are
        # not comparable across graphs with different initial label alphabets.
        bucket = (stage,len(ops),tuple(sorted(Counter(initial).items())),
                  neighborhood,tuple(sorted(Counter(zip(initial,colors)).items())))
        return Remainder((ops,ext,external,owned),ranks,tensors,rank_labels,tensor_labels,
                         incidence,colors,bucket)

    def exact_map(self, source, target):
        """Representative -> caller mapping, or None; explicitly check incidence."""
        if source.rank_labels == target.rank_labels and source.tensor_labels == target.tensor_labels and source.incidence == target.incidence:
            mapping = dict(enumerate(range(len(source.ranks))))
        else:
            if (Counter(source.rank_labels)!=Counter(target.rank_labels)
                    or Counter(source.tensor_labels)!=Counter(target.tensor_labels)):
                return None
            candidates = {i:tuple(j for j,label in enumerate(target.rank_labels)
                                  if label==source.rank_labels[i] and target.colors[j]==source.colors[i])
                          for i in range(len(source.ranks))}
            order = sorted(candidates,key=lambda i:(len(candidates[i]),-sum(i in ds for ds in source.incidence),i))
            mapping, used = {}, set()
            steps = 0

            def compatible():
                # Compare all tensor labels and their incidences to mapped
                # ranks; also preserve the color multiset of remaining ranks.
                a = Counter((label,tuple(sorted(mapping[i] for i in ds if i in mapping)),
                             tuple(sorted(source.colors[i] for i in ds if i not in mapping)))
                            for label,ds in zip(source.tensor_labels,source.incidence))
                b = Counter((label,tuple(sorted(j for j in ds if j in used)),
                             tuple(sorted(target.colors[j] for j in ds if j not in used)))
                            for label,ds in zip(target.tensor_labels,target.incidence))
                return a == b

            def visit(depth):
                nonlocal steps
                if depth==len(order):
                    return True
                i = order[depth]
                for j in candidates[i]:
                    if j in used:
                        continue
                    steps += 1
                    if steps > self.match_budget:
                        return False
                    mapping[i] = j
                    used.add(j)
                    if compatible() and visit(depth+1):
                        return True
                    used.remove(j)
                    del mapping[i]
                return False

            matched = visit(0)
            self.counts['match_steps'] += steps
            if steps > self.match_budget:
                self.counts['match_cutoffs'] += 1
            if not matched:
                return None
        # A verified tensor bijection is required even for the fast rank path.
        available = defaultdict(list)
        for t,label,ds in zip(target.tensors,target.tensor_labels,target.incidence):
            available[label,tuple(sorted(ds))].append(t)
        tensor_map = {}
        for t,label,ds in zip(source.tensors,source.tensor_labels,source.incidence):
            key = label,tuple(sorted(mapping[i] for i in ds))
            if not available[key]:
                return None
            tensor_map[t] = available[key].pop()
        if any(available.values()):
            return None
        return (dict(zip(source.state[0],target.state[0])),tensor_map,
                {source.ranks[i]:target.ranks[j] for i,j in mapping.items()})

    def _lookup(self, stage, ops, ext, external, owned):
        self.counts['builds'] += 1
        query = self.describe(stage,ops,ext,external,owned)
        for representative in self.buckets[query.bucket]:
            self.counts['exact_checks'] += 1
            mapping = self.exact_map(representative,query)
            if mapping is not None:
                self.counts['reused'] += 1
                return representative.state,mapping
            self.counts['bucket_nonmatches'] += 1
        self.buckets[query.bucket].append(query)
        self.counts['classes'] += 1
        return query.state,None

    def state(self, stage, ops, ext, external, owned):
        begin = perf_counter() if self.measure else 0.
        self.counts['calls'] += 1
        result = self.lookup(stage,ops,ext,external,owned)
        if self.measure:
            self.seconds += perf_counter()-begin
        return result
