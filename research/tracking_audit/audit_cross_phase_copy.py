"""Build conditional element witnesses for archived, re-evaluated FFM mappings."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from research.tracking_audit.cross_phase_copy_oracle import make_witness, compare_main_actions
from research.tracking_audit import common


def run(output):
    root = Path(__file__).parent
    archives = [root/'results/fusion_cut/audit.json',root/'results/fusion_cut/larger.json']
    lifetime_path = root/'results/fusion_lifetime/audit.json'
    lifetime = json.loads(lifetime_path.read_text())
    if not lifetime['all_valid']:
        raise ValueError('the source lifetime audit did not complete validation')
    for name, digest in lifetime['source_sha256'].items():
        if hashlib.sha256((common.ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError('source lifetime code or data changed: '+name)
    lifetime_counts = {(tuple(c['dimensions']),c['capacity_bytes']):Counter(r['mapping_id'] for r in c['rows'])
                       for c in lifetime['cases']}
    lifetime_status = {(tuple(c['dimensions']),c['capacity_bytes'],r['mapping_id']):r['ledger']['status']
                       for c in lifetime['cases'] for r in c['rows']}
    files = [Path(__file__),root/'cross_phase_copy_oracle.py',lifetime_path,*archives]
    report = dict(scope='constructed element witnesses conditional on declared backing; not FFM execution traces',
        source_sha256={str(p.relative_to(common.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        rows=[], skipped=[], unique_mapping_ids=0, validation_complete=False)
    seen = defaultdict(list)
    for path in archives:
        data = json.loads(path.read_text())
        if not data['all_valid']:
            raise ValueError('source FFM action audit not valid')
        for name, digest in data['source_sha256'].items():
            if hashlib.sha256((common.ROOT/name).read_bytes()).hexdigest() != digest:
                raise ValueError('source audit code or model changed: '+name)
        dimensions = (4,8) if path.name=='audit.json' else (8,16)
        if data['workload_T1_full_bits'] != dimensions[0]*dimensions[1]*8:
            raise ValueError('unexpected intermediate tensor shape or precision')
        for search in data['searches']:
            capacity = search['capacity_bytes']
            rows = search['rows']
            if Counter(r['mapping_id'] for r in rows) != lifetime_counts[(dimensions,capacity)]:
                raise ValueError('source FFM and lifetime mapping identities differ')
            for row in rows:
                if not row['actions_match'] or not row['validation']['ok']:
                    raise ValueError('source row was not successfully re-evaluated')
                cut = row['cut']
                if cut['kind'] != 'root_sequential_producer_consumer':
                    report['skipped'].append(dict(dimensions=dimensions,capacity_bytes=capacity,
                        mapping_id=row['mapping_id'],reason=cut['reason']))
                    continue
                if lifetime_status[(dimensions,capacity,row['mapping_id'])] != 'phase_scopes_only':
                    raise ValueError('the corresponding lifetime scope was not supported')
                if len(cut['cross_cut_storage']) != 1 or cut['cross_cut_storage'][0] not in ('MainMemory','GlobalBuffer'):
                    report['skipped'].append(dict(dimensions=dimensions,capacity_bytes=capacity,
                        mapping_id=row['mapping_id'],reason='no unique supported declared location'))
                    continue
                location = cut['cross_cut_storage'][0]
                # Save detailed element events for the two requested 96-byte
                # examples. Other instances are still validated element by element.
                detailed = dimensions==(4,8) and capacity==96 and row['index'] in (0,3)
                witness = make_witness(*dimensions,location,capture_events=detailed)
                compare = compare_main_actions(witness,row['t1_mainmemory_actions_bits'])
                record = dict(dimensions=dimensions,capacity_bytes=capacity,index=row['index'],
                    mapping_id=row['mapping_id'],declared_storage_location=location,
                    declaration_implies_physical_copy=False,
                    recorded_t1_mainmemory_actions_bits=row['t1_mainmemory_actions_bits'],
                    witness=witness,comparison=compare)
                report['rows'].append(record)
                seen[row['mapping_id']].append(len(report['rows'])-1)
    report['unique_mapping_ids'] = len(seen)
    report['mapping_occurrence_counts'] = dict(Counter(map(len,seen.values())))
    report['validation_complete'] = bool(report['rows']) and all(
        r['comparison']['counts_are_consistent'] and not r['witness']['safe_to_prune'] for r in report['rows'])
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    if not report['validation_complete']:
        raise AssertionError('a conditional witness disagrees with source action counts')
    print(json.dumps(dict(instances=len(report['rows']),unique=report['unique_mapping_ids'],
                          skipped=len(report['skipped']),all_conditional_counts_consistent=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output)
