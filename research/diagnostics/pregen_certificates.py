"""Read-only necessary-condition certificates. No native search decisions change."""
from dataclasses import dataclass, field
from fractions import Fraction
import math

from accelforge.frontend.mapping import Loop, Spatial, TensorHolder, Storage, Compute
from research.graph_coopt.template_support_audit import possible_interfaces


@dataclass(frozen=True)
class Bound:
    gb_bits: int = 0
    register_bits: int = 0
    energy: Fraction = Fraction(0)
    latency: Fraction = Fraction(0)

    def record(self):
        return dict(gb_bits=self.gb_bits, register_bits=self.register_bits,
            energy_j=float(self.energy), latency_s=float(self.latency),
            energy_rational=str(self.energy), latency_rational=str(self.latency))


@dataclass
class Facts:
    key: str
    einsum: str
    bound: Bound
    local_impossible: bool = False
    unknown: str | None = None
    spatial_min: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    compatibility: object = None


def required_bits(copies):
    """Same tensor may share storage; distinct tensor occupancies add locally."""
    per_tensor = {}
    for name, bits in copies:
        per_tensor[name] = max(per_tensor.get(name, 0), bits)
    return sum(per_tensor.values())


def largest_divisor(extent, cap):
    result = 1
    for d in range(1, math.isqrt(extent)+1):
        if extent % d == 0:
            for x in (d,extent//d):
                if x<=cap:
                    result = max(result,x)
    return result


def _actions(job):
    return {(str(n.name),str(a.name)):a for n in job.flattened_arch for a in getattr(n,'actions',())}


def _coefficient(actions, component, action, field):
    value = getattr(actions[(component,action)], field)
    value = Fraction(str(value))
    if value < 0:
        raise ValueError('negative action coefficient')
    return value


def extract_facts(job, key):
    """Pre-run_model only. Unknown grammars get zero bounds and remain eligible."""
    from accelforge.model._looptree.reuse.symbolic import IMPERFECT
    try:
        if job.is_copy_operation or job.spec.workload.n_instances != 1 or job.einsum.n_instances != 1:
            raise ValueError('requires one-instance dense compute')
        accesses = list(job.einsum.tensor_accesses)
        if len(accesses)!=3 or len({str(t.name) for t in accesses})!=3:
            raise ValueError('requires three distinct dense operands')
        shape = {str(k):int(v) for k,v in job.rank_variable_bounds.items()}
        if any(v<=0 for v in shape.values()):
            raise ValueError('nonpositive domain is outside this grammar')
        projections = {str(t.name):tuple(map(str,t.projection.values())) for t in accesses}
        if any(len(p)!=2 or len(set(p))!=2 or not set(p)<=shape.keys() for p in projections.values()):
            raise ValueError('requires direct two-axis projections')
        if (len(set(projections.values()))!=3 or len(job.einsum.output_tensor_names)!=1 or
            any(sum(r in p for p in projections.values())!=2 for r in set().union(*map(set,projections.values())))):
            raise ValueError('requires ordinary dense MatMul incidence')
        precision = {str(t.name):int(t.bits_per_value) for t in accesses}
        if any(v<=0 for v in precision.values()):
            raise ValueError('nonpositive precision')
        if len(set().union(*map(set,projections.values())))!=3:
            raise ValueError('requires dense MatMul rank incidence')
        axes = {(str(n.name),str(s.name)):int(s.fanout)
            for n in job.flattened_arch for s in n.spatial}
        state = {r:(n,n) for r,n in shape.items()}
        copies = {'GlobalBuffer':[], 'Register':[]}
        first_holder = {}
        spatial_min, spatial_nodes = {}, {}
        impossible = False
        notes = []
        for node in job.mapping.nodes:
            if isinstance(node,Loop):
                rank = str(node.rank_variable)
                if rank not in state or node.initial_tile_shape is not None:
                    raise ValueError('unsupported rank/initial Tile')
                lo,hi = state[rank]
                value = node.tile_shape
                if isinstance(value,int):
                    if value<=0 or value>hi:
                        impossible = True
                    new = (max(1,value),max(1,value))
                    count_min = max(1,math.ceil(lo/max(1,value)))
                else:
                    # Each raw "symbol" is an independently unbound Tile.
                    new, count_min = (1,hi),1
                if isinstance(node,Spatial):
                    axis = (str(node.component),str(node.name))
                    if axis not in axes:
                        raise ValueError('unknown spatial axis')
                    spatial_min[axis] = spatial_min.get(axis,1)*count_min
                    spatial_nodes.setdefault(axis,[]).append(node)
                state[rank] = new
            elif isinstance(node,TensorHolder):
                if not isinstance(node,Storage):
                    raise ValueError('Toll/copy node is outside this storage grammar')
                for tensor in map(str,node.tensors):
                    first_holder.setdefault(tensor,str(node.component))
                    if str(node.component) in copies and tensor in projections:
                        bits = precision[tensor]*math.prod(state[r][0] for r in projections[tensor])
                        copies[str(node.component)].append((tensor,bits))
                        notes.append(dict(tensor=tensor,resource=str(node.component),bits=bits,
                            lower_extents=[state[r][0] for r in projections[tensor]]))
            elif not isinstance(node,Compute):
                raise ValueError('split/transform/unknown node is outside linear grammar')
        for resource in copies:
            if resource=='GlobalBuffer' and {n for n,_ in copies[resource]} != set(projections):
                raise ValueError('not all operands have GB storage')
        # Operation volume is the MatMul's own three rank extents.
        used_ranks = set().union(*map(set,projections.values()))
        work = math.prod(shape[r] for r in used_ranks)
        actions = _actions(job)
        if any(Fraction(str(a.energy))<0 for a in actions.values()) or any(
            Fraction(str(getattr(n,'leak_power',0)))<0 for n in job.flattened_arch):
            raise ValueError('requires nonnegative native action/leak coefficients')
        e = work*_coefficient(actions,'MAC','compute','energy')
        read_bits = write_bits = 0
        outputs = set(map(str,job.einsum.output_tensor_names))
        for tensor,place in first_holder.items():
            if place=='MainMemory' and tensor in projections:
                bits = precision[tensor]*math.prod(shape[r] for r in projections[tensor])
                if tensor in outputs:
                    write_bits += bits
                else:
                    read_bits += bits
        e += read_bits*_coefficient(actions,'MainMemory','read','energy')
        e += write_bits*_coefficient(actions,'MainMemory','write','energy')
        max_pe = 1
        for axis,cap in axes.items():
            nodes = spatial_nodes.get(axis,[])
            if not nodes:
                count = 1
            elif (len(nodes)==1 and not IMPERFECT and nodes[0]._assume_perfect_factor):
                count = largest_divisor(shape[str(nodes[0].rank_variable)],cap)
            else:
                count = cap
            max_pe *= count
        latency = max(Fraction(work,max_pe)*_coefficient(actions,'MAC','compute','latency'),
            read_bits*_coefficient(actions,'MainMemory','read','latency'),
            write_bits*_coefficient(actions,'MainMemory','write','latency'))
        return Facts(key,str(job.einsum_name),Bound(required_bits(copies['GlobalBuffer']),
            required_bits(copies['Register']),e,latency),impossible,
            spatial_min=spatial_min, compatibility=job.compatibility,
            evidence=dict(storage_copies=notes,mandatory_mac_actions=work,
                dram_backing_read_bits=read_bits,dram_backing_write_bits=write_bits,
                max_spatial_instances=max_pe,
                real_arithmetic_cost_only=True,min_utilization_used_as_hard_constraint=False))
    except (ValueError,TypeError,KeyError,AttributeError,ZeroDivisionError) as error:
        return Facts(key,str(job.einsum_name),Bound(),unknown=str(error),compatibility=None)


def architecture_reasons(fact, gb_bits, register_bits, spatial_caps):
    reasons = []
    if fact.local_impossible:
        reasons.append('local_interval_contradiction')
    if fact.bound.gb_bits > gb_bits:
        reasons.append('gb_lower_bound_exceeds_capacity')
    if fact.bound.register_bits > register_bits:
        reasons.append('register_lower_bound_exceeds_capacity')
    for axis,value in fact.spatial_min.items():
        if value>spatial_caps[axis]:
            reasons.append('minimum_spatial_instances_exceed_fanout')
    return reasons


def supports(left, right):
    # Unknown includes all legal possibilities, not no support.
    return left is None or right is None or bool(left & right)


class Relaxation:
    def __init__(self, facts, nodes, edges):
        self.facts = {f.key:f for f in facts}
        self.roles = {e:{f.key for f in facts if f.einsum==e} for e in nodes}
        self.neighbors = {e:set() for e in nodes}
        self.adjacency = {f.key:{} for f in facts}
        self.patterns = {}
        for a,b,tensor in edges:
            self.neighbors[a].add(b)
            self.neighbors[b].add(a)
        # Bundle tensors shared by each mandatory pair, never external inputs.
        for a in nodes:
            for b in self.neighbors[a]:
                shared = sorted({t for x,y,t in edges if {x,y}=={a,b}})
                for key in self.roles[a] | self.roles[b]:
                    pkey = (key,tuple(shared))
                    if pkey not in self.patterns:
                        comp = self.facts[key].compatibility
                        self.patterns[pkey] = (None if comp is None else possible_interfaces(comp,shared))
                for key in self.roles[a]:
                    left = self.patterns[(key,tuple(shared))]
                    self.adjacency[key][b] = {peer for peer in self.roles[b]
                        if supports(left,self.patterns[(peer,tuple(shared))])}

    def condition(self, allowed, forced):
        """Necessary support closure. No numeric plan or Tile is constructed."""
        active = set(allowed)
        role = self.facts[forced].einsum
        active -= self.roles[role]-{forced}
        if forced not in active:
            return set()
        changed = True
        while changed:
            removed = {key for key in active if any(not(peers & active)
                for peers in self.adjacency[key].values())}
            changed = bool(removed)
            active -= removed
        if any(not(keys & active) for keys in self.roles.values()):
            return set()
        return active

    def completion_bound(self, active):
        if not active:
            return None
        domains = [[self.facts[k].bound for k in keys & active] for keys in self.roles.values()]
        if any(not d for d in domains):
            return None
        return Bound(max(min(b.gb_bits for b in d) for d in domains),
            max(min(b.register_bits for b in d) for d in domains),
            sum((min(b.energy for b in d) for d in domains),Fraction(0)),
            sum((min(b.latency for b in d) for d in domains),Fraction(0)))


def reference_oracle_dominator(bound, frontier):
    """POST-HOC diagnostic only. Never called by a rejection predicate."""
    if bound is None:
        return None
    values = frontier['values']
    if any(c.startswith('reservation_bits<SEP>') and not c.startswith(
        ('reservation_bits<SEP>GlobalBuffer<SEP>','reservation_bits<SEP>Register<SEP>')) for c in values):
        return None
    for i,(e,t) in enumerate(zip(values['Total<SEP>energy'],values['Total<SEP>latency'])):
        if (Fraction(str(e))<=bound.energy and Fraction(str(t))<=bound.latency and
            all(v[i] <= (bound.gb_bits if 'GlobalBuffer' in c else bound.register_bits)
                for c,v in values.items() if c.startswith('reservation_bits<SEP>'))):
            return i
    return None
