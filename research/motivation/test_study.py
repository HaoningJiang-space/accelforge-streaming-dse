import json
from pathlib import Path
from research.motivation.summarize import summarize


def test_zero_loops_does_not_mean_dram_materialization():
    path=Path(__file__).with_name('results')/'semantics.json'
    points={r['mode']:r for r in json.loads(path.read_text())['points']}
    def action(mode,op,kind):
        return points[mode]['dram_actions_bits'].get(f'{op}<SEP>action<SEP>MainMemory<SEP>T1<SEP>{kind}',0)
    for mode in ('graph','zero_loops'):
        assert action(mode,'Matmul0','write')==action(mode,'Matmul1','read')==0
    assert action('materialized','Matmul0','write')==256
    assert action('materialized','Matmul1','read')==256


def test_ties_report_range_without_favorable_tie_break():
    rows=[]
    for shape,graph,layer in [([2,8],10,20),([4,4],12,20),([8,2],9,21)]:
        for mode,edp in [('graph',graph),('materialized',layer)]:
            rows.append(dict(shape=shape,capacity_bytes=64,mode=mode,edp=edp,feasible=True,seconds=1))
    result=summarize(dict(case='unit',capacities=[64],points=rows))['capacities'][0]
    assert result['materialized_winners']==[[2,8],[4,4]]
    assert result['best_tie_regret']==10/9-1
    assert result['worst_tie_regret']==12/9-1
    assert result['graph_winners']==[[8,2]]
    assert result['near_tie_shortlists'][1]['best_after_graph_remap']==0


def test_reference_failure_not_hidden():
    rows=[dict(shape=[2,8],capacity_bytes=64,mode=mode,edp=edp,feasible=True,seconds=1)
          for mode,edp in [('graph',20),('materialized',10)]]
    assert summarize(dict(case='unit',capacities=[64],points=rows))['capacities'][0]['status']=='reference_inconsistency'


def test_checkpoint_cannot_be_reported_as_complete():
    row=dict(shape=[2,8],capacity_bytes=64,mode='graph',edp=10,feasible=True,seconds=1)
    assert summarize(dict(case='unit',capacities=[64],shapes=[[2,8]],points=[row]))['capacities'][0]['status']=='incomplete_grid'


def test_saved_grids_have_materialized_boundaries_and_capacity_witnesses():
    root=Path(__file__).with_name('results')
    for name,n in [('2mm_grid',2),('3mm_grid',3),('2mm_threshold',2),('2mm_edge',2)]:
        report=json.loads((root/f'{name}.json').read_text())
        assert len(report['points'])==len(report['shapes'])*len(report['capacities'])*2
        for row in report['points']:
            assert row['feasible']
            assert 0<row['reservations_bits']['reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right']<=row['capacity_bytes']*8
            if row['mode']=='materialized':
                assert row['materialized_replays_on_graph_target']
                for i in range(1,n):
                    actions=row['dram_actions_bits']
                    assert actions[f'Matmul{i-1}<SEP>action<SEP>MainMemory<SEP>T{i}<SEP>write']>=1024
                    assert actions[f'Matmul{i}<SEP>action<SEP>MainMemory<SEP>T{i}<SEP>read']>=1024


def test_threshold_mechanisms_in_saved_native_replay():
    data=json.loads((Path(__file__).with_name('results')/'2mm_edge.json').read_text())
    graph={(tuple(r['shape']),r['capacity_bytes']):r for r in data['points'] if r['mode']=='graph'}
    def traffic(row,tensor):
        return sum(v for k,v in row['dram_actions_bits'].items() if f'<SEP>{tensor}<SEP>' in k)/8
    before,after=(graph[((4,4),c)] for c in (175,176))
    assert traffic(before,'T1')==traffic(after,'T1')==0
    assert traffic(before,'T0')==256 and traffic(after,'T0')==128
    assert traffic(before,'T2')==384 and traffic(after,'T2')==128
    assert after['reservations_bits']['reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right']==176*8
    before,after=(graph[((2,8),c)] for c in (207,208))
    assert traffic(before,'T1')==256 and traffic(after,'T1')==0
    assert after['reservations_bits']['reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right']==208*8
