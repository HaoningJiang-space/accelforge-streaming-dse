import pytest

from accelforge.frontend.mapping import Compute, Mapping, Nested, Reservation, Sequential, Spatial, Storage, Temporal
from research.tracking_audit.fusion_lifetime_ledger import Ledger, mapping_ledger, phase_ledger, UnsupportedLedger, validate_dense_contract

CONTRACT = dict(kind='two_dense_matmuls_8bit_unit_gb_scale',m=4,kn=8)


def test_ledger_tracks_unknown_and_definite_overflow_without_false_certificate():
    ledger = Ledger({'GB':100})
    ledger.allocate('a','GB',40)
    ledger.allocate('unknown','GB',None)
    assert ledger.events[-1]['known_live_bits'] == 40
    assert ledger.events[-1]['status'] == 'unknown'
    assert ledger.peak_exact['GB'] is None
    ledger.allocate('b','GB',70)
    assert ledger.events[-1]['status'] == 'exceeds'
    ledger.release('b')
    ledger.release('unknown')
    ledger.release('a')
    assert ledger.peak_lower['GB'] == 110 and ledger.peak_exact['GB'] is None
    assert not ledger.active
    with pytest.raises(ValueError):
        ledger.release('a')


def test_invalid_sizes_resources_and_duplicate_ids_are_rejected():
    ledger = Ledger({'GB':100})
    for size in (-1,1.5,True):
        with pytest.raises(ValueError):
            ledger.allocate('x','GB',size)
    with pytest.raises(ValueError):
        ledger.allocate('x','missing',1)
    ledger.allocate('x','GB',1)
    with pytest.raises(ValueError):
        ledger.allocate('x','GB',1)
    ledger.observe('marker',resource='GB')
    assert ledger.events[-1]['known_live_bits'] == 1
    with pytest.raises(ValueError):
        ledger.observe('marker',resource='missing')


def phase(einsum, input_tensor, weight, output, reduction, output_rank):
    return Nested(nodes=[Reservation(purposes=[input_tensor],resource='GlobalBuffer'),
        Temporal(rank_variable=output_rank,tile_shape=4),
        Reservation(purposes=[weight],resource='GlobalBuffer'),
        Temporal(rank_variable='m',tile_shape=1),
        Reservation(purposes=[output],resource='GlobalBuffer'),
        Compute(einsum=einsum,component='MAC')])


def mapping():
    return Mapping(nodes=[Storage(tensors=['T1'],component='MainMemory'),Sequential(nodes=[
        phase('Matmul0','T0','W0','T1','n0','n1'),
        phase('Matmul1','T1','W1','T2','n1','n2')])])


def test_dense_tile_phase_occupancy_matches_explicit_tensor_index_sets():
    result = mapping_ledger(mapping(),4,8,544,contract=CONTRACT)
    assert result['status'] == 'phase_scopes_only'
    # Enumerate byte identities independently rather than using products.
    t0 = {(m,k) for m in range(4) for k in range(8)}
    w0 = {(k,n) for k in range(8) for n in range(4)}
    t1 = {(m,n) for m in range(1) for n in range(4)}
    expected = 8 * (len(t0)+len(w0)+len(t1))
    assert expected == 544 == result['phase_peak_bits']
    assert all(p['conditional_peak_bits']==expected for p in result['phases'])
    assert result['cut_free_capacity_bits'] is None
    assert result['cross_cut_physical_occupancy'] == 'unknown'
    assert result['boundary_event']['status'] == 'unknown'
    assert result['boundary_event']['globalbuffer_live_bits'] is None
    assert not result['safe_to_prune']
    assert result['phases'][0]['events'][-1]['known_live_bits'] == 0
    assert any(e['kind']=='representative_loop' for e in result['phases'][0]['events'])
    assert any(e['kind']=='representative_compute' for e in result['phases'][0]['events'])


def test_capacity_violation_and_unknown_cut_do_not_create_certificate():
    result = mapping_ledger(mapping(),4,8,543,contract=CONTRACT)
    assert result['phases'][0]['status_under_assumptions'] == 'exceeds'
    assert result['cut_free_capacity_bits'] is None and not result['safe_to_prune']


def test_repeated_reservations_and_spatial_replication_fail_closed():
    x = mapping().nodes[-1].nodes[0]
    x.nodes.insert(1,Reservation(purposes=['T0'],resource='GlobalBuffer'))
    with pytest.raises(UnsupportedLedger):
        phase_ledger(x,0,4,8,1000)
    x = mapping().nodes[-1].nodes[0]
    x.nodes.insert(0,Spatial(rank_variable='m',tile_shape=1,name='a',component='ArrayFanout'))
    with pytest.raises(UnsupportedLedger):
        phase_ledger(x,0,4,8,1000)


def test_imperfect_or_non_dividing_tile_fails_closed():
    x = mapping().nodes[-1].nodes[0]
    x.nodes[1].tile_shape = 3
    with pytest.raises(UnsupportedLedger):
        phase_ledger(x,0,4,8,1000)


def test_real_workload_model_contract_is_checked():
    from research.tracking_audit import common
    from research.tracking_audit.shape_capacity_audit import build
    spec = build(common.Case('matmuls','nvdla',(2,4,8)),(4,8),96,common.RU)
    assert validate_dense_contract(spec,4,8)['kind'] == 'two_dense_matmuls_8bit_unit_gb_scale'
    assert mapping_ledger(mapping(),4,8,544)['status'] == 'unsupported'
    with pytest.raises(UnsupportedLedger):
        validate_dense_contract(spec,8,8)
    spec.arch.find('GlobalBuffer').bits_per_value_scale = {'All':2}
    with pytest.raises(UnsupportedLedger):
        validate_dense_contract(spec,4,8)
