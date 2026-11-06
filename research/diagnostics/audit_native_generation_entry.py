"""Read existing G1/G2/consumer archives; no observer, native search or pruning.

Reproduce one closed-scope certificate's information boundary. Cross-run links
use uniquely observed (target, einsum, compact template), never UUID/task IDs.
That archive join is not a sufficient model-reuse key.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
from time import perf_counter

from research.diagnostics.scoped_resource_effect import compile_closed, concrete_oracle, exact, parse


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT/'research/diagnostics/results'


def unique_index(items, key):
    result = {}
    for item in items:
        k = key(item)
        if k in result:
            raise ValueError('ambiguous archive join: '+repr(k))
        result[k] = item
    return result


def raw_key(record):
    return record['target'], record['einsum'], record['template']


def position(frame, selection):
    choices = [i for i in range(len(frame['index']))
               if all(frame['columns'][k][i]==v for k,v in selection.items())]
    if len(choices)!=1:
        raise ValueError('archive row is not unique: '+repr(selection))
    return choices[0]


def audit():
    started = perf_counter()
    files = {
        'g1': ARCHIVE/'generation_provenance_3mm/trial_1.json',
        'g2': ARCHIVE/'pregen_certificates/native_1.json',
        'classification': ARCHIVE/'counterfactual_effects/classification.json',
        'trace': ARCHIVE/'counterfactual_effects/trace.json.gz',
    }
    values = {name:json.loads(path.read_text()) for name,path in files.items() if name!='trace'}
    with gzip.open(files['trace'],'rt') as stream:
        trace = json.load(stream)
    provenance = trace['provenance']
    native = unique_index(provenance['tasks'],raw_key)
    g1 = unique_index(values['g1']['tasks'],raw_key)
    g2 = unique_index((record for c in values['g2']['catalogs'] for record in c['records'].values()),raw_key)
    if not native.keys()==g1.keys()==g2.keys() or len(native)!=126:
        raise AssertionError('the three archived catalogs do not describe the same 126 raw families')
    for key,task in native.items():
        if task['has_final_descendant']!=g1[key]['has_final_descendant']:
            raise AssertionError('archive returned-source labels differ')
    witness = next(job['examples']['margin_separated_resource_reversal']
                   for job in values['classification']['jobs'] if job['task_id']=='task:55')
    if (witness['consumer_when_q_efficient'],witness['consumer_when_p_dominates'])!=(217,209):
        raise AssertionError('selected archived consumer witness changed')
    bucket = next(b for b in trace['buckets'] if b['id']==witness['bucket'])
    if bucket['next_shared_loop_index']!=-1 or any(bucket[k]for k in ('allocation_count','free_count','alias_count')):
        raise AssertionError('selected resource program is outside the existing closed grammar')
    tasks = unique_index(provenance['tasks'],lambda x:x['id'])
    compressed = unique_index(provenance['compressed_local_rows'],
        lambda x:(x['target'],x['einsum'],x['compressed_index']))
    def link(einsum,source):
        row = compressed[(bucket['target'],einsum,source)]
        task = tasks[row['task_id']]
        key = raw_key(task)
        fact = g2[key]
        tile_position = task['tile_ids'].index(row['tile_id'])
        return dict(compressed_source=source, trace_task=task['id'],g1_task=g1[key]['id'],
            einsum=einsum,template=task['template'],target=task['target'],
            tile_id=row['tile_id'], tile=dict(zip(task['symbols'],task['tile_assignments'][tile_position])),
            job_has_returned_descendant=task['has_final_descendant'],
            generated_model_rows=len(task['tile_ids']),
            premodel_bound=fact['bound'],premodel_unknown=fact['unknown'],
            premodel_decisions=fact['targets'], historical_g1_evaluation_s=g1[key]['evaluation_s'])
    links = {
        role:[link(f'Matmul{i}',source) for i,source in enumerate(witness[role+'_prefix_sources'])]
        for role in ('q','p')}
    links['consumers']=[link('Matmul2',witness[k]) for k in
        ('consumer_when_q_efficient','consumer_when_p_dominates')]
    left,right = bucket['prepared_left'],bucket['prepared_right']
    positions = {role:position(left,dict(zip(bucket['left_sources'],witness[role+'_prefix_sources'])))
                 for role in ('q','p')}
    differing = {key:[column[positions[role]]for role in ('q','p')]
                 for key,column in left['columns'].items()
                 if column[positions['q']]!=column[positions['p']]}
    allowed = {'Total<SEP>energy',*bucket['left_sources']}
    if any(k not in allowed and parse(k)is None for k in differing):
        raise AssertionError('prefixes differ in an unmodeled physical/context field')
    lcols = [c for c in left['columns'] if parse(c)is not None and parse(c)[0]in ('GlobalBuffer','Register')]
    rcols = [c for c in right['columns'] if parse(c)is not None and parse(c)[0]in ('GlobalBuffer','Register')]
    operations = [tuple(op)for op in bucket['operations']if parse(op[0])is not None and parse(op[0])[0]in ('GlobalBuffer','Register')]
    checks = []
    effects = {}
    for role,lp in positions.items():
        lv = {c:exact(left['columns'][c][lp])for c in lcols}
        effect = compile_closed(lv,rcols,operations)
        effects[role] = effect.record()
        for context,consumer in enumerate(links['consumers']):
            rp = position(right,{bucket['right_sources'][0]:consumer['compressed_source']})
            if not all(left['columns'][a][lp]==right['columns'][b][rp]
                       for a,b in zip(bucket['left_match'],bucket['right_match'])):
                raise AssertionError('witness violates the prepared physical match')
            rv = {c:exact(right['columns'][c][rp])for c in rcols}
            result = effect.evaluate(rv)
            if result!=concrete_oracle(lv,rv,operations):
                raise AssertionError('resource effect and existing scalar interpreter disagree')
            selection = dict(zip(bucket['left_sources'],witness[role+'_prefix_sources']))
            selection[bucket['right_sources'][0]]=consumer['compressed_source']
            terminal = bucket['pre_capacity'];tp = position(terminal,selection)
            if any(result[c]!=exact(terminal['columns'][c][tp])for c in result):
                raise AssertionError('resource effect differs from archived native result')
            expected = witness[role+('_efficient_context'if context==0 else'_dominated_context')]
            observed = [terminal['columns']['Total<SEP>energy'][tp],terminal['columns']['Total<SEP>latency'][tp],
                max(v for c,v in result.items()if parse(c)[0]=='GlobalBuffer'),
                max(v for c,v in result.items()if parse(c)[0]=='Register')]
            if observed!=expected:
                raise AssertionError('complete witness differs from archived native pre-capacity row')
            checks.append(dict(prefix=role,consumer=consumer['compressed_source'],
                incoming_resource_bits=rv,resource_result_bits=result,complete_vector=observed))
    # Recognize this recorded pair; do not infer a theorem for arbitrary programs.
    gb='reservation<SEP>GlobalBuffer<SEP>0<SEP>right'
    if effects['q']['variables']!=effects['p']['variables']:
        raise AssertionError('different resource domains')
    def terms(role):
        return {(tuple(t['coefficients']),t['intercept'])for t in effects[role]['outputs'][gb]}
    qterms,pterms=terms('q'),terms('p');common=qterms&pterms
    qonly,p_only=qterms-common,pterms-common
    if (qonly,p_only)!=({((0,0,0),360448)},{((0,0,0),557056)}) or common!={((0,1,0),262144),((1,0,0),264192)}:
        raise AssertionError('the documented resource equality region changed')
    return dict(status='complete',native_search_rerun=False,actual_jobs_skipped=0,
        actual_run_model_calls_avoided=0,actual_tile_enumerations_avoided=0,
        actual_candidate_materializations_avoided=0,
        catalog_crosswalk=dict(raw_families=126,unique_keys_verified=True,
            key='(shared target, einsum, compact template); archive linkage only, not an equivalence key',
            returned_source_labels_equal=True),
        g1_stage_counts=dict(Counter(t['observed_stage_class']for t in g1.values())),
        inherited_g2=values['g2']['tiers'],selected_witness=witness,
        physical_contract=dict(bucket=bucket['id'],target=bucket['target'],
            shared_loop_index=bucket['shared_loop_index'],next_shared_loop_index=bucket['next_shared_loop_index'],
            allocation_count=0,free_count=0,alias_count=0,
            nonresource_context_fields_equal=True,differing_prepared_fields=differing,
            left_match=bucket['left_match'],right_match=bucket['right_match']),
        linked_raw_families=links,prepared_effects=effects,native_and_scalar_resource_replay=checks,
        conditional_resource_equality=dict(resource_unit='bits',floors_kib=dict(q=44,p=68),
            common_term_offsets_kib=[32,32.25],
            statement='For this prepared closed program, both GB responses are equal iff max(32KiB+x3,32.25KiB+x2)>=68KiB.',
            pre_generation_certificate=False,raw_job_elimination_proved=False),
        scope='Offline archive crosswalk and prepared-program replay. No new analyzer, native execution or search mechanism.',
        archive_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in files.values()},
        executed_source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        offline_audit_wall_s=perf_counter()-started)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status=result['status'],families=126,prepared_rows_checked=4,
                         native_search_rerun=False,actual_generation_avoided=0)))


if __name__=='__main__':
    main()
