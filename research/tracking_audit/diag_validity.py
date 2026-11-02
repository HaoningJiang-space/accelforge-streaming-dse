"""Does the shared search report the true GlobalBuffer reservation of its chosen mappings?

usage: diag_validity.py M,G,C CAP1,CAP2,... VARIANT
VARIANT: var   = RESOURCE_USAGE, AF_VARIABLE_RESOURCES=GlobalBuffer during the join (tag1 shared search)
         novar = plain RESOURCE_USAGE
         push  = var + AF_GENERATION_VARIABLE_RESOURCES=GlobalBuffer during generation
For each capacity, picks the best-EDP row that fits and re-evaluates its mapping at the largest
capacity, so the true reservation can be compared with the reported one.
"""
import copy, json, os, sys, time
from pathlib import Path
import accelforge as af
from accelforge.mapper.FFM.main import make_pmappings, join_pmappings
from accelforge.model.main import evaluate_mapping

root = Path(__file__).resolve().parents[2]
af.set_n_parallel_jobs(1)
shape = [int(x) for x in sys.argv[1].split(',')]
caps = [float(x) for x in sys.argv[2].split(',')]
variant = sys.argv[3]
MAXCAP = max(caps)
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
if variant == 'push':
    os.environ['AF_GENERATION_VARIABLE_RESOURCES'] = 'GlobalBuffer'
t = time.time()
pm = make_pmappings(build(MAXCAP, RU), print_number_of_pmappings=False)
os.environ.pop('AF_GENERATION_VARIABLE_RESOURCES', None)
if variant in ('var', 'push'):
    os.environ['AF_VARIABLE_RESOURCES'] = 'GlobalBuffer'
res = join_pmappings(pm)
os.environ.pop('AF_VARIABLE_RESOURCES', None)
print('SEARCH', json.dumps({'variant': variant, 'shape': shape, 'seconds': time.time() - t,
                            'rows': len(res.data)}), flush=True)

d = res.data
for cap in caps:
    fit = d[d[GB] <= cap / MAXCAP * (1 + 1e-12)]
    if fit.empty:
        print('CAP', json.dumps({'cap_mib': cap, 'fit': 0}), flush=True)
        continue
    edp = fit['Total<SEP>energy'] * fit['Total<SEP>latency']
    row = fit.loc[edp.idxmin()]
    rec = {'cap_mib': cap, 'fit': len(fit), 'edp': float(edp.min()),
           'reported_gb_mib': float(row[GB]) * MAXCAP, 'reported_energy': float(row['Total<SEP>energy'])}
    try:
        s = build(MAXCAP, RU)
        s.model.metrics = RU
        s.mapping = copy.deepcopy(row['Total<SEP>mapping']())
        ev = evaluate_mapping(s).data
        rec.update(true_gb_mib=float(ev[GB].iloc[0]) * MAXCAP, true_energy=float(ev['Total<SEP>energy'].iloc[0]))
        rec['valid_at_cap'] = rec['true_gb_mib'] <= cap * (1 + 1e-12)
    except Exception as e:
        rec.update(reeval_error=f'{type(e).__name__}: {str(e)[:200]}')
    print('CAP', json.dumps(rec), flush=True)
