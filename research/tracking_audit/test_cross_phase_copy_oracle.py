import pytest

from research.tracking_audit.cross_phase_copy_oracle import CopyWitness, compare_main_actions, make_witness


@pytest.mark.parametrize('location', ['GlobalBuffer','MainMemory'])
def test_element_witness_has_full_final_live_set_and_explicit_copy_id(location):
    result = make_witness(4,8,location,capture_events=True)
    assert result['elements'] == 32
    assert result['minimum_hypothetical_writes_bits'] == 256
    assert result['minimum_hypothetical_reads_bits'] == 256
    assert result['physical_copy_identity'] == 'unproved'
    assert result['identity_weight_functional_check']
    assert result['cut_occupancy'] == 'unknown' and not result['safe_to_prune']
    barrier = next(x for x in result['events'] if x['kind']=='logical_barrier')
    assert barrier['live_values']==32 and barrier['physical_copy_validity']=='assumed'
    writes = [tuple(x['index']) for x in result['events'] if x['kind']=='write_hypothetical_copy']
    reads = [tuple(x['index']) for x in result['events'] if x['kind']=='read_hypothetical_copy']
    assert set(writes) == set(reads) == {(i,j) for i in range(4) for j in range(8)}
    written = {tuple(x['index']):x['value'] for x in result['events'] if x['kind']=='write_hypothetical_copy'}
    read = {tuple(x['index']):x['value'] for x in result['events'] if x['kind']=='read_hypothetical_copy'}
    assert written == read


def test_missing_copy_and_stale_version_are_rejected():
    oracle = CopyWitness(1,1,'MainMemory')
    oracle.create_copy('x','MainMemory')
    with pytest.raises(ValueError):
        oracle.write('x',(0,0),None)
    with pytest.raises(ValueError):
        oracle.barrier()
    oracle.produce((0,0),'final')
    with pytest.raises(ValueError):
        oracle.barrier()
    oracle.write('x',(0,0),'final')
    oracle.barrier()
    with pytest.raises(ValueError):
        oracle.read('x',(0,0),'partial')
    with pytest.raises(ValueError):
        oracle.finish()
    oracle.read('x',(0,0),'final')
    with pytest.raises(ValueError):
        oracle.read('x',(0,0),'final')
    assert oracle.finish()['elements'] == 1


def test_copy_declarations_are_not_observed_physical_copies():
    oracle = CopyWitness(1,1,'GlobalBuffer')
    with pytest.raises(ValueError):
        oracle.create_copy('x','MainMemory')
    oracle.create_copy('x','GlobalBuffer')
    with pytest.raises(ValueError):
        oracle.create_copy('y','GlobalBuffer')


def test_recorded_dram_actions_are_not_counted_again_as_extra_spill():
    witness = make_witness(4,8,'MainMemory')
    actions = {'Matmul0<SEP>action<SEP>MainMemory<SEP>T1<SEP>write':256.,
               'Matmul1<SEP>action<SEP>MainMemory<SEP>T1<SEP>read':512.}
    result = compare_main_actions(witness,actions)
    assert result['counts_are_consistent']
    assert result['additional_lower_bound_proved_bits'] == 0
    actions['Matmul0<SEP>action<SEP>MainMemory<SEP>T1<SEP>write'] = 248.
    assert not compare_main_actions(witness,actions)['counts_are_consistent']


def test_globalbuffer_witness_does_not_forbid_additional_mainmemory_copies():
    witness = make_witness(4,8,'GlobalBuffer')
    result = compare_main_actions(witness,{'Matmul0<SEP>action<SEP>MainMemory<SEP>T1<SEP>write':256.})
    assert result['counts_are_consistent']
    assert result['conditional_min_write_bits'] == 0


def test_archived_real_mappings_keep_instances_unique_ids_and_unknowns_distinct(tmp_path):
    import json
    from research.tracking_audit.audit_cross_phase_copy import run
    out = tmp_path/'audit.json'
    run(out)
    result = json.loads(out.read_text())
    assert result['validation_complete'] and len(result['rows']) == 27
    assert result['unique_mapping_ids'] == 18 and len(result['skipped']) == 7
    assert all(not row['declaration_implies_physical_copy'] for row in result['rows'])
    assert all(not row['witness']['safe_to_prune'] for row in result['rows'])
    samples = [row for row in result['rows'] if row['witness']['events'] is not None]
    assert {(x['capacity_bytes'],x['index'],x['declared_storage_location']) for x in samples} == {
        (96,0,'MainMemory'), (96,3,'GlobalBuffer')}
