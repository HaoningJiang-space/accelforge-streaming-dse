"""Small native counterexample gate; real Attention128 remains the main experiment."""
from unittest.mock import patch

from research.joint_budget.protocol import Domain,Hardware
from research.joint_search import validation
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import validate_pick
from .demand import search


def test_complete_physical_witness_quality_on_small_native_attention():
    case = common.Case('attention','nvdla',(8,1,4))
    domain = Domain(tuple(Hardware(x,y,c) for x,y in ((2,12),(4,6),(6,4),(12,2)) for c in (64,96,128)))
    native_build = validation.build
    def relaxed(*args,**kwargs):
        spec = native_build(*args,**kwargs)
        for dim in spec.arch.find('ArrayFanout').spatial:
            dim.min_usage = 0
        return spec
    common.af.set_n_parallel_jobs(1)
    with patch.object(validation,'build',relaxed):
        expected,_,_ = validation.capacity_events(case,domain)
    actual,stats = search(case,domain,completion_limit=4096)
    assert stats['full_cartesian_tile_enumeration'] is False
    assert stats['proposer']['cartesian_tile_expansions']==0
    assert stats['proposer']['complete_factor_assignments']>0
    for capacity in (64,96,128):
        old,new = [],[]
        for point in domain.points:
            if point.capacity_bytes>capacity:
                continue
            for outputs,records in ((expected,old),(actual,new)):
                row = common.best_row(outputs[point])
                witness = validate_pick(case,(point.px,point.py),point.capacity_bytes,row)
                assert witness['ok']
                if witness['feasible']:
                    records.append(witness['edp'])
        assert old and new
        assert min(new)<=min(old)
