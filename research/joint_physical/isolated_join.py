"""Compare one shared Join against independent Joins of the same selected rows."""

from accelforge.mapper.FFM._join_pmappings.pmapping_group import PmappingGroup
from accelforge.mapper.FFM._pareto_df.capacity_membership import is_membership_col, membership_for_target
from accelforge.mapper.FFM._pareto_df.df_convention import col_used_in_pareto
from accelforge.mapper.FFM._pareto_df.pareto import makepareto
from research.joint_search import ffm_backend as backend
from research.joint_search.conditional_composer import compose
from research.joint_search.validation import frontier


def audit(spec, groups, objects, jobs, contract, domain, outputs, points):
    records = []
    for point in points:
        index = domain.points.index(point)
        selected = {}
        for name, candidates in groups.items():
            selected[name] = []
            for group in candidates:
                data = group.mappings.data
                if not len(data):
                    continue
                mask = membership_for_target(data, 'JointArchitectureDomain', domain.labels[index])
                if mask.any():
                    frame = data.loc[mask].drop(columns=[c for c in data if is_membership_col(c)]).copy()
                    selected[name].append(PmappingGroup(group.compatibility,
                        group.mappings.update(data=frame,skip_pareto=True)))
        result = compose(backend.package(spec, selected, objects, jobs, contract))
        data = result.data
        raw = 'reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right'
        data = data[data[raw]<=point.capacity_bytes*8].copy()
        for c in data:
            if c.startswith('reservation<SEP>GlobalBuffer<SEP>'):
                data[c] = data[c.replace('reservation<SEP>','reservation_bits<SEP>')] / (point.capacity_bytes*8)
        columns = [c for c in data.select_dtypes(include='number') if col_used_in_pareto(c)]
        independent = frontier(makepareto(data,columns=columns)).to_dict('records')
        shared = frontier(outputs[point]).to_dict('records')
        records.append(dict(shape=[point.px,point.py],capacity_bytes=point.capacity_bytes,
                            independent_rows=len(independent),shared_rows=len(shared),equal=independent==shared))
    return records
