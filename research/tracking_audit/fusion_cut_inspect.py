"""Conservative structural inspection of one reconstructed two-MatMul mapping.

No capacity/traffic lower bound is issued here. A Mapping tree alone does not
prove simultaneous physical reservations, aliasing, recomputation or in-flight
transfer semantics. This module deliberately fails closed on unknown structure.
"""
from accelforge.frontend.mapping import Compute, Loop, Nested, Pipeline, Reservation, Sequential, Split, Storage, Toll


def inspect_whole_tensor_cut(mapping, *, producer='Matmul0', consumer='Matmul1', tensor='T1'):
    result = dict(kind='unsupported', reason=None, tensor=tensor,
                  safe_to_prune=False, cross_cut_storage=[], cross_cut_reservations=[], phase_storage=[],
                  proof_obligations=['workload tensor extent and full producer/consumer access',
                      'mapping execution and data dependency semantics',
                      'simultaneously live other reservations and aliasing',
                      'recomputation, other storage levels and in-flight transfers'])
    if not isinstance(mapping, Nested):
        result['reason'] = 'mapping is not Nested'
        return result
    roots = list(mapping.nodes)
    splits = [i for i,n in enumerate(roots) if isinstance(n, Split)]
    if len(splits) != 1 or not isinstance(roots[splits[0]], Sequential):
        result['reason'] = 'requires one root Sequential split'
        return result
    index = splits[0]
    if any(not isinstance(n, (Storage, Reservation)) for n in roots[:index]) or roots[index+1:]:
        result['reason'] = 'outer loop, unsupported node or trailing node prevents whole-graph barrier'
        return result
    split = roots[index]
    if len(split.nodes) != 2:
        result['reason'] = 'requires exactly two sequential branches'
        return result
    for n in roots[:index]:
        if isinstance(n, Storage) and tensor in n.tensors:
            result['cross_cut_storage'].append(n.component)
        if isinstance(n, Reservation) and tensor in n.purposes:
            result['cross_cut_reservations'].append(n.resource)
    for expected, child in zip((producer,consumer), split.nodes):
        nodes = child._flatten()
        if any(isinstance(n, (Split, Pipeline, Toll)) for n in nodes):
            result['reason'] = 'nested split, pipeline or Toll is unsupported'
            return result
        if any(not isinstance(n, (Nested, Storage, Reservation, Loop, Compute)) for n in nodes):
            result['reason'] = 'unknown node in sequential phase'
            return result
        computes = [n.einsum for n in nodes if isinstance(n, Compute)]
        if computes != [expected] or not isinstance(nodes[-1], Compute):
            result['reason'] = 'expected exactly one ordered compute per phase'
            return result
        result['phase_storage'].append(dict(einsum=expected,
            tensor_components=[n.component for n in nodes if isinstance(n, Storage) and tensor in n.tensors],
            tensor_reservations=[n.resource for n in nodes if isinstance(n, Reservation) and tensor in n.purposes],
            loops=[dict(kind=type(n).__name__,rank=str(n.rank_variable),tile=str(n.tile_shape))
                   for n in nodes if isinstance(n, Loop)]))
    result['kind'] = 'root_sequential_producer_consumer'
    return result
