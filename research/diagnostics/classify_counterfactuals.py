"""Classify evidence, not universal causes, in an already completed native trace."""
import argparse
from collections import Counter,defaultdict
import gzip
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from accelforge.mapper.FFM._pareto_df.capacity_membership import membership_for_target
from research.diagnostics.scoped_resource_effect import parse
from research.tracking_audit import common

COSTS=('Total<SEP>energy','Total<SEP>latency')
GB='reservation<SEP>GlobalBuffer<SEP>0<SEP>right'
REG='reservation<SEP>Register<SEP>0<SEP>right'


def restore(record):
    frame=pd.DataFrame(record['columns'],index=record['index'])
    return frame.astype(record['dtypes'])


def strict_front(vectors,block=128):
    """Independent strict dominance, retaining every numeric tie/source."""
    v=np.asarray(vectors)
    keep=np.ones(len(v),dtype=bool)
    for start in range(0,len(v),block):
        q=v[start:start+block]
        no_worse=(v[None,:,:]<=q[:,None,:]).all(axis=2)
        better=(v[None,:,:]<q[:,None,:]).any(axis=2)
        keep[start:start+len(q)]=~(no_worse & better).any(axis=1)
    return keep


def vectors(frame,public=False):
    resource=lambda c:c.replace('reservation<SEP>','reservation_bits<SEP>')if public else c
    cols=[*COSTS,resource(GB),resource(REG)]
    for c in cols[2:]:
        if (frame[c]>2**53).any():raise ValueError('mixed vector would lose exact integer bits')
    return frame[cols].to_numpy(dtype='float64')


def separated_costs(q1,p1,q2,p2):
    """Diagnostic margin filter, not a new pruning theorem or certificate."""
    return any(min(q1[d]-p1[d],q2[d]-p2[d])>8*np.finfo(np.float32).eps*
        max(q1[d],p1[d],q2[d],p2[d])for d in (0,1))


def classify(raw,g1):
    started=time.perf_counter()
    old={(t['target'],t['einsum'],t['template']):t for t in g1['tasks']}
    current={t['id']:t for t in raw['provenance']['tasks']}
    task_map={t['id']:old[(t['target'],t['einsum'],t['template'])]['id']for t in current.values()}
    old_by_id={t['id']:t for t in g1['tasks']}
    origins={(r['target'],r['einsum'],r['compressed_index']):r for r in raw['provenance']['compressed_local_rows']}
    interesting={t['id']for t in g1['tasks']if t['observed_stage_class']=='join_rows_no_final_descendant'}
    if len(interesting)!=54:raise AssertionError('unexpected frozen G1 cohort')
    stats={k:dict(task_id=k,shape_target=old_by_id[k]['target'],einsum=old_by_id[k]['einsum'],
        local_row_occurrences=0,local_sufficiently_covered_rows=0,
        matched_pair_occurrences=0,prefix_return_occurrences=0,
        terminal_target_completion_occurrences=0,strict_global_dominance_occurrences=0,
        equal_final_point_occurrences=0,consumer_conditioned_front_occurrences=0,
        consumer_conditioned_but_globally_strict_occurrences=0,
        nontrivial_conditioning_contrast_occurrences=0,resource_context_reversal_witnesses=0,
        margin_separated_resource_reversal_witnesses=0,examples={})for k in interesting}
    def job(target,column,index):
        e=column.split('<SEP>')[0]
        return task_map[origins[(target,e,int(index))]['task_id']]
    def row_jobs(target,frame,position):
        return [job(target,c,frame[c].iloc[position])for c in frame if c.endswith('<SEP>compressed_index')]
    # Conservative, sufficient local numerical substitution: same complete
    # non-cost/non-source transition state, and no worse E/T, in one group.
    for group in raw['local_groups']:
        frame=restore(group['frame']);target=group['target']
        source=group['einsum']+'<SEP>compressed_index'
        requirements=sorted(c for c in frame if c not in COSTS and c!=source)
        equal=defaultdict(list)
        for i in range(len(frame)):
            equal[tuple(frame[c].iloc[i].item()for c in requirements)].append(i)
        for rows in equal.values():
            for q in rows:
                qjob=job(target,source,frame[source].iloc[q])
                if qjob not in interesting:continue
                stats[qjob]['local_row_occurrences']+=1
                witness=next((p for p in rows if job(target,source,frame[source].iloc[p])!=qjob and
                    all(frame[c].iloc[p]<=frame[c].iloc[q]for c in COSTS)),None)
                if witness is not None:
                    stats[qjob]['local_sufficiently_covered_rows']+=1
                    stats[qjob]['examples'].setdefault('local_numerical_replacement',dict(
                        group=group['group'],removed=int(frame[source].iloc[q]),kept=int(frame[source].iloc[witness])))
    terminal=defaultdict(list)
    for bucket in raw['buckets']:
        target=bucket['target']
        if 'matched'in bucket:
            matched=restore(bucket['matched'])
            for i in range(len(matched)):
                for k in row_jobs(target,matched,i):
                    if k in interesting:stats[k]['matched_pair_occurrences']+=1
        returned=restore(bucket['returned'])
        if len([c for c in returned if c.endswith('<SEP>compressed_index')])==2:
            for i in range(len(returned)):
                for k in row_jobs(target,returned,i):
                    if k in interesting:stats[k]['prefix_return_occurrences']+=1
        if 'terminal_pool'in bucket:
            pool=restore(bucket['terminal_pool']);pool['_bucket']=bucket['id']
            terminal[target].append(pool)
    point_results={};reversal_examples=[]
    for point,final_record in raw['final_target_rows'].items():
        x,y,cap=map(int,point.split(','));target=repr(((x,y),(131072,135168)))
        pool=pd.concat(terminal[target],ignore_index=True).fillna(0)
        pool=pool[(pool[GB]<=cap*8)&membership_for_target(pool,'GlobalBuffer',cap/135168)].copy().reset_index(drop=True)
        v=vectors(pool);final=restore(final_record);fv=vectors(final,public=True)
        consumer='Matmul2<SEP>compressed_index'
        conditional=np.zeros(len(pool),dtype=bool)
        choices=np.zeros(len(pool),dtype='int64');same_sets=defaultdict(list)
        prefix_cols=['Matmul0<SEP>compressed_index','Matmul1<SEP>compressed_index']
        # Hold the prepared alignment/Join bucket as well as the local consumer
        # source fixed; a source ID alone need not fix its final LoopTree context.
        for positions in pool.groupby(['_bucket',consumer],sort=False).indices.values():
            conditional[positions]=strict_front(v[positions])
            by_source={tuple(int(pool[c].iloc[i])for c in prefix_cols):int(i)for i in positions}
            choices[positions]=len(by_source)
            if len(by_source)==len(positions)and len(by_source)>1:
                same_sets[(int(pool['_bucket'].iloc[positions[0]]),tuple(sorted(by_source)))].append(by_source)
        # A stronger finite witness: SAME producer set and prepared program,
        # different consumer row, with a producer's efficiency status changing.
        for (bucket,producer_set),groups in same_sets.items():
            if len(groups)<2:continue
            for qsource in producer_set:
                wins=next((g for g in groups if conditional[g[qsource]]),None)
                loses=next((g for g in groups if not conditional[g[qsource]]),None)
                if wins is None or loses is None:continue
                q1,q2=wins[qsource],loses[qsource]
                relevant=[job(target,c,pool[c].iloc[q1])for c in prefix_cols]
                relevant=[k for k in relevant if k in interesting]
                if not relevant:continue
                psource=next(p for p in producer_set if (v[loses[p]]<=v[q2]).all()and (v[loses[p]]<v[q2]).any())
                p1,p2=wins[psource],loses[psource]
                resource_flip=bool((v[p1,:2]<=v[q1,:2]).all()and (v[p2,:2]<=v[q2,:2]).all()and
                    (v[p1,2:]>v[q1,2:]).any()and (v[p2,2:]<=v[q2,2:]).all())
                separated=bool(separated_costs(v[q1],v[p1],v[q2],v[p2]))
                example=dict(target=point,bucket=bucket,producer_competitor_count=len(producer_set),
                    q_prefix_sources=qsource,p_prefix_sources=psource,
                    consumer_when_q_efficient=int(pool[consumer].iloc[q1]),
                    consumer_when_p_dominates=int(pool[consumer].iloc[q2]),
                    q_efficient_context=v[q1].tolist(),p_efficient_context=v[p1].tolist(),
                    q_dominated_context=v[q2].tolist(),p_dominated_context=v[p2].tolist(),
                    resource_order_reversal=resource_flip,strict_cost_margin_filter=separated,cohort_jobs=relevant)
                if len(reversal_examples)<200:reversal_examples.append(example)
                if resource_flip:
                    for k in relevant:
                        stats[k]['resource_context_reversal_witnesses']+=1
                        stats[k]['examples'].setdefault('same_producer_set_resource_reversal',example)
                        if separated:
                            stats[k]['margin_separated_resource_reversal_witnesses']+=1
                            stats[k]['examples'].setdefault('margin_separated_resource_reversal',example)
        equal_count=strict_count=0
        for i,q in enumerate(v):
            equality=np.flatnonzero((fv==q).all(axis=1))
            dominators=np.flatnonzero((fv<=q).all(axis=1)&(fv<q).any(axis=1))
            if not len(equality)and not len(dominators):
                raise AssertionError('visited feasible completion has no final numeric cover')
            equal_count+=bool(len(equality));strict_count+=not len(equality)
            for k in row_jobs(target,pool,i):
                if k not in interesting:continue
                s=stats[k];s['terminal_target_completion_occurrences']+=1
                s['equal_final_point_occurrences']+=bool(len(equality))
                s['strict_global_dominance_occurrences']+=not len(equality)
                s['consumer_conditioned_front_occurrences']+=bool(conditional[i])
                contrast=bool(conditional[i])and not len(equality)
                s['consumer_conditioned_but_globally_strict_occurrences']+=contrast
                s['nontrivial_conditioning_contrast_occurrences']+=int(contrast and choices[i]>1)
                name='equal_frontier_point'if len(equality)else 'strict_global_cover'
                if contrast:name='finite_consumer_conditioning_contrast'
                if name not in s['examples']:
                    p=int(equality[0]if len(equality)else dominators[0])
                    s['examples'][name]=dict(target=point,bucket=int(pool['_bucket'].iloc[i]),
                        consumer_candidate=int(pool[consumer].iloc[i]),
                        conditioned_producer_choices=int(choices[i]),
                        local_source_indices={c:int(pool[c].iloc[i])for c in pool if c.endswith('<SEP>compressed_index')},
                        complete_vector=q.tolist(),covering_final_vector=fv[p].tolist(),
                        covering_final_returned_row=int(final.index[p]),
                        covering_final_sources=next(r['tile_ids']for r in raw['provenance']['final_sources'][point]
                            if r['returned_row']==int(final.index[p])))
        point_results[point]=dict(recorded_capacity_feasible_completion_occurrences=len(pool),
            equal_final_point_occurrences=equal_count,strict_global_cover_occurrences=strict_count,
            consumer_conditioned_front_occurrences=int(conditional.sum()))
    counts=Counter()
    for s in stats.values():
        s['local_sufficient_coverage_complete']=(s['local_row_occurrences']>0 and
            s['local_row_occurrences']==s['local_sufficiently_covered_rows'])
        for label,predicate in (
            ('local_sufficient_coverage_complete',s['local_sufficient_coverage_complete']),
            ('has_visited_feasible_complete_plan',s['terminal_target_completion_occurrences']>0),
            ('has_equal_final_point',s['equal_final_point_occurrences']>0),
            ('has_strict_global_cover',s['strict_global_dominance_occurrences']>0),
            ('has_finite_consumer_conditioning_contrast',s['consumer_conditioned_but_globally_strict_occurrences']>0),
            ('has_nonsingleton_conditioning_contrast',s['nontrivial_conditioning_contrast_occurrences']>0),
            ('has_same_producer_set_resource_reversal',s['resource_context_reversal_witnesses']>0),
            ('has_margin_separated_resource_reversal',s['margin_separated_resource_reversal_witnesses']>0),
            ('unresolved_no_terminal_witness',s['terminal_target_completion_occurrences']==0)):
            counts[label]+=predicate
        s['classification_scope']='Observed reference trace only; not exhaustive legal completions or universal local/context dominance.'
    return dict(status='complete',cohort=54,counts=dict(counts),points=point_results,
        conditioning_key='Exact recorded prepared Join bucket + final consumer compressed source.',
        context_reversal_examples=reversal_examples,
        jobs=list(stats.values()),classification_s=time.perf_counter()-started,
        proven_graph_specific_waste_s=None,
        scope='Overlapping evidence classes, not a partition into universal causes. No absence of a local witness is treated as proof of Graph necessity.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--trace',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    with gzip.open(args.trace,'rt')as stream:raw=json.load(stream)
    g1=json.loads((common.ROOT/'research/diagnostics/results/generation_provenance_3mm/trial_1.json').read_text())
    result=classify(raw,g1)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(counts=result['counts'],seconds=result['classification_s'])),flush=True)


if __name__=='__main__':main()
