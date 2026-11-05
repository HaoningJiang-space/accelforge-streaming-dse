from dataclasses import FrozenInstanceError
import pytest

from research.joint_search.architecture_domain import Architecture, ArchitectureDomain
from research.joint_search.validation import audit, gate_domain
from research.tracking_audit import common


def test_domain_is_one_global_budgeted_variable():
    d=gate_domain()
    assert len(d.points)==6
    assert {p.px*p.py for p in d.points}=={256}
    assert len(set(d.labels))==6 and sorted(d.labels)==list(d.labels)
    with pytest.raises(FrozenInstanceError):
        d.points=()
    with pytest.raises(ValueError):
        ArchitectureDomain((Architecture(4,8,96),Architecture(8,8,96)))
    with pytest.raises(ValueError):
        Architecture(3,8,96)
    with pytest.raises(ValueError):
        ArchitectureDomain((Architecture(4,8,96),)*2)


def test_shared_six_point_policy_and_full_frontier_gate():
    report=audit(validate_all=False)
    assert report['status']=='complete' and len(report['points'])==6
    assert all(p['coverage']['exact_policy_tile_sets'] for p in report['points'])
    assert all(p['quality']['exact_full_etr_frontier'] for p in report['points'])
    assert report['shared_stats']['shared_generation_calls']==1
    assert report['shared_stats']['shared_join_calls']==1
    assert not report['consumer_requirements_enabled']


def test_integer_capacity_boundary_is_not_a_membership_ratio():
    d=ArchitectureDomain((Architecture(4,8,68),Architecture(4,8,96)))
    report=audit(common.Case('matmuls','nvdla',(2,4,8)),d,validate_all=False)
    assert all(p['coverage']['exact_policy_tile_sets'] and p['quality']['exact_full_etr_frontier']
               for p in report['points'])
