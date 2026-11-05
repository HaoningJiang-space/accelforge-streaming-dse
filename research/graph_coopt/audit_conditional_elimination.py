"""Compare one legal conditional producer elimination with native final Join."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from pandas.testing import assert_frame_equal

from research.graph_coopt.conditional_elimination import TerminalBucketElimination
from research.graph_coopt.validate_resource_effect import NativeTransferCheck
from research.graph_coopt.cut_state_analysis import numeric_frontier
from research.graph_coopt.decision_hypergraph_audit import JoinObserver
from research.graph_coopt.ffm_adapter import prepare_candidates
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, validate_pick


def work(observer):
    return dict(numeric_group_joins=len(observer.calls),
                materialized_pairs=sum(c['materialized_pair_rows'] for c in observer.calls),
                largest_pair_frame=max(c['materialized_pair_rows'] for c in observer.calls),
                post_pareto_rows=sum(c['post_local_pareto_rows'] for c in observer.calls))


def audit(n, m, kn, shape, capacity):
    started = time.perf_counter()
    common.clear_switches()
    common.af.set_n_parallel_jobs(1)
    case = common.Case('matmuls', 'nvdla', (n, m, kn))
    pm = common.make_pmappings(build(case, shape, capacity, common.RU), print_number_of_pmappings=False)
    store = prepare_candidates(pm)
    cut = store.start()
    while len(cut.remaining) > 1:
        cut = store.advance(cut)
    if len(cut.remaining) != 1:
        raise ValueError('one prepared terminal consumer required')
    native_observer = JoinObserver()
    transfer_check = NativeTransferCheck()
    with transfer_check.installed(), native_observer.installed():
        expected = store.finalize(store.advance(cut))
    identities = lambda result: sorted(common.mapping_identity(row['Total<SEP>mapping']())
                                       for _, row in result.data.iterrows())
    variants = {}
    for mode in ('coordinates', 'live_coordinates', 'effect'):
        elimination, reduced_observer = TerminalBucketElimination(mode=mode), JoinObserver()
        # Reducer captures the native numeric implementation; observer wraps it.
        with elimination.installed(), reduced_observer.installed():
            actual = store.finalize(store.advance(cut))
        assert_frame_equal(numeric_frontier(expected.data), numeric_frontier(actual.data))
        if identities(expected) != identities(actual):
            raise AssertionError('strictness guard did not preserve Mapping source identities')
        variants[mode] = dict(work=work(reduced_observer), bucket_records=elimination.records,
            producer_row_occurrences_removed=sum(r['rows_before'] - r['rows_after'] for r in elimination.records),
            full_numeric_frontier_equal=True, full_mapping_sources_equal=True)
    for _, row in actual.data.iterrows():
        if not validate_pick(case, shape, capacity, row)['ok']:
            raise AssertionError('reduced final frontier failed reconstruction')
    return dict(case=str(case), shape=list(shape), capacity_bytes=capacity,
                processed=list(cut.processed), consumer=cut.remaining[0],
                native=work(native_observer), variants=variants,
                native_transfer_validation=dict(checked_rows=transfer_check.checked_rows,
                    checked_coordinates=transfer_check.checked_coordinates, unknown=transfer_check.unknown),
                full_numeric_frontier_equal=True, full_mapping_sources_equal=True,
                final_reconstruction_instances=len(actual.data),
                target_optimum_used=False, completion_response_oracle_used=False,
                candidate_generation_avoided=False, cross_architecture_rule_established=False,
                diagnostic_total_s=time.perf_counter() - started,
                speedup_claim=False, pipeline_scope='One terminal consumer group per bucket; upstream candidate/policy decisions frozen.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    points = [(2, 4, 8, (4, 8), 96), (3, 4, 8, (4, 8), 128),
              (2, 4, 8, (8, 4), 96), (3, 4, 8, (8, 4), 128),
              (2, 16, 16, (16, 16), 4096), (3, 16, 16, (16, 16), 4096)]
    report = dict(scope='Restricted conditional elimination contract probe, not a full InsideOut or joint architecture optimizer.',
                  status='in_progress', results=[])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for point in points:
        try:
            result = audit(*point)
        except Exception as exc:
            report['status'] = 'failed'
            report['failure'] = dict(point=point, message=str(exc))
            args.output.write_text(json.dumps(report, indent=2) + '\n')
            raise
        report['results'].append(result)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(dict(case=result['case'], shape=result['shape'], native=result['native'],
            variants={k: v['work'] for k, v in result['variants'].items()},
            transfer_validation=result['native_transfer_validation'])), flush=True)
    paths = [Path(__file__), Path(__file__).with_name('conditional_elimination.py'),
             Path(__file__).with_name('resource_effect.py'), Path(__file__).with_name('validate_resource_effect.py'),
             common.ROOT / 'accelforge/mapper/FFM/_join_pmappings/pmapping_dataframe.py']
    report['source_sha256'] = {str(p.relative_to(common.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    report['status'] = 'complete'
    args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
