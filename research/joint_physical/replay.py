"""Rebuild saved mappings and rescore them on the original physical NVDLA spec."""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path

from accelforge.frontend import mapping as af_mapping
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import validate_pick,build,mapping_structure
from research.joint_budget.protocol import Hardware,ResourceBudget


NODE_TYPES = {name:getattr(af_mapping,name) for name in (
    'Mapping','Nested','Sequential','Storage','Temporal','Spatial','Compute','Reservation')}


def encode(mapping):
    record = mapping_structure(mapping)
    def annotate(node,out):
        if isinstance(node,af_mapping.Loop):
            out['native_loop'] = dict(fused=bool(node._fused),
                assume_perfect_factor=bool(node._assume_perfect_factor),
                iterations=None if node.tile_pattern.calculated_n_iterations is None else
                           str(node.tile_pattern.calculated_n_iterations))
        if isinstance(node,af_mapping.TensorHolder):
            out['native_storage'] = dict(lower=bool(node._lower),must_be_here=bool(node._must_be_here))
        if hasattr(node,'nodes'):
            for child,value in zip(node.nodes,out['nodes']):
                annotate(child,value)
    annotate(mapping,record)
    return record


def compute_names(record):
    return ({record['einsum']} if record['type']=='Compute' else
            set().union(*(compute_names(n) for n in record.get('nodes',[]))))


def decode(record,component_for,einsum=None):
    cls = NODE_TYPES[record['type']]
    if einsum is None:
        names = compute_names(record)
        if len(names)==1:
            einsum = next(iter(names))
    fields = {}
    for name,value in record.items():
        if name in ('type','native_loop','native_storage'):
            continue
        if name=='nodes':
            fields[name] = [decode(node,component_for,einsum) for node in value]
        elif name in ('tile_shape','initial_tile_shape','tensors','purposes','persistent'):
            fields[name] = ast.literal_eval(value) if isinstance(value,str) else value
        else:
            fields[name] = value
    if record['type']=='Spatial':
        if einsum is None:
            raise ValueError('spatial scope must have a unique native compute operator')
        fields['component_object'] = component_for(einsum,record['component'])
    node = cls(**fields)
    if isinstance(node,af_mapping.Loop):
        if 'native_loop' not in record:
            raise ValueError('witness predates complete native-loop metadata serialization')
        native = record['native_loop']
        node._fused = native['fused']
        node._assume_perfect_factor = native['assume_perfect_factor']
        if native['iterations'] is not None:
            node.tile_pattern = node.tile_pattern.update(calculated_n_iterations=ast.literal_eval(native['iterations']))
    if isinstance(node,af_mapping.TensorHolder):
        native = record['native_storage']
        node._lower = native['lower']
        node._must_be_here = native['must_be_here']
    return node


def replay(case,architecture,witness):
    spec = build(case,(architecture['px'],architecture['py']),architecture['capacity_bytes'],common.RU)
    evaluated = {}
    def component_for(einsum,component):
        if einsum not in evaluated:
            evaluated[einsum] = spec.calculate_component_area_energy_latency_leak(einsum_name=einsum,area=False)
        return evaluated[einsum].arch.find(component)
    mapping = decode(witness['mapping'],component_for)
    row = {'Total<SEP>mapping':lambda:mapping,'Total<SEP>energy':witness['energy'],
           'Total<SEP>latency':witness['latency']}
    actual = validate_pick(case,(architecture['px'],architecture['py']),architecture['capacity_bytes'],row)
    if not actual['ok'] or not actual['feasible']:
        raise AssertionError('serialized witness is not physically feasible')
    for field in ('energy','latency','edp','gb_bytes'):
        if not math.isclose(actual[field],witness[field],rel_tol=1e-12,abs_tol=0):
            raise AssertionError(f'physical witness changed {field}: {actual[field]} vs {witness[field]}')
    return actual['edp']


def verify(path,reference_path=None):
    common.af.set_n_parallel_jobs(1)
    report = json.loads(path.read_text(encoding='utf-8'))
    if report['status']!='complete':
        raise ValueError('complete result required')
    case = common.Case(report['case']['workload'],report['case']['arch'],tuple(report['case']['params']))
    records = [r for r in report['points'] if r.get('witness',{}).get('feasible')]
    for record in records:
        replay(case,record['architecture'],record['witness'])
    for selected in report['budget_selections']+report.get('seed_budget_selections',[]):
        if selected and (selected['architecture'] not in report['domain'] or
            not ResourceBudget(**selected['budget']).admits(Hardware(**selected['architecture']))):
            raise AssertionError('serialized selection violates its declared physical budget')
    selections = [replay(case,r['architecture'],r['witness']) for r in report['budget_selections']]
    seed = [replay(case,r['architecture'],r['witness']) if r else None
            for r in report.get('seed_budget_selections',[])]
    reference_edp = []
    if reference_path:
        reference = json.loads(reference_path.read_text(encoding='utf-8'))
        if reference['case']!=report['case'] or reference['domain']!=report['domain'] or reference.get('policy')!=report.get('policy'):
            raise ValueError('reference case/domain/policy differs')
        for selected in reference['budget_selections']:
            reference_edp.append(replay(case,selected['architecture'],selected['witness']))
        if any(a>b and not math.isclose(a,b,rel_tol=1e-12,abs_tol=0) for a,b in zip(selections,reference_edp)):
            raise AssertionError('canonical quality regressed versus fair reference')
    return dict(status='verified',serialized_physical_witnesses=len(records)+len(selections)+sum(v is not None for v in seed),
                canonical_edp=selections,reference_canonical_edp=reference_edp,
                seed_canonical_edp=seed,
                canonical_quality_no_regression=True if reference_path else None,
                report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                physical_mapspace_completeness_claim=False,external_sota_acceptance=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    result = verify(args.report,args.reference)
    if args.output:
        args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()
