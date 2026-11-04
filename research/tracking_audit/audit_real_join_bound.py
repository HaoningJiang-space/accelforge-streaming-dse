"""Retrospective best-EDP bounds for actual final FFM Join groups.

This first observes the original full Join, then runs an experimental Join
using an oracle-derived incumbent to skip selected pair materializations. It
is not a graph-specific lower bound or an end-to-end speed benchmark.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
from unittest.mock import patch

import numpy as np

from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, validate_pick

ENERGY = 'Total<SEP>energy'
LATENCY = 'Total<SEP>latency'


def downward_float32(value):
    """Conservative nonnegative float32 lower bound on a finite input float."""
    if not math.isfinite(value) or value < 0:
        raise ValueError('requires finite nonnegative objectives')
    with np.errstate(over='ignore',under='ignore',invalid='ignore'):
        v = np.float32(value)
        if not np.isfinite(v):
            raise ValueError('float32 overflow')
        return max(0., float(np.nextafter(v, np.float32(-np.inf))))


def downward_sum(left, right):
    """Lower than real sum and its nonnegative float32/float64 rounded sum."""
    a,b = downward_float32(left),downward_float32(right)
    with np.errstate(over='ignore',under='ignore',invalid='ignore'):
        total = np.float32(a) + np.float32(b)
    if not np.isfinite(total):
        raise ValueError('float32 sum overflow')
    return max(0.,float(np.nextafter(total, np.float32(-np.inf))))


def group_bound(left, right):
    """Bound EDP of any nonnegative pair under additive E and T Join."""
    vals = []
    for col in (ENERGY,LATENCY):
        for frame in (left,right):
            if col not in frame or len(frame)==0 or frame[col].dtype not in (np.dtype('float32'),np.dtype('float64')):
                raise ValueError('missing, empty or unsupported objective column')
            x = frame[col].to_numpy()
            if not np.isfinite(x).all() or (x<0).any():
                raise ValueError('nonfinite or negative objective')
        vals.append(downward_sum(float(left[col].min()),float(right[col].min())))
    return Fraction.from_float(vals[0])*Fraction.from_float(vals[1])


def run(output):
    common.af.set_n_parallel_jobs(1)
    common.clear_switches()
    case = common.Case('matmuls','nvdla',(2,4,8))
    shape,capacity = (4,8),96
    metrics = common.RU | common.af.Metrics.ACTIONS
    baseline,_ = common.search(build(case,shape,capacity,metrics))
    row = common.best_row(baseline.data)
    if row is None:
        raise ValueError('no executable incumbent')
    validation = validate_pick(case,shape,capacity,row)
    if not validation['ok']:
        raise ValueError('incumbent did not re-evaluate')
    upper = Fraction.from_float(float(row[ENERGY]))*Fraction.from_float(float(row[LATENCY]))
    records=[]
    original = PmappingDataframe.merge_next
    def observe(self,right,*args,**kwargs):
        record = dict(left_rows=len(self.data),right_rows=len(right.data),bound=None,matched_pairs=None)
        try:
            lower = group_bound(self.data,right.data)
            record['bound'] = str(lower)
            plan = self._matching_pair_plan(right,kwargs['compatibility_left'],kwargs['compatibility_right'])
            if plan is not None:
                record['matched_pairs'] = sum(len(a)*len(b) for a,b in plan)
            record['strictly_above_incumbent'] = lower > upper
        except (KeyError,TypeError,ValueError) as e:
            record['unsupported'] = str(e)
        # Always execute the real Join, even if the lower bound is decisive.
        result = original(self,right,*args,**kwargs)
        record['result_rows'] = len(result.data)
        if record['bound'] is not None:
            bound = Fraction(record['bound'])
            record['all_retained_rows_respect_bound'] = all(
                Fraction.from_float(float(e))*Fraction.from_float(float(t)) >= bound
                for e,t in zip(result.data[ENERGY],result.data[LATENCY]))
            if not record['all_retained_rows_respect_bound']:
                raise AssertionError('observed Join output violated the proposed lower bound')
        records.append(record)
        return result
    with patch.object(PmappingDataframe,'merge_next',observe):
        observed,_ = common.search(build(case,shape,capacity,metrics))
    if common.best_row(observed.data) is None:
        raise AssertionError('instrumented reference returned no rows')
    observed_best = common.best_row(observed.data)
    observed_cost = Fraction.from_float(float(observed_best[ENERGY]))*Fraction.from_float(float(observed_best[LATENCY]))
    if observed_cost != upper:
        raise AssertionError('instrumentation changed the best reported FFM EDP')
    skipped = [r for r in records if r.get('strictly_above_incumbent')]
    actual_skips = []
    def prune(self,right,*args,**kwargs):
        try:
            bound = group_bound(self.data,right.data)
        except (KeyError,TypeError,ValueError):
            return original(self,right,*args,**kwargs)
        if bound <= upper:
            return original(self,right,*args,**kwargs)
        # Execute the original schema/resource pipeline on an empty left input.
        # No matching pairs from this group are materialized. This experimental
        # wrapper is restricted to the last Join of the two-operator workload.
        actual_skips.append(dict(left_rows=len(self.data),right_rows=len(right.data),bound=str(bound)))
        empty = self.update(data=self.data.iloc[:0].copy(),skip_pareto=True)
        return original(empty,right,*args,**kwargs)
    with patch.object(PmappingDataframe,'merge_next',prune):
        pruned,_ = common.search(build(case,shape,capacity,metrics))
    pruned_row = common.best_row(pruned.data)
    if pruned_row is None:
        raise AssertionError('experimental pruning returned no rows')
    pruned_cost = Fraction.from_float(float(pruned_row[ENERGY]))*Fraction.from_float(float(pruned_row[LATENCY]))
    pruned_validation = validate_pick(case,shape,capacity,pruned_row)
    if pruned_cost != upper or not pruned_validation['ok']:
        raise AssertionError('experimental pruning changed the target best EDP or reconstruction')
    root = Path(__file__).parent
    paths = [Path(__file__),root/'shape_capacity_audit.py',common.ROOT/'accelforge/mapper/FFM/_join_pmappings/pmapping_dataframe.py',
             common.ROOT/'accelforge/mapper/FFM/_pareto_df/df_convention.py']
    report = dict(scope='oracle-incumbent final-Join experiment; no graph-bound or runtime comparison',
        case=str(case),shape=shape,capacity_bytes=capacity,incumbent_reported_edp=str(upper),
        incumbent_validation=validation,records=records,
        groups=len(records),hypothetically_prunable_groups=len(skipped),
        actual_pruned_groups=actual_skips,actual_pruned_best_edp=str(pruned_cost),
        actual_pruned_validation=pruned_validation,
        hypothetically_prunable_matched_pairs=sum(r['matched_pairs'] for r in skipped if r['matched_pairs'] is not None),
        all_skipped_pair_counts_known=all(r['matched_pairs'] is not None for r in skipped),
        all_retained_rows_respect_bound=all(r.get('all_retained_rows_respect_bound',True) for r in records),
        source_sha256={str(p.relative_to(common.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('groups','hypothetically_prunable_groups',
                                           'hypothetically_prunable_matched_pairs','all_retained_rows_respect_bound')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output)
