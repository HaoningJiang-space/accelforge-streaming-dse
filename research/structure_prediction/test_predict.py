import hashlib
import json
from pathlib import Path
from research.structure_prediction.predict import boundaries, predictions, matching, evaluate


def test_passthrough_counts_shared_external_once_and_excludes_current_inputs():
    sizes=dict(X=10,A=20,B=30,Y=40)
    ops=[dict(name='a',inputs=['X'],outputs=['A']),dict(name='b',inputs=['X'],outputs=['B']),
         dict(name='join',inputs=['A','B'],outputs=['Y'])]
    rows=boundaries(ops,sizes)
    assert [r['pass_bytes'] for r in rows]==[0,20,0]
    assert predictions(rows)['P0']['plateau_bytes']==20
    assert predictions(rows)['P1']['plateau_bytes']==30


def test_one_to_one_matching_penalizes_candidate_flooding():
    result=matching([95,96,97,98,99,100],[100])
    assert result['matched']==1 and result['recall']==1 and result['precision']==1/6


def test_error_direction_and_significant_breakpoints():
    curve=[dict(capacity_bytes=3,traffic_bytes=100),dict(capacity_bytes=4,traffic_bytes=98),
           dict(capacity_bytes=10,traffic_bytes=50)]
    result=evaluate(dict(P0=dict(plateau_bytes=5,breakpoint_candidates=[4,10])),curve)['P0']
    assert result['signed_relative_error']==-.5
    assert result['breakpoints']['actual_count']==1
    assert result['breakpoints']['precision']==.5


def test_saved_predictions_precede_global_data_and_match_protocol():
    root=Path(__file__).parent
    count=0
    for path in (root/'results').glob('*_predictions.json'):
        frozen=json.loads(path.read_text())
        assert frozen['phase']=='predictions_frozen_before_graph_search'
        assert 'graph' not in frozen
        assert frozen['protocol_sha256']==hashlib.sha256((root/'PROTOCOL.md').read_bytes()).hexdigest()
        digest=hashlib.sha256(json.dumps(frozen['predictions'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        assert digest==frozen['prediction_sha256']
        current=json.loads(path.with_name(path.name.replace('_predictions','')).read_text())
        assert current['predictions']==frozen['predictions']
        count+=1
    assert count>0


def test_saved_reference_fronts_are_monotone_and_unit_cost_equals_actions():
    root=Path(__file__).with_name('results')
    count=0
    for path in root.glob('*.json'):
        if path.stem.endswith(('_status','_predictions')):
            continue
        record=json.loads(path.read_text())
        if record.get('phase')!='complete':
            continue
        for name in ('graph','materialized'):
            points=record[name]['points']
            assert all(a['capacity_bytes']<b['capacity_bytes'] and a['traffic_bytes']>b['traffic_bytes']
                       for a,b in zip(points,points[1:]))
            assert all(sum(p['dram_actions_bits'].values())==p['traffic_bytes']*8 for p in points)
        count+=1
    assert count>0


def test_fresh_fixed_capacity_checks_cover_all_calibration_knees():
    root=Path(__file__).with_name('results')
    curve=json.loads((root/'cal_mm2_4_4.json').read_text())['graph']['points']
    checks=json.loads((root/'fixed_capacity_check.json').read_text())['checks']
    expected={p['capacity_bytes'] for p in curve}|{max(curve[0]['capacity_bytes'],p['capacity_bytes']-1) for p in curve}
    assert {r['capacity_bytes'] for r in checks}==expected
    for r in checks:
        assert r['reference_traffic_bytes']==r['fresh_search_traffic_bytes']
        assert r['replayed_bytes']<=r['capacity_bytes']


def test_summary_excludes_failed_and_incomplete_cases():
    root=Path(__file__).with_name('results')
    summary=json.loads((root/'summary.json').read_text())
    included={r['case'] for r in summary['cases']}
    assert len(included)==6
    for path in root.glob('*_status.json'):
        status=json.loads(path.read_text())
        assert (status['case'] in included)==(status['status']=='complete')
