import copy
import importlib
import json
import math

import pytest

from research.diagnostics.causal_3mm import (SOURCE,restore,replay,phase_materialized_intermediates,
    common,mapping_structure)


def picks():return json.loads(SOURCE.read_text())['runs'][0]['picks']


def test_all_six_archived_structures_restore_without_mapping_identity_changes():
    for p in picks():
        mapping=restore(p['mapping'])
        assert common.mapping_identity(mapping)==p['mapping_id']
        assert mapping_structure(mapping)==p['mapping']
    malformed=copy.deepcopy(picks()[0]['mapping']);malformed['unrecorded']=1
    with pytest.raises(ValueError):restore(malformed)


def test_132_kib_threshold_has_actual_two_full_intermediates_plus_weight_tile():
    common.af.set_n_parallel_jobs(1)
    p=picks()[3];mapping=restore(p['mapping'])
    module=importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.run_model')
    original=module.run_model
    high=replay(mapping,p['shape'],135168);low=replay(mapping,p['shape'],131072)
    assert high['feasible'] and not low['feasible']
    assert low['excess_phase_bits']==4096*8
    phase=next(x for x in high['phases']if x['einsum']=='Matmul1')
    assert {x['tensor']:x['bits']//8 for x in phase['tensors']}=={'T1':65536,'T2':65536,'W1':4096}
    assert high['globalbuffer_peak_bits']==phase['phase_peak_bits']==135168*8
    assert math.isclose(high['energy_j'],p['energy'],rel_tol=1e-6)
    just_below=replay(mapping,p['shape'],135167)
    assert not just_below['feasible'] and just_below['excess_phase_bits']==8
    assert module.run_model is original


def test_fused_join_carries_future_t2_reservation_beyond_individual_phase_maximum():
    common.af.set_n_parallel_jobs(1);p=picks()[4]
    result=replay(restore(p['mapping']),p['shape'],131072)
    assert result['feasible'] and result['maximum_phase_reservation_bits']==102400*8
    assert result['globalbuffer_peak_bits']==118784*8
    join=result['join_resource_transfers'][0]
    assert join['left_before']['columns']['reservation<SEP>GlobalBuffer<SEP>1<SEP>right']==[53248*8]
    assert join['right_before']['columns']['reservation<SEP>GlobalBuffer<SEP>0<SEP>right']==[65536*8]
    assert join['result']['columns']['reservation<SEP>GlobalBuffer<SEP>0<SEP>right']==[(53248+65536)*8]
    assert not result['independent_physical_lifetime_validation']


def test_fixed_residency_control_preserves_loops_and_adds_two_full_dram_roundtrips():
    common.af.set_n_parallel_jobs(1);p=picks()[3];mapping=restore(p['mapping'])
    controlled=phase_materialized_intermediates(mapping)
    def loops(n):
        return ([{k:v for k,v in n.items()if k!='nodes'}]if n['type']in ('Temporal','Spatial')else [])+[
            x for child in n.get('nodes',[])for x in loops(child)]
    assert loops(mapping_structure(controlled))==loops(p['mapping'])
    result=replay(controlled,p['shape'],135168)
    assert result['feasible'] and result['globalbuffer_peak_bits']==135168*8
    traffic=sum(v for k,v in result['actions'].items()if '<SEP>MainMemory<SEP>'in k and
                any('<SEP>'+t+'<SEP>'in k for t in ('T1','T2')))
    assert traffic==4*65536*8
    assert math.isclose(result['latency_s'],15.36e-6,rel_tol=1e-12)
    with pytest.raises(ValueError):phase_materialized_intermediates(restore(picks()[4]['mapping']))
