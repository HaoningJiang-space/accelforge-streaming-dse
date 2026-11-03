"""Reservation prefixes include every outer lifetime, including persistent data."""
import importlib
from types import SimpleNamespace

import pandas as pd
import pytest

from accelforge.frontend.arch import Memory
from accelforge.frontend.mapping import Compute, Mapping
from accelforge.frontend.mapper.metrics import Metrics
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from accelforge.mapper.FFM._pareto_df.df_convention import nameloop2col
from accelforge.model._looptree.reuse.symbolic import BuffetStats, SymbolicAnalysisOutput
from accelforge.model._looptree.types import Buffet

model = importlib.import_module(
    'accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.run_model')


def reservation_frame(monkeypatch, levels, sizes, instances=1):
    reuse = SymbolicAnalysisOutput(buffet_stats={
        Buffet(tensor=f'T{i}', einsum='E', level='Memory'): BuffetStats(
            max_occupancy=size, _n_loops_above=max(0, level), persistent=level == -1)
        for i, (level, size) in enumerate(zip(levels, sizes))
    })
    workload = SimpleNamespace(n_instances=instances, tensor_names_used_in_multiple_einsums=set(),
                               einsums={'E': SimpleNamespace(n_instances=1)})
    job = SimpleNamespace(
        mapping=Mapping(nodes=[Compute(einsum='E', component='MAC')]),
        spec=SimpleNamespace(workload=workload), metrics=Metrics.RESOURCE_USAGE,
        is_copy_operation=False, einsum_name='E',
        flattened_arch=[Memory(name='Memory', size=100)],
        memories_track_all={'Memory'}, ignored_resources=set(),
    )
    # Exercise run_model's real reservation assembly. Cost modeling is orthogonal.
    monkeypatch.setattr(model, 'analyze_reuse_and_add_reservations_to_mapping', lambda _: reuse)
    monkeypatch.setattr(model, 'component_latency', lambda *args: {})
    monkeypatch.setattr(model, 'compute_energy_from_actions', lambda *args: {})
    return pd.DataFrame([model.run_model(job)[1]])


@pytest.mark.parametrize('levels,sizes,instances,expected', [
    ([-1, 0], [20, 30], 1, {-1: .2, 0: .5}),
    ([0, -1], [30, 20], 2, {-1: .4, 0: .7}),
    ([8, 1], [30, 20], 1, {1: .2, 8: .5}),
])
def test_prefixes_follow_lifetime_order(monkeypatch, levels, sizes, instances, expected):
    data = reservation_frame(monkeypatch, levels, sizes, instances)
    for level, value in expected.items():
        assert data[nameloop2col('Memory', level)].iloc[0] == pytest.approx(value)


def test_persistent_data_is_included_in_peak_capacity_check(monkeypatch):
    data = reservation_frame(monkeypatch, [-1, 0], [60, 60])
    frame = PmappingDataframe(data, 1, 1, skip_pareto=True, check_above_subset_below=False)
    frame.limit_capacity(drop_valid_reservations=False)
    assert frame.data.empty  # 60 persistent + 60 temporary bits exceed 100 bits.


def test_capacity_elimination_drops_only_the_finished_level():
    outer, inner = nameloop2col('Memory', 0), nameloop2col('Memory', 2)
    frame = PmappingDataframe(pd.DataFrame({outer: [.2], inner: [.8]}), 1, 1, skip_pareto=True)
    frame.limit_capacity(next_shared_loop_index=-1)
    assert outer not in frame.data
    assert inner in frame.data
    assert frame.right_reservations == {'Memory': {2}}
