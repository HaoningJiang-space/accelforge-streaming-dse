"""Prepared/cached FFM versus all-template family compilation, in separate processes."""
import argparse
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
from unittest.mock import patch

import numpy as np

from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.enumeration_reuse import EnumerationReuse
from research.tracking_audit import parametric_operator as p

b = p.b
FAMILY = p.Box(((8,128),(16,384),(32768,262144)))
RAW_GB = 'reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right'


def query_points(count,seed=731):
    points = [(48,128,135168),(24,256,131072),(96,64,65536),(40,160,98304)]
    rng = np.random.default_rng(seed)
    while len(points)<count:
        point = tuple(int(rng.integers(lo,hi+1)) for lo,hi in FAMILY.ranges)
        if point not in points:
            points.append(point)
    return points[:count]


def evaluation_key(job):
    return hashlib.sha256(json.dumps(b.mapping_structure(job.mapping),sort_keys=True).encode()).hexdigest()


def fingerprint(choices,symbols):
    choices = b.canonical_choices(choices)
    header = json.dumps(dict(shape=choices.shape,dtype=choices.dtype.str,symbols=list(map(str,symbols))))
    return dict(rows=len(choices),sha256=hashlib.sha256(header.encode()+choices.tobytes()).hexdigest())


def candidate_records(programs,choices):
    return {evaluation_key(program.kwargs['job']):fingerprint(rows,program.kwargs['symbols'])
            for program,rows in zip(programs,choices)}


def independent_query(programs,point):
    choices,parts = [],[]
    work = dict(state_expansion_requests=0,expanded_row_requests=0,cost_rows=0)
    for program in programs:
        rows,counts = b.oracle(program,b.instantiate_objectives(program,point))
        choices.append(rows)
        parts.append(b.selected_costs(program,rows))
        work['state_expansion_requests'] += counts['state_expansions']
        work['expanded_row_requests'] += counts['expanded_rows']
        work['cost_rows'] += len(rows)
    costs = np.concatenate(parts)
    front = b.frontier(costs)
    if not len(costs):
        return front,None,choices,work
    best = int(np.argmin(costs[:,0]*costs[:,1]))
    offset = 0
    for program,rows,part in zip(programs,choices,parts):
        if offset <= best < offset+len(rows):
            i = best-offset
            return front,b.reconstruct_best(program,rows[i:i+1],part[i:i+1]),choices,work
        offset += len(rows)
    raise AssertionError('lost source mapping')


def physical_query(size,point):
    """Unmodified full FFM path; intercept enumeration only to audit coverage."""
    case = b.common.Case('matmuls','nvdla',(1,size,size))
    spec = b.build(case,point[:2],point[2],b.common.RU)
    original = b.tiles.get_tile_shape_choices_for_targets
    candidates = {}
    def observe(*args,**kwargs):
        key = evaluation_key(kwargs['job'])
        result = original(*args,**kwargs)
        if key in candidates:
            raise AssertionError('ambiguous template evaluation identity')
        candidates[key] = fingerprint(result[0],kwargs['symbols'])
        return result
    with patch.object(b.tiles,'get_tile_shape_choices_for_targets',observe):
        result,stats = b.common.search(spec)
    data = result.data
    front = b.frontier(data[[b.E,b.L,RAW_GB]].to_numpy())
    if not len(data):
        return front,None,candidates,stats
    values = data[[b.E,b.L]].to_numpy(dtype=np.float64)
    row = data.iloc[int(np.argmin(values[:,0]*values[:,1]))]
    mapping = row['Total<SEP>mapping']()
    pick = {b.E:row[b.E],b.L:row[b.L],'raw_gb_bits':int(row[RAW_GB]),'Total<SEP>mapping':lambda:mapping}
    return front,pick,candidates,stats


def sources():
    files = [Path(__file__),Path(p.__file__),Path(b.__file__),Path(__file__).with_name('parametric_template.py')]
    return {x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in files}


def run(args):
    if args.queries<1:
        raise ValueError('queries must be positive')
    b.common.af.set_n_parallel_jobs(1)
    b.common.clear_switches()
    case = b.common.Case('matmuls','nvdla',(1,args.size,args.size))
    report = dict(config=b.common.effective_config(case),mode=args.mode,family=FAMILY.ranges,
                  size=args.size,seed=args.seed,source_sha256=sources(),queries=[],
                  environment=dict(python=sys.version,platform=platform.platform(),workers=1))
    # All three methods receive the same generic JIT warmup, before timing.
    b.frontier(np.array([[1.,2.,3.],[2.,1.,2.]]))
    t0 = time.perf_counter()
    programs = p.prepare_all(args.size,tuple(hi for lo,hi in FAMILY.ranges))
    prepare_s = time.perf_counter()-t0
    if len(programs)!=6:
        raise ValueError('expected all six MatMul templates for this experiment')
    compiled,compile_s = None,0.
    if args.mode=='regions':
        t0 = time.perf_counter()
        compiled = p.CompiledOperator(programs,FAMILY)
        compile_s = time.perf_counter()-t0
        report['compilation'] = compiled.stats
        report['regions'] = [dict(boxes=[box.ranges for box in r.boxes],ids=r.ids.tolist(),
                                  frontier=compiled.costs[r.ids].tolist()) for r in compiled.regions]
    report.update(prepare_s=prepare_s,compile_s=compile_s,preprocess_s=prepare_s+compile_s,
                  template_ids=[hashlib.sha256(x.template_key.encode()).hexdigest() for x in programs])
    b.save(args.output,report)
    # Concrete query points first exist after compilation/preparation completes.
    points = query_points(args.queries,args.seed)
    pending,total = [],0.
    context = EnumerationReuse() if args.mode=='cached' else nullcontext()
    with context as reuse:
        for point in points:
            target = reuse.target(point) if reuse else nullcontext()
            with target:
                t0 = time.perf_counter()
                if compiled:
                    front,ids = compiled.query(point)
                    pick = compiled.best_mapping(point)
                    work = {}
                else:
                    front,pick,choices,work = independent_query(programs,point)
                query_s = time.perf_counter()-t0
            total += query_s
            # Coverage diagnostics, serialization and evaluation are outside
            # timers. No physical oracle warms any timed query in this process.
            if compiled:
                choices = [t.query(point)[0] for t in compiled.templates]
            records = candidate_records(programs,choices)
            report['queries'].append(dict(point=point,query_s=query_s,cumulative_s=prepare_s+compile_s+total,
                frontier=front.tolist(),candidates=records,work=work))
            pending.append(pick)
            b.save(args.output,report)
        if reuse:
            report['cache_work'] = dict(reuse.stats)
    report['total_s'] = prepare_s+compile_s+total
    report['search_peak_rss_gib'] = b.common.peak_rss_gb()['main']
    b.save(args.output,report)
    # Re-evaluate every selected source only after all timing and cache scopes.
    for record,pick in zip(report['queries'],pending):
        record['validation'] = b.validate_selected(case,tuple(record['point']),pick)
        b.save(args.output,report)
    report['all_picks_valid'] = all(q['validation']['ok'] for q in report['queries'])
    b.save(args.output,report)
    print(json.dumps(dict(mode=args.mode,preprocess_s=report['preprocess_s'],total_s=report['total_s'],
                         queries=len(points),all_picks_valid=report['all_picks_valid'])),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('regions','independent','cached'),required=True)
    parser.add_argument('--size',type=int,default=256)
    parser.add_argument('--queries',type=int,default=256)
    parser.add_argument('--seed',type=int,default=731)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args())
