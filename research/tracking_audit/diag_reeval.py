"""Why does the shared-search best mapping at CAP fail re-evaluation?

usage: diag_reeval.py M,G,C CAP MAXCAP
Runs the join-only shared search at MAXCAP, picks the best row that fits CAP, prints all of its
resource columns, and re-evaluates the mapping at CAP, CAP*(1+1e-9), CAP*1.01 and MAXCAP.
Failure only at CAP points to a boundary comparison; failure everywhere points to reconstruction.
"""
import copy, json, os, sys, traceback
from pathlib import Path
import accelforge as af
from accelforge.mapper.FFM.main import make_pmappings, join_pmappings
from accelforge.model.main import evaluate_mapping

root = Path(__file__).resolve().parents[2]
af.set_n_parallel_jobs(1)
shape = [int(x) for x in sys.argv[1].split(',')]
CAP, MAXCAP = float(sys.argv[2]), float(sys.argv[3])
EL = af.Metrics.ENERGY | af.Metrics.LATENCY
RU = EL | af.Metrics.RESOURCE_USAGE
GB = 'reservation<SEP>GlobalBuffer<SEP>0<SEP>right'


def build(cap, metrics):
    spec = af.Spec.from_yaml(root/'examples/arches/tpu_v4i.yaml', root/'research/streaming_join/glu_tag1.yaml',
                             jinja_parse_data=dict(zip(('M', 'G', 'C'), shape)))
    spec.arch.find('GlobalBuffer').size = cap * 1024 * 1024 * 8
    spec.mapper.ffm.metrics = metrics
    return spec


for k in ('AF_VARIABLE_RESOURCES', 'AF_GENERATION_VARIABLE_RESOURCES'):
    os.environ.pop(k, None)
pm = make_pmappings(build(MAXCAP, RU), print_number_of_pmappings=False)
os.environ['AF_VARIABLE_RESOURCES'] = 'GlobalBuffer'
res = join_pmappings(pm)
os.environ.pop('AF_VARIABLE_RESOURCES')

d = res.data
fit = d[d[GB] <= CAP / MAXCAP * (1 + 1e-12)]
edp = fit['Total<SEP>energy'] * fit['Total<SEP>latency']
row = fit.loc[edp.idxmin()]
cols = [c for c in d.columns if c != 'Total<SEP>mapping' and not callable(row[c])]
print('ROW', json.dumps({c: (float(row[c]) if isinstance(row[c], (int, float)) else str(row[c])) for c in cols}), flush=True)
print('COLUMNS', json.dumps(list(d.columns)), flush=True)
mapping = row['Total<SEP>mapping']()

for cap in (CAP, CAP * (1 + 1e-9), CAP * 1.01, MAXCAP):
    for name, m in (('cost', EL), ('resources', RU)):
        try:
            s = build(cap, m)
            s.model.metrics = m
            s.mapping = copy.deepcopy(mapping)
            ev = evaluate_mapping(s)
            vals = {c: float(ev.data[c].iloc[0]) for c in ev.data.columns
                    if c.startswith('reservation<SEP>') or (c.startswith('Total<SEP>') and c != 'Total<SEP>mapping')}
            print('REEVAL', json.dumps({'cap_mib': cap, 'metrics': name, 'values': vals}), flush=True)
        except Exception as e:
            print('REEVAL_ERROR', json.dumps({'cap_mib': cap, 'metrics': name, 'type': type(e).__name__,
                                              'msg': str(e)[:300], 'where': traceback.format_exc()[-600:]}), flush=True)
