"""Correctness gate against a separately generated, unchanged FFM search.

Usage: python -m research.graph_coopt.audit --output path.json
This is not a performance experiment or a graph-planning algorithm.
"""
import argparse
import json
from pathlib import Path

from pandas.testing import assert_frame_equal

from research.graph_coopt.ffm_adapter import generate_memo, join_memo
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, validate_pick


def numeric_frontier(frame):
    numeric = frame.select_dtypes(include='number')
    cols = sorted(numeric.columns)
    return numeric[cols].sort_values(cols).reset_index(drop=True)


def audit_case(n, capacity):
    case = common.Case('matmuls', 'nvdla', (n, 4, 8))
    shape = (4, 8)
    common.clear_switches()
    reference, _ = common.search(build(case, shape, capacity, common.RU))
    common.clear_switches()
    memo = generate_memo(build(case, shape, capacity, common.RU))
    actual = join_memo(memo)
    assert_frame_equal(numeric_frontier(reference.data), numeric_frontier(actual.data))
    if actual.data.empty:
        raise AssertionError('empty output')
    validations = [validate_pick(case, shape, capacity, row)
                   for _, row in actual.data.iterrows()]
    if not all(v['ok'] and v['feasible'] for v in validations):
        raise AssertionError('mapping validation failed')
    return dict(workload=str(case), shape=shape, capacity_bytes=capacity,
                dag_nodes=memo.dag.nodes, dag_edges=memo.dag.edges,
                candidate_groups=len(memo.groups),
                candidate_rows=sum(g.row_count for g in memo.groups),
                result_rows=len(actual.data),
                reference_rows=len(reference.data),
                complete_numeric_frontier_equal=True,
                reconstructed_and_re_evaluated=len(validations),
                unique_mapping_ids=len({v['mapping_id'] for v in validations}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    common.af.set_n_parallel_jobs(1)
    report = dict(scope='Fixed architecture; memo stores FFM groups, original FFM performs all joins. No cross-architecture reuse or new planner.',
                  results=[audit_case(2, 96), audit_case(3, 128)])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
