from fractions import Fraction
from itertools import product

from accelforge.mapper.FFM._join_pmappings.compatibility import Compatibility,TensorReservation,Loop
from accelforge.frontend.mapping import TilePattern
from accelforge.frontend.renames import Rank,TensorName
from accelforge.util import fzs
from research.diagnostics.pregen_certificates import (
    Bound,Facts,Relaxation,architecture_reasons,required_bits,largest_divisor,supports,
    reference_oracle_dominator,
)
from research.graph_coopt.template_support_audit import possible_interfaces


def comp(**backings):
    return Compatibility(tensors=fzs(TensorReservation((),TensorName(t),m)for t,m in backings.items()),
        reservation_indices=fzs([0]))


def test_duplicate_copy_bounds_do_not_add_and_stage_peaks_use_max():
    assert required_bits([('x',8),('x',12),('y',4)])==16
    a=Facts('a','A',Bound(100,8,Fraction(2),Fraction(3)))
    b=Facts('b','B',Bound(60,8,Fraction(4),Fraction(5)))
    graph=Relaxation([a,b],['A','B'],[])
    bound=graph.completion_bound({'a','b'})
    assert bound.gb_bits==100 and bound.energy==6 and bound.latency==8


def test_unknown_support_is_retained_not_rejected():
    assert supports(None,frozenset())
    a=Facts('a','A',Bound(),unknown='unsupported grammar')
    b=Facts('b','B',Bound(),compatibility=comp(x='GlobalBuffer'))
    graph=Relaxation([a,b],['A','B'],[('A','B','x')])
    assert graph.condition({'a','b'},'a')=={'a','b'}


def test_graph_can_reject_a_locally_feasible_but_unsupported_family():
    a=Facts('a','A',Bound(8,8),compatibility=comp(x='GlobalBuffer'))
    aa=Facts('aa','A',Bound(8,8),compatibility=comp(x='MainMemory'))
    b=Facts('b','B',Bound(8,8),compatibility=comp(x='MainMemory',y='GlobalBuffer'))
    c=Facts('c','C',Bound(8,8),compatibility=comp(y='GlobalBuffer'))
    assert not architecture_reasons(a,16,8,{})
    graph=Relaxation([a,aa,b,c],['A','B','C'],[('A','B','x'),('B','C','y')])
    assert not graph.condition({'a','aa','b','c'},'a')
    assert graph.condition({'a','aa','b','c'},'aa')=={'aa','b','c'}


def test_unit_loop_deletion_must_allow_different_raw_loop_counts():
    loop=Loop(Rank('M'),TilePattern(tile_shape='s',calculated_n_iterations='i'),False)
    one=Compatibility(tensors=fzs([TensorReservation((loop,),TensorName('x'),'GlobalBuffer')]),
        reservation_indices=fzs([1]))
    zero=comp(x='GlobalBuffer')
    assert possible_interfaces(one,['x']) & possible_interfaces(zero,['x'])


def test_spatial_capacity_is_hard_but_no_min_usage_fallback_is_assumed():
    f=Facts('a','A',Bound(8,8),spatial_min={('array','x'):4})
    assert architecture_reasons(f,8,8,{('array','x'):3})==['minimum_spatial_instances_exceed_fanout']
    assert architecture_reasons(f,8,8,{('array','x'):4})==[]
    assert architecture_reasons(f,7,8,{('array','x'):4})==['gb_lower_bound_exceeds_capacity']


def test_factor_bound_uses_extent_divisors_not_unused_physical_pes():
    assert largest_divisor(256,192)==128
    assert largest_divisor(256,384)==256
    assert largest_divisor(256,2)==2
    assert largest_divisor(15,4)==3


def test_every_explicit_legal_completion_survives_and_bounds_are_optimistic():
    # Independent small root-interface completion catalog, with nonnegative
    # extra completion costs; no search-generator or lineage labels involved.
    facts=[Facts('a','A',Bound(8,8,Fraction(1),Fraction(2)),compatibility=comp(x='GlobalBuffer')),
        Facts('aa','A',Bound(16,8,Fraction(2),Fraction(1)),compatibility=comp(x='MainMemory')),
        Facts('b','B',Bound(12,8,Fraction(3),Fraction(4)),compatibility=comp(x='GlobalBuffer')),
        Facts('bb','B',Bound(4,8,Fraction(5),Fraction(2)),compatibility=comp(x='MainMemory'))]
    graph=Relaxation(facts,['A','B'],[('A','B','x')])
    for left,right in product(facts[:2],facts[2:]):
        if left.compatibility.get_tensor_by_name('x').resource_name!=right.compatibility.get_tensor_by_name('x').resource_name:
            continue
        active=graph.condition(set(graph.facts),left.key)
        assert {left.key,right.key}<=active
        bound=graph.completion_bound(active)
        assert bound.gb_bits<=max(left.bound.gb_bits,right.bound.gb_bits)
        assert bound.energy<=left.bound.energy+right.bound.energy+1
        assert bound.latency<=left.bound.latency+right.bound.latency+1


def test_posthoc_incumbent_screen_requires_all_ru_coordinates_not_edp():
    f={'values':{'Total<SEP>energy':[1.], 'Total<SEP>latency':[1.],
        'reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right':[100],
        'reservation_bits<SEP>Register<SEP>0<SEP>right':[8]}}
    assert reference_oracle_dominator(Bound(99,8,Fraction(2),Fraction(2)),f)is None
    assert reference_oracle_dominator(Bound(100,8,Fraction(2),Fraction(2)),f)==0
