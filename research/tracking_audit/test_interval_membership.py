import copy
from fractions import Fraction
import itertools
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ordered_fallback_regions import ordered_fallback_regions, fallback_oracle
from accelforge.mapper.FFM._pareto_df.capacity_membership import (
    pack_exclusions, encode_membership, expand_membership, membership_for_target, validate_membership,
)
from accelforge.mapper.FFM._pareto_df.interval_membership import (
    intervalize_columns, interval_to_words, is_interval_col, align_membership_frames, UPPER_COLUMN,
)
from accelforge.mapper.FFM._pareto_df.pareto import makepareto
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe


def test_fixed_candidate_theorem_exhaustive_small_universes():
    # 5,832 complete 3-candidate universes, two ordered fallback stages.
    attributes = list(itertools.product(range(3), repeat=2))
    for requirements in itertools.product((1, 2), repeat=3):
        for usages in itertools.product(attributes, repeat=3):
            regions = ordered_fallback_regions(requirements, usages, [2, 2])
            for c in range(4):
                actual = [i for i, region in enumerate(regions) if region and region.contains(c)]
                assert actual == fallback_oracle(requirements, usages, [2, 2], c)


def test_fixed_candidate_exact_bits_ties_and_unseen_queries():
    requirements = [65536, 65537, 128000, 65536]
    usages = [[Fraction(1,2)], [Fraction(3,4)], [1], [Fraction(1,2)]]
    regions = ordered_fallback_regions(requirements, usages, [1])
    for c in [0,65535,65536,65537,100000,127999,128000,2**70]:
        assert [i for i,r in enumerate(regions) if r and r.contains(c)] == fallback_oracle(requirements,usages,[1],c)
    assert regions[0] == regions[3]
    with pytest.raises(ValueError, match='integers'):
        ordered_fallback_regions([65536.], [[1]], [1])
    assert ordered_fallback_regions([], [], []) == []
    assert all(r.upper_bits is None for r in ordered_fallback_regions([1,2], [[],[]], []))


@pytest.mark.parametrize('k', [1,16,64,65,256,1024])
def test_interval_roundtrip_pareto_queries_and_empty_sets(k, monkeypatch):
    rng = np.random.default_rng(k)
    lower = rng.integers(0,k+1,80)
    upper = np.array([rng.integers(lo,k+1) for lo in lower])
    excluded = ~((lower[:,None] <= np.arange(k)) & (np.arange(k) < upper[:,None]))
    fractions = [(i+1)/k for i in range(k)]
    words = pack_exclusions('GlobalBuffer',fractions,excluded,len(excluded))
    intervals = intervalize_columns(words)
    assert intervals is not None
    costs = {'Total<SEP>energy': rng.integers(0,5,80).astype(np.float32),
             'Total<SEP>latency': rng.integers(0,5,80).astype(np.float32),
             'fused_loop<SEP>key': rng.integers(0,3,80), 'source': np.arange(80)}
    a,b = pd.DataFrame({**costs,**words}),pd.DataFrame({**costs,**intervals})
    a.index = b.index = [9]*80
    restored = interval_to_words(b)
    pd.testing.assert_frame_equal(restored[a.columns],a)
    pa,pb = expand_membership(makepareto(a)),expand_membership(makepareto(b))
    pd.testing.assert_frame_equal(pb[pa.columns],pa)
    for f in fractions:
        np.testing.assert_array_equal(membership_for_target(a,'GlobalBuffer',f), membership_for_target(b,'GlobalBuffer',f))
    with pytest.raises(ValueError, match='lacks membership'):
        membership_for_target(b,'GlobalBuffer',1e-9)
    bad = b.copy();bad[UPPER_COLUMN] = k+1
    with pytest.raises(ValueError): validate_membership(bad)


def test_holes_use_exact_bitsets_and_mixed_concat_falls_back(monkeypatch):
    monkeypatch.setenv('AF_CAPACITY_MEMBERSHIP','interval')
    fractions = [.25,.5,.75,1.]
    holes = np.array([[False,True,False,True],[True,False,True,False]])
    a = pd.DataFrame(encode_membership('GlobalBuffer',fractions,holes,2))
    b = pd.DataFrame(encode_membership('GlobalBuffer',fractions,np.zeros((2,4),dtype=bool),2))
    assert not any(is_interval_col(c) for c in a)
    assert any(is_interval_col(c) for c in b)
    a['Total<SEP>energy']=[1.,2.];b['Total<SEP>energy']=[3.,4.]
    result=PmappingDataframe.concat([PmappingDataframe(a,2,2),PmappingDataframe(b,2,2)]).data
    reference=makepareto(pd.concat([a,interval_to_words(b)],ignore_index=True))
    pd.testing.assert_frame_equal(result[reference.columns],reference)
    assert any(is_interval_col(c) for c in b)  # Alignment must not mutate parents.
    with pytest.raises(ValueError,match='different'):
        align_membership_frames([a,b.drop(columns=[c for c in b if is_interval_col(c)])])


def test_interval_empty_schema_malformed_bounds_and_unsupported_modes(monkeypatch):
    from accelforge.mapper.FFM._pareto_df import pareto
    words = pack_exclusions('GlobalBuffer',[.5,1.],None,0)
    empty = pd.DataFrame(intervalize_columns(words))
    pd.testing.assert_frame_equal(interval_to_words(empty),pd.DataFrame(words))
    frame = pd.DataFrame(intervalize_columns(pack_exclusions('GlobalBuffer',[.5,1.],None,2)))
    lo,hi = validate_membership(frame)
    bad = frame.copy();bad[hi]=np.array([3,2],dtype=np.uint32)
    with pytest.raises(ValueError,match='bounds'):validate_membership(bad)
    bad = frame.copy();bad[lo]=np.array([2,0],dtype=np.uint32)
    with pytest.raises(ValueError,match='bounds'):validate_membership(bad)
    different = pd.DataFrame(intervalize_columns(pack_exclusions('GlobalBuffer',[.25,1.],None,2)))
    with pytest.raises(ValueError,match='different'):align_membership_frames([frame,different])
    monkeypatch.setattr(pareto,'TOLERANCE',.01)
    frame['Total<SEP>energy']=[1.,2.]
    with pytest.raises(ValueError,match='zero'):pareto.makepareto(frame)


def test_interval_diagnostics_count_actual_intersections():
    from audit_membership_structure import interval_stats, trace_materialized_pairs
    # Two distinct nonempty intervals and an empty one: one of nine pairs lives.
    left = pd.DataFrame(intervalize_columns(pack_exclusions('GlobalBuffer',[.25,.5,.75,1.],
        np.array([[False,False,True,True],[True,True,False,False],[True]*4]),3)))
    right = pd.DataFrame(intervalize_columns(pack_exclusions('GlobalBuffer',[.25,.5,.75,1.],
        np.array([[True,False,True,True],[True]*4,[True]*4]),3)))
    assert interval_stats([left]) == interval_stats([interval_to_words(left)])
    with trace_materialized_pairs() as rows:
        pd.merge(left,right,how='cross',suffixes=['','_RIGHT_MERGE'])
    assert rows == [dict(matched_pairs=9,no_common_target=8)]


def test_interval_indices_follow_sorted_capacity_labels_not_input_order():
    fractions=[1.,.25,.75,.5]
    words=pack_exclusions('GlobalBuffer',fractions,np.array([[False,True,False,True]]),1)
    result=pd.DataFrame(intervalize_columns(words))
    lo,hi=validate_membership(result)
    assert result[lo].tolist()==[2] and result[hi].tolist()==[4]
    for f,allowed in [(1.,True),(.25,False),(.75,True),(.5,False)]:
        assert membership_for_target(result,'GlobalBuffer',f).tolist()==[allowed]


def test_ffm_partial_pareto_noncontiguous_membership_requires_bitset():
    from repro_noncontiguous_membership import reproduce
    report=reproduce()
    assert report['allowed']==[True,False,True]
    assert report['backend']=='bitset'
    assert report['actual_pareto_prefix_lengths']==[2]
    assert report['pareto_disabled_allowed']==[True,False,False]


@pytest.mark.parametrize('mixed', [False,True])
@pytest.mark.parametrize('streaming,early', [('0','late'),('16','late'),('16','early')])
def test_real_join_interval_and_mixed_fallback(monkeypatch,mixed,streaming,early):
    path=Path(__file__).parents[1]/'streaming_join/fixtures/real_join_large_tag1.pkl'
    with path.open('rb') as handle:left,right,args,kwargs=copy.deepcopy(pickle.load(handle))
    left._data=left.data.iloc[:96].copy()
    fractions=[(i+1)/65 for i in range(65)]
    for side in (left,right):
        n=len(side.data);excluded=np.ones((n,65),dtype=bool)
        for i in range(n):excluded[i, (i%2)*32:(i%2)*32+20]=False
        if mixed and side is right:excluded[0,64]=False
        words=pack_exclusions('GlobalBuffer',fractions,excluded,n)
        for c,v in words.items():side._data[c]=v
    def run(intervals):
        a,b=copy.deepcopy((left,right))
        if intervals:
            for side in (a,b):
                words={c:side.data[c].to_numpy() for c in validate_membership(side.data)}
                codec=intervalize_columns(words)
                if codec is not None:
                    side._data=side.data.drop(columns=list(words)).assign(**codec)
        return a.merge_next(b,*args,**kwargs).data
    monkeypatch.setenv('AF_STREAMING_JOIN_PAIRS',streaming)
    monkeypatch.setenv('AF_MEMBERSHIP_JOIN',early)
    monkeypatch.setenv('AF_PARTITIONED_FRONTIER','1')
    a,b=expand_membership(run(False)),expand_membership(run(True))
    pd.testing.assert_frame_equal(b[a.columns].reset_index(drop=True),a.reset_index(drop=True))
