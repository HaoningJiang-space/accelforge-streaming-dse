from fractions import Fraction
from types import SimpleNamespace

import pytest

from .analytic_bounds import lower_bound, floor_power_two, factor_domain, check_frozen_inputs, audit_vectors
from .protocol import Hardware, Domain


def test_geometry_accounts_for_undivisible_fanout_and_rank_limits():
    case = SimpleNamespace(arch='nvdla', workload='matmuls', params=(3, 256, 256))
    central = lower_bound(case, Hardware(32, 192, 131072))
    extreme = lower_bound(case, Hardware(1, 6144, 131072))
    assert central.phase_parallelism == (4096,)*3
    assert extreme.phase_parallelism == (256,)*3
    assert extreme.latency == 16*central.latency
    assert lower_bound(case, Hardware(32,192,262144)).edp == central.edp
    assert central.compulsory_dram_bits == 5*256*256*8  # input + 3 weights + final output
    assert central.compute_ops == 3*256**3
    check_frozen_inputs()


def test_unsupported_workload_cannot_enable_cuts():
    point = Hardware(8, 8, 1024)
    with pytest.raises(ValueError):
        lower_bound(SimpleNamespace(arch='nvdla', workload='attention', params=(128,1,64)), point)
    with pytest.raises(ValueError):
        lower_bound(SimpleNamespace(arch='nvdla', workload='matmuls', params=(3,7,8)), point)
    with pytest.raises(ValueError):
        floor_power_two(0)


def test_full_reference_audit_detects_a_bound_violation():
    case = SimpleNamespace(arch='nvdla', workload='matmuls', params=(3,256,256))
    domain = Domain((Hardware(32,192,131072),))
    record = dict(architecture=dict(px=32,py=192,capacity_bytes=131072), vectors=[{
        'Total<SEP>energy':1e-6, 'Total<SEP>latency':1e-6}])
    with pytest.raises(AssertionError, match='inadmissible'):
        audit_vectors(case, domain, [record])


def test_factor_domain_is_all_ordered_pairs_not_a_selected_geometry_subset():
    domain = factor_domain()
    shapes = {(p.px,p.py) for p in domain.points}
    assert len(domain.points) == 96 and len(shapes) == 24
    assert shapes == {(x,6144//x) for x in range(1,6145) if 6144%x==0}
    assert all(p.px*p.py==6144 for p in domain.points)
