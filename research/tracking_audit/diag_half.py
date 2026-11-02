"""Half-scale GLU: is the shared-search EDP below independent FFM real (valid mapping) or an artifact?
A shared (RU + AF_VARIABLE_RESOURCES=GlobalBuffer at max cap) -> filter -> re-evaluate best at CAP
B independent ENERGY|LATENCY at CAP
C independent ENERGY|LATENCY|RESOURCE_USAGE at CAP
"""
import copy, json, os, sys, time
from pathlib import Path
import accelforge as af
from accelforge.mapper.FFM.main import make_pmappings, join_pmappings
from accelforge.model.main import evaluate_mapping

root = Path(__file__).resolve().parents[2]
af.set_n_parallel_jobs(1)
shape = [256, 512, 1024]
CAP, MAXCAP = float(sys.argv[1]) if len(sys.argv) > 1 else 0.375, 4.0
EL = af.Metrics.ENERGY | af.Metrics.LATENCY
RU = EL | af.Metrics.RESOURCE_USAGE
GB = 'reservation<SEP>GlobalBuffer<SEP>0<SEP>right'


def build(cap, metrics):
    spec = af.Spec.from_yaml(root/'examples/arches/tpu_v4i.yaml', root/'research/streaming_join/glu_tag1.yaml',
                             jinja_parse_data=dict(zip(('M', 'G', 'C'), shape)))
    spec.arch.find('GlobalBuffer').size = cap * 1024 * 1024 * 8
    spec.mapper.ffm.metrics = metrics
    return spec


def search(spec, variable=None):
    os.environ.pop('AF_VARIABLE_RESOURCES', None)
    pm = make_pmappings(spec, print_number_of_pmappings=False)
    if variable:
        os.environ['AF_VARIABLE_RESOURCES'] = variable
    r = join_pmappings(pm)
    os.environ.pop('AF_VARIABLE_RESOURCES', None)
    return r


def best(data):
    i = (data['Total<SEP>energy'] * data['Total<SEP>latency']).idxmin()
    return data.loc[i]


def out(tag, **kw):
    print(tag, json.dumps(kw, default=float), flush=True)


def reevaluate(label, mapping, cap):
    for mname, m in (('cost', EL), ('resources', RU)):
        try:
            s = build(cap, m)
            s.model.metrics = m
            s.mapping = copy.deepcopy(mapping)
            ev = evaluate_mapping(s)
            cols = [c for c in ev.data.columns
                    if (c.startswith('Total<SEP>') and c != 'Total<SEP>mapping') or c.startswith('reservation<SEP>')]
            vals = ev.data[cols].astype(float).iloc[0].to_dict()
            out('REEVAL', label=label, cap_mib=cap, metrics=mname, values=vals,
                max_reservation=max([v for k, v in vals.items() if k.startswith('reservation')], default=None))
        except Exception as e:
            out('REEVAL_ERROR', label=label, cap_mib=cap, metrics=mname, type=type(e).__name__, msg=str(e)[:500])


t = time.time()
shared = search(build(MAXCAP, RU), variable='GlobalBuffer')
view = shared.data[shared.data[GB] <= CAP / MAXCAP * (1 + 1e-12)]
sb = best(view)
out('A_SHARED', seconds=time.time() - t, rows=len(shared.data), rows_fit=len(view),
    edp=sb['Total<SEP>energy'] * sb['Total<SEP>latency'], energy=sb['Total<SEP>energy'],
    latency=sb['Total<SEP>latency'], gb_frac_of_max=sb[GB], gb_frac_of_cap=sb[GB] * MAXCAP / CAP)
reevaluate('shared_best', sb['Total<SEP>mapping'](), CAP)

t = time.time()
ind = search(build(CAP, EL))
ib = best(ind.data)
out('B_INDEP_EL', seconds=time.time() - t, rows=len(ind.data),
    edp=ib['Total<SEP>energy'] * ib['Total<SEP>latency'], energy=ib['Total<SEP>energy'], latency=ib['Total<SEP>latency'])
reevaluate('indep_el_best', ib['Total<SEP>mapping'](), CAP)

t = time.time()
indr = search(build(CAP, RU))
rb = best(indr.data)
out('C_INDEP_RU', seconds=time.time() - t, rows=len(indr.data),
    edp=rb['Total<SEP>energy'] * rb['Total<SEP>latency'], energy=rb['Total<SEP>energy'], latency=rb['Total<SEP>latency'])
