"""Extract consumer tile hints from an actual native numeric Join prefix."""

import numpy as np

from accelforge.mapper.FFM._join_pmappings import join_engine
from accelforge.mapper.FFM._join_pmappings.compress_pmappings import compress_einsum2pmappings
from accelforge.mapper.FFM._join_pmappings.join_context import JoinContext
from accelforge.mapper.FFM._join_pmappings.partial_state import copy_groups
from accelforge.mapper.FFM._pareto_df.capacity_membership import membership_for_target


def extract(spec, groups, domain, boundary):
    """Keep live boundary reservations. The future seed only declares liveness.

    The next-Einsum lookahead filter is disabled so its initial seed patterns
    cannot veto native numeric prefixes. Hints never remove a candidate.
    """
    compressed, _ = compress_einsum2pmappings(copy_groups(groups))
    context = JoinContext.from_spec(spec, lookahead_filter=False)
    state = join_engine.advance(join_engine.start(compressed, context))
    if len(state.processed)!=2 or len(state.remaining)!=1:
        raise ValueError('prefix hints require a three-operator chain')
    by_point = {point:set() for point in domain.points}
    row_count = 0
    for group in state.left:
        data = group.mappings.data
        if not len(data):
            continue
        row_count += len(data)
        # Use the actual boundary reservation's loop prefix. Repeated rank
        # occurrences are ambiguous for this heuristic and are left unbound.
        for reservation in group.compatibility.tensors:
            if reservation.name!=boundary or reservation.resource_name!='GlobalBuffer':
                continue
            loops = [loop for loop in reservation.loops if not loop.is_spatial]
            names = [str(loop.rank_name).lower() for loop in loops]
            columns = []
            for name,loop in zip(names,loops):
                if names.count(name)!=1:
                    continue
                size = loop.tile_pattern.tile_shape
                if isinstance(size,str):
                    if size not in data:
                        continue
                    values = data[size].to_numpy()
                else:
                    values = np.full(len(data),size)
                columns.append((name,values))
            if not columns:
                continue
            for i,point in enumerate(domain.points):
                mask = membership_for_target(data,'JointArchitectureDomain',domain.labels[i])
                for row in zip(*(values[mask] for _,values in columns)):
                    try:
                        sizes = tuple(int(v) for v in row)
                    except (TypeError, ValueError, OverflowError):
                        continue
                    if all(v>=1 and v==original and not (v&(v-1)) for v,original in zip(sizes,row)):
                        by_point[point].add(tuple(sorted((name,v) for (name,_),v in zip(columns,sizes))))
    return by_point,row_count
