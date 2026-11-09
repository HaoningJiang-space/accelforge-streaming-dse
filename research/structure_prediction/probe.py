"""Small smoke test for an explicit modern Snowcat spec."""
import json
from pathlib import Path
from research.tracking_audit import common


def main():
    common.set_jobs(1)
    spec=common.af.Spec.from_yaml(Path(__file__).with_name('snowcat.yaml'),
        common.ROOT/'examples/workloads/matmuls.yaml',jinja_parse_data=dict(N_EINSUMS=2,M=4,KN=4))
    spec.mapper.ffm.metrics=common.af.Metrics.ENERGY | common.af.Metrics.RESOURCE_USAGE
    spec.model.metrics=spec.mapper.ffm.metrics
    spec.arch.find('GlobalBuffer').size=1024*8
    result,stats=common.search(spec,gen_env={'AF_GENERATION_VARIABLE_RESOURCES':'GlobalBuffer'},
                               join_env={'AF_VARIABLE_RESOURCES':'GlobalBuffer'})
    data=result.data
    print('COLUMNS',list(data.columns),flush=True)
    cols=['Total<SEP>energy','reservation_bits<SEP>GlobalBuffer<SEP>0<SEP>right']
    print(data[cols].to_string(index=False),flush=True)
    Path('research/structure_prediction/results/probe.json').write_text(json.dumps(dict(stats=stats,front=data[cols].to_dict('records')),indent=2)+'\n')


if __name__=='__main__':
    main()
