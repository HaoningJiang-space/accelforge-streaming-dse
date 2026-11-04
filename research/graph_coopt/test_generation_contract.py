from accelforge.mapper.FFM.generation_contract import GenerationContract
from accelforge.mapper.FFM.pmappings import MultiEinsumPmappings


def test_combining_and_filtering_keeps_unknown_generation_provenance():
    def candidates(contracts):
        return MultiEinsumPmappings(spec=None, einsum2pmappings={}, pmapping_objects={},
            einsum2jobs={}, can_combine_multiple_runs=True, einsums_with_pmappings_generated=set(),
            flattened_arches={}, evaluated_specs={}, generation_contracts=contracts)
    known = GenerationContract('energy|latency', 0., (), 'bits')
    combined = candidates((known,)) | candidates(())
    assert combined.generation_contracts == (known, None)
    assert combined._filter(lambda group: True).generation_contracts == (known, None)
