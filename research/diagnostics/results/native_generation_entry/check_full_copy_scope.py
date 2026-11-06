"""One archived-family counterexample check; no model, search, or filter.

Restricted to frozen dense 8-bit 3mm(256,256), raw linear templates and their
first emitted Tile. Fail closed on unrecognized symbols/storage/loop patterns.
This is not a general Mapping parser or proof that these rows are Pareto-needed.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[4]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    source=ROOT/'research/diagnostics/results/counterfactual_effects/trace.json.gz'
    facts_path=ROOT/'research/diagnostics/results/pregen_certificates/native_1.json'
    with gzip.open(source,'rt')as stream:trace=json.load(stream)
    facts=json.loads(facts_path.read_text())
    lookup={}
    for catalog in facts['catalogs']:
        for fact in catalog['records'].values():
            key=(fact['target'],fact['einsum'],fact['template'])
            if key in lookup:raise AssertionError('ambiguous family identity')
            lookup[key]=fact
    records=[]
    for task in trace['provenance']['tasks']:
        fact=lookup[(task['target'],task['einsum'],task['template'])]
        if fact['unknown']is not None:raise AssertionError('unsupported native template facts')
        tokens=re.findall(r'\[[^\]]+\]|S-\w+-\w+|T-\w+',task['template'])
        first={}
        for token in tokens:
            if token.startswith('['):
                names,component=token[1:-1].rsplit(' in ',1)
                for name in names.split(','):first.setdefault(name.strip(),component)
        needed={'Matmul0':{'T1'},'Matmul1':{'T1','T2'},'Matmul2':{'T2'}}[task['einsum']]
        if not all(first[t]=='MainMemory'for t in needed):continue
        # In this frozen grammar the model names raw loops stride{loop_index};
        # only the last loop of each rank is forcibly set to one before analysis.
        ranks=[x.rsplit('-',1)[-1]for x in tokens if not x.startswith('[')]
        last={rank:i for i,rank in enumerate(ranks)}
        assignment=dict(zip(task['symbols'],task['tile_assignments'][0]))
        if any(not re.fullmatch(r'stride\d+',s)for s in assignment):
            raise AssertionError('initial/unknown Tile pattern')
        if set(assignment)!={f'stride{i}'for i,rank in enumerate(ranks)if last[rank]!=i}:
            raise AssertionError('raw loop/Symbol correspondence is not the checked grammar')
        shape={r:256 for r in ('m','n0','n1','n2','n3')}
        copies={t:[] for t in needed};loop=0;spatial_seen=False
        for token in tokens:
            if not token.startswith('['):
                rank=ranks[loop];symbol=f'stride{loop}'
                if symbol in assignment:value=assignment[symbol]
                elif last[rank]==loop:value=1
                else:raise AssertionError('unbound nonterminal loop')
                if type(value)is not int or value<=0 or shape[rank]%value:
                    raise AssertionError('not a perfect-tiling assignment')
                shape[rank]=value;loop+=1;spatial_seen|=token.startswith('S-')
            else:
                names,component=token[1:-1].rsplit(' in ',1)
                for tensor in map(str.strip,names.split(',')):
                    if component!='GlobalBuffer' or tensor not in needed:continue
                    if spatial_seen:raise AssertionError('spatial/GB reorder requires another proof')
                    axes=('m','n'+tensor[1:]);extents=[shape[r]for r in axes]
                    copies[tensor].append(dict(axes=axes,extents=extents,
                        raw_scope_payload_upper_bits=8*extents[0]*extents[1]))
        if any(len(v)!=1 for v in copies.values()):
            raise AssertionError('multiple/missing same-tensor GB copies need another proof')
        partial=[t for t,v in copies.items()if v[0]['raw_scope_payload_upper_bits']<256*256*8]
        if not partial:raise AssertionError('this first Tile does not refute full-copy eligibility')
        records.append(dict(task_id=task['id'],target=task['target'],einsum=task['einsum'],
            template=task['template'],first_emitted_tile_id=task['tile_ids'][0],assignment=assignment,
            relevant_intermediates=sorted(needed),copy_bounds=copies,partial_intermediates=partial,
            job_has_returned_descendant=task['has_final_descendant'],
            observed_stage_class=task['observed_stage_class']))
    if len(records)!=54:raise AssertionError('frozen native-family cohort changed')
    result=dict(status='complete',base_commit='b1725647a6f79623884b9f840f85ae0aacb38a6b',
        candidate='Sequential full-buffer forwarding, with full-copy and ownership premises.',
        scope='Offline refutation of applying this rewrite to entire observed raw DRAM-backed Job domains.',
        dram_backed_raw_jobs=54,jobs_with_an_emitted_tile_outside_full_copy_predicate=len(records),
        entire_jobs_certified_by_this_rewrite_alone=0,
        stage_counts=dict(Counter(r['observed_stage_class']for r in records)),
        records=records,
        assumptions=['Frozen direct dense 3mm, all rank extents 256 and values 8 bits.',
            'Perfect divisor Tiles; no initial-Tile/halo cases; terminal loops forced to one.',
            'Exactly one relevant GB copy per tensor and no preceding spatial loop.',
            'Later reservation lowering cannot enlarge the tensor region present at this GB storage scope.'],
        limitations=['Counterexamples to whole-Job predicate applicability, not necessary Pareto completions.',
            'Compact strings are used only under the checked restricted pattern, not as equivalence keys.',
            'No lower bound on all possible partial-prefix savings, and no general no-go for forwarding.'],
        native_searches_run=0,native_model_calls=0,actual_generation_tasks_skipped=0,
        checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()for p in (
            'accelforge/frontend/mapping/mapping.py',
            'accelforge/model/_looptree/reuse/symbolic/symbolic.py',
            'accelforge/mapper/FFM/_make_pmappings/make_pmappings_from_templates/make_tile_shapes.py')},
        archive_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (source,facts_path)})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k]for k in ('status','dram_backed_raw_jobs',
        'jobs_with_an_emitted_tile_outside_full_copy_predicate','entire_jobs_certified_by_this_rewrite_alone','stage_counts')}))


if __name__=='__main__':main()
