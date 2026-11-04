"""Audit real prefix reuse against the frozen pre-refactor Join controller."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch

from pandas.testing import assert_frame_equal

from accelforge.mapper.FFM._join_pmappings.compress_pmappings import compress_einsum2pmappings
from accelforge.mapper.FFM._join_pmappings.join_pmappings import restore_mappings
from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe
from research.graph_coopt._reference_join_bd39555f import reference_join_pmappings
from research.graph_coopt.ffm_adapter import generate_memo, join_memo
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, validate_pick


def numeric(frame):
    frame = frame.select_dtypes(include='number')
    cols = sorted(frame.columns)
    return frame[cols].sort_values(cols).reset_index(drop=True)


def audit(n, capacity):
    case = common.Case('matmuls', 'nvdla', (n, 4, 8))
    common.clear_switches()
    timings = {}
    started = time.perf_counter()
    memo = generate_memo(build(case, (4, 8), capacity, common.RU))
    timings['spec_generation_and_memo_snapshot_s'] = time.perf_counter() - started
    source = memo.materialize()
    compressed, metadata = compress_einsum2pmappings(source.einsum2pmappings)
    expected = restore_mappings(source, reference_join_pmappings(compressed, source.spec),
                                metadata, tuple(source.einsum2pmappings))
    calls = []
    original = PmappingDataframe.merge_next

    def counted(self, right, *args, **kwargs):
        calls.append([c.split('<SEP>')[0] for c in right.data if c.endswith('<SEP>compressed_index')])
        return original(self, right, *args, **kwargs)

    with patch.object(PmappingDataframe, 'merge_next', counted):
        started = time.perf_counter()
        initial = memo.start()
        timings['candidate_store_and_start_s'] = time.perf_counter() - started
        started = time.perf_counter()
        middle = memo.advance(initial, 'Matmul1')
        timings['prefix_advance_including_copy_s'] = time.perf_counter() - started
        started = time.perf_counter()
        memo.save_partial(middle)
        timings['checkpoint_copy_s'] = time.perf_counter() - started
        before = len(calls)
        with patch('accelforge.mapper.FFM._make_pmappings.make_pmappings.get_jobs',
                   side_effect=AssertionError('generation called after pause')):
            started = time.perf_counter()
            resumed = memo.resume_partial(middle.processed)
            timings['resume_copy_s'] = time.perf_counter() - started
            started = time.perf_counter()
            actual = join_memo(memo, resumed)
            timings['continuation_finalize_and_source_copy_s'] = time.perf_counter() - started
    resumed_calls = calls[before:]
    if not calls[:before] or any(names != ['Matmul1'] for names in calls[:before]):
        raise AssertionError('unexpected prefix call trace')
    if any(names != ['Matmul2'] for names in resumed_calls) or n == 3 and not resumed_calls:
        raise AssertionError('prefix replay or missing continuation')
    assert_frame_equal(numeric(expected.data), numeric(actual.data))
    identities = lambda r: sorted(common.mapping_identity(row['Total<SEP>mapping']())
                                 for _, row in r.data.iterrows())
    if identities(expected) != identities(actual):
        raise AssertionError('source mapping identities changed')
    started = time.perf_counter()
    validations = [validate_pick(case, (4, 8), capacity, row) for _, row in actual.data.iterrows()]
    timings['reconstruction_validation_s'] = time.perf_counter() - started
    if not validations or not all(v['ok'] for v in validations):
        raise AssertionError('reconstructed mapping failed')
    return dict(workload=str(case), shape=[4, 8], capacity_bytes=capacity,
                processed=list(middle.processed), remaining=list(middle.remaining),
                partial_rows=sum(len(g.mappings.data) for g in middle.left),
                prefix_merge_calls=calls[:before], resumed_merge_calls=resumed_calls,
                prefix_joins_replayed=0, generation_calls_after_pause=0,
                complete_numeric_frontier_equal=True, source_mapping_identities_equal=True,
                result_rows=len(actual.data), re_evaluations=len(validations),
                diagnostic_phase_seconds=timings,
                total_including_generation_copies_and_validation_s=sum(timings.values()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    common.af.set_n_parallel_jobs(1)
    report = dict(scope='Engineering reference-equivalent in-memory pause/resume; no new pruning, cross-architecture binding or speedup claim.',
                  timing_scope='One diagnostic run per case; frozen-reference work excluded from phase totals but runs before the new engine and warms JIT. No fair baseline timing or speedup inference.',
                  results=[audit(2, 96), audit(3, 128)])
    paths = [Path(__file__), *Path(__file__).parent.glob('_reference_join_*.py'),
             *[common.ROOT / 'accelforge/mapper/FFM/_join_pmappings' / name for name in (
                 'join_pmappings.py', 'join_engine.py', 'join_context.py', 'partial_state.py')],
             Path(__file__).with_name('ffm_adapter.py'), Path(__file__).with_name('memo.py')]
    report['source_sha256'] = {str(p.relative_to(common.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in paths}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['results'], indent=2))


if __name__ == '__main__':
    main()
