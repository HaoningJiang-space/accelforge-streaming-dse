"""Use original FFM composition and select one supported architecture."""
from accelforge.mapper.FFM._pareto_df.capacity_membership import is_membership_col, membership_for_target
from accelforge.mapper.FFM._pareto_df.pareto import makepareto
from accelforge.mapper.FFM._pareto_df.df_convention import col_used_in_pareto
from research.tracking_audit import common


def compose(candidates):
    return common.join_pmappings(candidates)


def query_architecture(result, domain, architecture):
    """Recover that architecture's complete numeric frontier and source closures."""
    index = domain.points.index(architecture)
    data = result.data[membership_for_target(result.data,'JointArchitectureDomain',domain.labels[index])].copy()
    raw = 'reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right'
    data = data[data[raw] <= architecture.capacity_bytes*8].copy()
    data = data.drop(columns=[c for c in data if is_membership_col(c)])
    data['capacity_reference_bits<SEP>GlobalBuffer'] = architecture.capacity_bytes*8
    for c in data:
        if c.startswith('reservation<SEP>GlobalBuffer<SEP>'):
            data[c] = data[c.replace('reservation<SEP>','reservation_bits<SEP>')] / (architecture.capacity_bytes*8)
    # Public Mapping closures are named Total<SEP>mapping but are not objectives.
    columns = [c for c in data.select_dtypes(include='number') if col_used_in_pareto(c)]
    return makepareto(data, columns=columns)
