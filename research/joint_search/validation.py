"""Frozen reference backend, exact frontier comparison and source validation."""
from contextlib import ExitStack, nullcontext
from dataclasses import asdict
import json
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.enumeration_reuse import EnumerationReuse
from accelforge.mapper.FFM._pareto_df.capacity_membership import is_membership_col
from accelforge.mapper.FFM._pareto_df.df_convention import col_used_in_pareto
from accelforge.mapper.FFM._pareto_df.pareto import makepareto
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, mapping_structure, validate_pick
from .architecture_domain import Architecture, ArchitectureDomain
from .ffm_backend import tiles


def gate_domain():
    return ArchitectureDomain(tuple(Architecture(x,y,c) for x,y in ((8,32),(16,16),(32,8))
                                     for c in (4096,8192)))


def frontier(frame):
    """Complete E/T/exact-resource vector set; source metadata is separate.

    Shared catalogs retain extra provenance columns absent from an individual
    architecture. They are not optimization coordinates. Distinct mappings may
    tie on a frontier vector; all returned sources are validated separately.
    """
    columns = sorted(c for c in frame if c in ('Total<SEP>energy','Total<SEP>latency')
                     or c.startswith('reservation_bits<SEP>')
                     or (c.startswith('reservation<SEP>') and
                         c.replace('reservation<SEP>','reservation_bits<SEP>') not in frame))
    return frame[columns].drop_duplicates().sort_values(columns).reset_index(drop=True)


def compare(actual, expected):
    a,b=frontier(actual),frontier(expected)
    assert_frame_equal(a,b,check_exact=True)
    return dict(exact_full_etr_frontier=True, vectors=a.to_dict('records'),
                actual_source_rows=len(actual),reference_source_rows=len(expected))


def validate_sources(case, point, frame):
    records=[]
    for _,row in frame.iterrows():
        check=validate_pick(case,(point.px,point.py),point.capacity_bytes,row)
        if not check['ok']:
            raise AssertionError(f'source validation failed: {point}: {check}')
        records.append(check)
    return records


class CandidateTrace:
    """Compare pre-model policy Tile sets, not only terminal Pareto vectors."""
    def __init__(self, domain=None):
        self.domain=domain
        self.tables={}

    def capture(self, job, symbols, choices, excluded):
        key=json.dumps([job.einsum_name,mapping_structure(job.mapping),[str(s) for s in symbols]],sort_keys=True)
        if key in self.tables:
            raise AssertionError('ambiguous template identity')
        if self.domain is None:
            self.tables[key]=[tuple(v) for v in choices.tolist()]
        else:
            if excluded.words.shape[1] != 1:
                raise ValueError('one-word prototype trace required')
            words=excluded.words[:,0]
            self.tables[key]=[[tuple(v) for v in choices[((words>>np.uint64(i))&np.uint64(1)).astype(bool)].tolist()]
                              for i in range(len(self.domain.points))]

    def compare_point(self, native, index):
        if self.tables.keys()!=native.tables.keys():
            raise AssertionError('template catalogs differ')
        rows=0
        for key in self.tables:
            actual=set(self.tables[key][index]); expected=set(native.tables[key])
            if actual!=expected:
                raise AssertionError(f'policy Tile coverage differs: {key}: {len(actual)} != {len(expected)}')
            rows+=len(actual)
        return dict(exact_policy_tile_sets=True,templates=len(self.tables),selected_tile_rows=rows)


class WorkCounter:
    """Actual numeric work, with separate requested/avoided cache statistics."""
    def __init__(self, capture=None):
        self.capture=capture
        self.counts=dict(expansion_calls=0,expanded_rows=0,model_rows=0,
                         model_templates=0,join_pair_rows=0,largest_pair_frame=0)

    def __enter__(self):
        self.stack=ExitStack()
        expansion, enumeration, merge=tiles._compute_symbol_choices, tiles.get_tile_shape_choices_for_targets, pd.merge
        def expand(*args,**kwargs):
            result=expansion(*args,**kwargs)
            self.counts['expansion_calls']+=1
            self.counts['expanded_rows']+=len(result)
            return result
        def enumerate_tiles(**kwargs):
            result=enumeration(**kwargs)
            self.counts['model_rows']+=len(result[0]);self.counts['model_templates']+=1
            if self.capture is not None:
                self.capture(kwargs['job'],kwargs['symbols'],*result)
            return result
        def joined(*args,**kwargs):
            result=merge(*args,**kwargs)
            if tuple(kwargs.get('suffixes',()))==('', '_RIGHT_MERGE'):
                self.counts['join_pair_rows']+=len(result)
                self.counts['largest_pair_frame']=max(self.counts['largest_pair_frame'],len(result))
            return result
        self.stack.enter_context(patch.object(tiles,'_compute_symbol_choices',expand))
        self.stack.enter_context(patch.object(tiles,'get_tile_shape_choices_for_targets',enumerate_tiles))
        self.stack.enter_context(patch.object(pd,'merge',joined))
        return self

    def __exit__(self,*args):
        return self.stack.__exit__(*args)


def reference(case, domain, cached=False, trace=False):
    outputs,stats,traces={},{},{}
    with ExitStack() as stack:
        reuse=stack.enter_context(EnumerationReuse()) if cached else None
        for point in domain.points:
            capture=CandidateTrace() if trace else None
            with WorkCounter(capture.capture if capture else None) as counter:
                with reuse.target(point) if reuse else nullcontext():
                    result,timing=common.search(build(case,(point.px,point.py),point.capacity_bytes,common.RU))
            outputs[point]=result.data
            stats[point]=dict(**timing,work=counter.counts)
            if capture:
                traces[point]=capture
        cache_stats=dict(reuse.stats) if reuse else None
    return outputs,stats,traces,cache_stats


def capacity_events(case,domain):
    """Existing shared-capacity Event+Bitset search, cached across PE shapes."""
    outputs,stats={},[]
    shapes=sorted({(p.px,p.py) for p in domain.points})
    with EnumerationReuse() as reuse:
        for shape in shapes:
            points=[p for p in domain.points if (p.px,p.py)==shape]
            caps=[p.capacity_bytes for p in points]; largest=max(caps)
            env={'AF_TARGET_ENUMERATION':'events','AF_CAPACITY_MEMBERSHIP':'bitset',
                 'AF_GENERATION_CAPACITY_FRACTIONS':'GlobalBuffer:'+','.join(repr(c/largest)for c in caps),
                 'AF_GENERATION_CAPACITY_BITS':'GlobalBuffer:'+','.join(str(c*8)for c in caps)}
            with reuse.target(shape), WorkCounter() as counter:
                result,timing=common.search(build(case,shape,largest,common.RU),env)
                for point in points:
                    data=common.rows_for_capacity(result.data,point.capacity_bytes/2**20,largest/2**20).copy()
                    data=data.drop(columns=[c for c in data if is_membership_col(c)])
                    data['capacity_reference_bits<SEP>GlobalBuffer']=point.capacity_bytes*8
                    for c in data:
                        if c.startswith('reservation<SEP>GlobalBuffer<SEP>'):
                            data[c]=data[c.replace('reservation<SEP>','reservation_bits<SEP>')]/(point.capacity_bytes*8)
                    columns=[c for c in data.select_dtypes(include='number') if col_used_in_pareto(c)]
                    outputs[point]=makepareto(data,columns=columns)
            stats.append(dict(**timing,work=counter.counts))
        cache_stats=dict(reuse.stats)
    return outputs,stats,cache_stats


def audit(case=None, domain=None, validate_all=True):
    from .joint_optimizer import search_2mm
    case=case or common.Case('matmuls','nvdla',(2,16,16))
    domain=domain or gate_domain()
    trace=CandidateTrace(domain)
    actual,shared_stats=search_2mm(case,domain,capture=trace.capture)
    expected,baseline,traces,_=reference(case,domain,trace=True)
    points=[]
    for i,point in enumerate(domain.points):
        coverage=trace.compare_point(traces[point],i)
        quality=compare(actual[point],expected[point])
        source_ids=lambda frame: sorted(common.mapping_identity(row['Total<SEP>mapping']())
                                      for _,row in frame.iterrows())
        selected=actual[point] if validate_all else actual[point].iloc[:1]
        points.append(dict(architecture=asdict(point),coverage=coverage,quality=quality,
            actual_mapping_ids=source_ids(actual[point]),reference_mapping_ids=source_ids(expected[point]),
            validations=validate_sources(case,point,selected),reference_stats=baseline[point]))
    return dict(status='complete',case=str(case),points=points,shared_stats=shared_stats,
        consumer_requirements_enabled=False,architecture_family_certificate=False,
        full_physical_mapspace_optimality=False)


def main():
    import argparse,hashlib
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=audit()
    report['source_sha256']={str(p.relative_to(common.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in Path(__file__).parent.glob('*.py')}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],points=len(report['points']),
                         shared_stats=report['shared_stats'])))


if __name__=='__main__':
    main()
