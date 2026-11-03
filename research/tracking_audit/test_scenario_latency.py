"""Bandwidth objectives must evaluate component formulas after scaling actions."""
import importlib
from types import SimpleNamespace

import pytest

from accelforge.frontend import arch
from accelforge.frontend.mapping import Compute, Mapping
from accelforge.frontend.mapper.metrics import Metrics
from accelforge.mapper.FFM._pareto_df.df_convention import scaled_latency2col
from accelforge.model._looptree.latency.memory import component_latency
from accelforge.model._looptree.reuse.symbolic import BuffetStats, SymbolicAnalysisOutput
from accelforge.model._looptree.types import Buffet

model = importlib.import_module(
    'accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.run_model')


@pytest.mark.parametrize('formula,expected', [
    ('read_latency + 5', 17),
    ('max(read_latency, 10)', 12),
    ('read_actions', 3),
    ('read_latency + latency_scale', 14),
    ("actions['read'].latency * read_actions + 5", 17),
    (5, 5),
    ('max(read_latency, write_latency)', 12),
])
def test_scenario_matches_independently_scaled_architecture(monkeypatch, formula, expected):
    memory = arch.Memory(name='GlobalBuffer', size=100, total_latency=formula, actions=[
        arch.TensorHolderAction(name='read', latency=2),
        arch.TensorHolderAction(name='write', latency=0),
    ])
    compute = arch.Compute(name='MAC', actions=[arch.Action(name='compute', latency=1)])
    reuse = SymbolicAnalysisOutput(buffet_stats={
        Buffet(tensor='X', einsum='E', level='GlobalBuffer'):
            BuffetStats(max_per_unit_read_actions=3),
    })
    workload = SimpleNamespace(n_instances=1, tensor_names_used_in_multiple_einsums=set(),
                               einsums={'E': SimpleNamespace(n_instances=1)})
    spec = SimpleNamespace(workload=workload, variables={})
    mapping = Mapping(nodes=[Compute(einsum='E', component='MAC')])
    job = SimpleNamespace(
        mapping=mapping, spec=spec, metrics=Metrics.LATENCY, is_copy_operation=False,
        einsum_name='E', flattened_arch=[memory, compute], memories_track_all=set(),
        ignored_resources=set(), latency_scales=(('GlobalBuffer', 2.0),),
    )
    monkeypatch.setattr(model, 'analyze_reuse_and_add_reservations_to_mapping', lambda _: reuse)
    monkeypatch.setattr(model, 'compute_energy_from_actions', lambda *args: {})
    data = model.run_model(job)[1]
    # The real architecture model scales individual actions, not total_latency.
    scaled_memory = memory.model_copy(deep=True)
    scaled_memory.latency_scale = 2
    scaled_memory.calculate_action_latency(in_place=True)
    reference = component_latency(reuse, [scaled_memory, compute], mapping, spec)
    assert float(reference['GlobalBuffer']) == expected
    assert float(data[scaled_latency2col('GlobalBuffer', 2.0)]) == expected
    # Generating one scenario must not modify the base costs used by other ones.
    assert memory.actions['read'].latency == 2
    assert memory.latency_scale == 1
