"""Conservative reservation-scope ledger for a restricted MatMul chain.

This records one representative perfect-tile iteration per sequential phase.
It is not a cycle trace, does not establish cross-phase copy validity, and must
not be used as a graph-cut pruning certificate.
"""
from dataclasses import dataclass

from accelforge.frontend.mapping import Compute, Loop, Nested, Reservation, Spatial, Split, Storage
from research.tracking_audit.fusion_cut_inspect import inspect_whole_tensor_cut


class UnsupportedLedger(ValueError):
    """The input is outside the explicitly supported semantic subset."""


def validate_dense_contract(spec, m, kn):
    """Check model inputs used by the restricted 8-bit dense-tile adapter.

    This is a model-input check, not a proof of mapping correctness, aliases,
    cut simultaneity or physical execution. Unsupported inputs fail closed.
    """
    from research.tracking_audit import common
    if any(type(v) is not int or v <= 0 for v in (m,kn)):
        raise UnsupportedLedger('workload dimensions must be positive integers')
    evaluated = spec._spec_eval_expressions(eval_arch=False,eval_non_arch=True)
    expected = {
        'Matmul0': {'T0':({'M':'m','N0':'n0'},False), 'W0':({'N0':'n0','N1':'n1'},False),
                    'T1':({'M':'m','N1':'n1'},True)},
        'Matmul1': {'T1':({'M':'m','N1':'n1'},False), 'W1':({'N1':'n1','N2':'n2'},False),
                    'T2':({'M':'m','N2':'n2'},True)},
    }
    einsums = list(evaluated.workload.einsums)
    if len(einsums) != 2 or set(e.name for e in einsums) != set(expected):
        raise UnsupportedLedger('requires exactly the two expected MatMul einsums')
    if evaluated.workload.n_instances != 1 or any(e.n_instances != 1 for e in einsums):
        raise UnsupportedLedger('multiple workload or einsum instances are unsupported')
    for einsum in einsums:
        accesses = list(einsum.tensor_accesses)
        if len(accesses) != 3 or {a.name for a in accesses} != set(expected[einsum.name]):
            raise UnsupportedLedger('unexpected tensor set')
        for access in accesses:
            projection, output = expected[einsum.name][access.name]
            if (dict(access.projection) != projection or access.bits_per_value != 8
                    or access.output != output or access.persistent or access.backing_storage_size_scale != 1):
                raise UnsupportedLedger('unexpected tensor projection, precision or storage policy')
    if common.get_rank_variable_bounds_for_all_einsums(spec) != {'m':m,'n0':kn,'n1':kn,'n2':kn}:
        raise UnsupportedLedger('unexpected iteration bounds')
    if dict(evaluated.arch.find('GlobalBuffer').bits_per_value_scale) != {'All':1}:
        raise UnsupportedLedger('requires unit GlobalBuffer bit scaling')
    return dict(kind='two_dense_matmuls_8bit_unit_gb_scale',m=m,kn=kn,
                caveat='model inputs checked; cross-phase lifetimes and aliasing remain unproved')


@dataclass(frozen=True)
class Allocation:
    resource: str
    bits: int | None


class Ledger:
    """Independent allocation accounting; unknown bytes never become zero."""
    def __init__(self, capacities):
        self.capacities = dict(capacities)
        if any(type(v) is not int or v < 0 for v in self.capacities.values()):
            raise ValueError('capacities must be nonnegative integer bits')
        self.active = {}
        self.events = []
        self.peak_lower = {k:0 for k in capacities}
        self.peak_exact = {k:0 for k in capacities}

    def _record(self, kind, key, allocation):
        resource = allocation.resource
        allocations = [v for v in self.active.values() if v.resource == resource]
        known = sum(v.bits for v in allocations if v.bits is not None)
        unknown = sum(v.bits is None for v in allocations)
        cap = self.capacities[resource]
        self.peak_lower[resource] = max(self.peak_lower[resource], known)
        if unknown:
            self.peak_exact[resource] = None
        elif self.peak_exact[resource] is not None:
            self.peak_exact[resource] = max(self.peak_exact[resource], known)
        status = 'exceeds' if known > cap else ('unknown' if unknown else 'fits')
        self.events.append(dict(kind=kind, allocation_id=key, resource=resource,
                                bits=allocation.bits, known_live_bits=known,
                                unknown_allocations=unknown, capacity_bits=cap, status=status))

    def allocate(self, key, resource, bits):
        if key in self.active:
            raise ValueError('duplicate allocation ID')
        if resource not in self.capacities:
            raise ValueError('resource has no specified capacity')
        if bits is not None and (type(bits) is not int or bits < 0):
            raise ValueError('allocation size must be nonnegative integer bits or unknown')
        allocation = Allocation(resource, bits)
        self.active[key] = allocation
        self._record('allocate', key, allocation)

    def release(self, key):
        if key not in self.active:
            raise ValueError('release of unknown allocation ID')
        allocation = self.active.pop(key)
        self._record('release', key, allocation)

    def observe(self, kind, *, resource='GlobalBuffer', **details):
        """Record a structural marker without claiming it allocates a copy."""
        if resource not in self.capacities:
            raise ValueError('resource has no specified capacity')
        allocations = [v for v in self.active.values() if v.resource == resource]
        known = sum(v.bits for v in allocations if v.bits is not None)
        unknown = sum(v.bits is None for v in allocations)
        cap = self.capacities[resource]
        self.events.append(dict(kind=kind,known_live_bits=known,unknown_allocations=unknown,
            capacity_bits=cap,status='exceeds' if known > cap else ('unknown' if unknown else 'fits'),
            **details))


def _linear_phase(child):
    """Flatten only Nested containers; a split or unknown node is forbidden."""
    result = []
    def visit(node):
        if isinstance(node, Split):
            raise UnsupportedLedger('nested or parallel split')
        if isinstance(node, Nested):
            for child in node.nodes:
                visit(child)
        elif isinstance(node, (Loop, Reservation, Storage, Compute)):
            result.append(node)
        else:
            raise UnsupportedLedger('unsupported mapping node: '+type(node).__name__)
    visit(child)
    return result


def phase_ledger(child, phase, m, kn, capacity_bits):
    """Model one phase's GlobalBuffer reservation nesting for dense MatMul.

    Only the repository matmuls.yaml identity projections, 8-bit values, no
    aliases, unit storage scaling, and perfect uniform tiles are supported.
    At most one reservation per tensor is allowed per phase. All GlobalBuffer
    reservations must precede spatial loops, avoiding replication accounting.
    """
    if phase not in (0,1) or any(type(v) is not int or v <= 0 for v in (m,kn,capacity_bits)):
        raise ValueError('positive integer workload and capacity required')
    dims = {'m':m,'n0':kn,'n1':kn,'n2':kn}
    tensors = ({'T0':('m','n0'),'W0':('n0','n1'),'T1':('m','n1')} if phase == 0
               else {'T1':('m','n1'),'W1':('n1','n2'),'T2':('m','n2')})
    nodes = _linear_phase(child)
    if not nodes or not isinstance(nodes[-1], Compute) or nodes[-1].einsum != f'Matmul{phase}':
        raise UnsupportedLedger('phase does not terminate in the expected compute')
    ledger = Ledger({'GlobalBuffer':capacity_bits})
    seen, allocated = set(), []
    spatial_seen = False
    for position,node in enumerate(nodes):
        if isinstance(node, Loop):
            rank = str(node.rank_variable)
            if rank not in dims:
                raise UnsupportedLedger('unknown or non-scalar loop rank')
            tile = node.tile_shape
            if type(tile) is not int or tile <= 0 or tile > dims[rank] or dims[rank] % tile:
                raise UnsupportedLedger('requires integral perfect nested tiles')
            if node.initial_tile_shape not in (None,tile):
                raise UnsupportedLedger('imperfect initial tile')
            dims[rank] = tile
            spatial_seen |= isinstance(node, Spatial)
            ledger.observe('representative_loop',rank=rank,tile=tile,loop_type=type(node).__name__)
        elif isinstance(node, Storage):
            # A storage declaration is not itself an allocation event.
            ledger.observe('storage_declaration',component=node.component,tensors=list(node.tensors))
        elif isinstance(node, Reservation) and node.resource == 'GlobalBuffer':
            if spatial_seen or node.persistent:
                raise UnsupportedLedger('spatial replication or persistent reservation')
            for tensor in node.purposes:
                if tensor not in tensors or tensor in seen:
                    raise UnsupportedLedger('unknown, repeated or aliased tensor reservation')
                seen.add(tensor)
                size = 8
                for rank in tensors[tensor]:
                    size *= dims[rank]
                key = f'{phase}:{position}:{tensor}'
                ledger.allocate(key,'GlobalBuffer',size)
                allocated.append(key)
        elif isinstance(node, Reservation):
            ledger.observe('untracked_reservation',untracked_resource=node.resource,purposes=list(node.purposes))
        elif isinstance(node, Compute):
            ledger.observe('representative_compute',einsum=node.einsum)
    # These scope exits are the end of the representative phase iteration,
    # not an assertion that cross-phase copies physically cease to exist.
    for key in reversed(allocated):
        ledger.release(key)
    assert not ledger.active
    return dict(phase=f'Matmul{phase}',events=ledger.events,
                peak_known_bits=ledger.peak_lower['GlobalBuffer'],
                conditional_peak_bits=ledger.peak_exact['GlobalBuffer'],
                assumptions=['independent tensor reservations do not alias',
                             'representative iteration is uniform',
                             'reservation scopes follow the chosen linear interpretation'],
                status_under_assumptions='exceeds' if any(e['status']=='exceeds' for e in ledger.events) else 'fits',
                representative_iteration_only=True)


def mapping_ledger(mapping, m, kn, capacity_bits, *, contract=None):
    if not isinstance(contract, dict) or any(contract.get(k) != v for k,v in
            (('kind','two_dense_matmuls_8bit_unit_gb_scale'),('m',m),('kn',kn))):
        return dict(status='unsupported', reason='validated dense model contract required', safe_to_prune=False)
    cut = inspect_whole_tensor_cut(mapping)
    if cut['kind'] != 'root_sequential_producer_consumer':
        return dict(status='unsupported', reason=cut['reason'], safe_to_prune=False)
    split = next(n for n in mapping.nodes if isinstance(n, Split))
    try:
        phases = [phase_ledger(child, i, m, kn, capacity_bits) for i,child in enumerate(split.nodes)]
    except UnsupportedLedger as error:
        return dict(status='unsupported', reason=str(error), safe_to_prune=False)
    return dict(status='phase_scopes_only', phases=phases,
                phase_peak_bits=max(x['peak_known_bits'] for x in phases),
                boundary_event=dict(kind='between_sequential_phases',intermediate='T1',
                    globalbuffer_live_bits=None,other_globalbuffer_live_bits=None,
                    status='unknown',reason='cross-phase physical lifetime has not been established'),
                cross_cut_physical_occupancy='unknown', cut_free_capacity_bits=None,
                safe_to_prune=False)
