from itertools import product
import pytest

from research.diagnostics.scoped_resource_effect import compile_closed,concrete_oracle,Unsupported,namespaced,chain_root_max

L='reservation<SEP>GlobalBuffer<SEP>1<SEP>left'
X='reservation<SEP>GlobalBuffer<SEP>0<SEP>right'
Y='reservation<SEP>GlobalBuffer<SEP>1<SEP>right'


def test_effect_matches_independent_scalar_and_explicit_formula_on_all_small_nested_inputs():
    effect=compile_closed({L:7},(X,Y),[(L,X)])
    for x,y in product(range(8),repeat=2):
        if x>y:continue
        answer=effect.evaluate({X:x,Y:y})
        assert answer=={X:max(7+x,y)}
        assert answer==concrete_oracle({L:7},{X:x,Y:y},[(L,X)])


def test_real_scope_witness_is_116_kib_not_max_local_100_kib():
    effect=compile_closed({L:52*1024*8},(X,Y),[(L,X)])
    assert effect.evaluate({X:64*1024*8,Y:100*1024*8})[X]==116*1024*8


def test_capacity_is_a_query_not_embedded_in_resource_function():
    # Same effect and correlated plan cost can be queried at both capacities.
    effect=compile_closed({L:68*1024*8},(X,Y),[(L,X)])
    peak=effect.evaluate({X:64*1024*8,Y:100*1024*8})[X]
    assert peak==132*1024*8
    assert not peak<=128*1024*8
    assert peak<=132*1024*8


def test_duplicate_consumer_column_uses_right_operand_exactly_once():
    operations=[(X,X+'_RIGHT_MERGE')]
    effect=compile_closed({X:3},(X,),operations)
    assert effect.evaluate({X:5})=={X:8}
    assert effect.evaluate({X:5})==concrete_oracle({X:3},{X:5},operations)


def test_signed_persistent_and_non_nested_inputs_are_not_supported():
    with pytest.raises(Unsupported):compile_closed({L:-1},(X,Y),[(L,X)])
    with pytest.raises(Unsupported):compile_closed({'reservation<SEP>GlobalBuffer<SEP>-1<SEP>right':8},(X,),[])
    effect=compile_closed({L:7},(X,Y),[(L,X)])
    with pytest.raises(Unsupported):effect.evaluate({X:8,Y:7})


def test_all_six_archived_fixed_plans_and_both_capacity_queries_match():
    from research.diagnostics.counterfactual_trace import archived_effects
    result=archived_effects()
    assert result['native_transfer_checks']==12
    assert len(result['fixed_plan_records'])==6
    for plan in result['fixed_plan_records']:
        if plan['source_capacity']==135168:
            assert not plan['fits_128'] and plan['fits_132']
        else:
            assert plan['fits_128'] and plan['fits_132']
    assert sorted(map(len,result['full_fixed_library_frontiers'].values()))==[1,1,1,2,2,2]


def test_composed_root_barrier_matches_independent_sequential_integer_execution():
    first=namespaced(compile_closed({L:7},(X,Y),[(L,X)]),'B')
    whole=chain_root_max(first,(X,),'C')
    for x,y,z in product(range(5),repeat=3):
        if x>y:continue
        prefix=concrete_oracle({L:7},{X:x,Y:y},[(L,X)])
        root_left={'reservation<SEP>GlobalBuffer<SEP>0<SEP>left':prefix[X]}
        expected=concrete_oracle(root_left,{X:z},[])
        assert whole.evaluate({'B::'+X:x,'B::'+Y:y,'C::'+X:z})==expected
