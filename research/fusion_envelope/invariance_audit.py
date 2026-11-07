"""Independent physical extraction: verify RHS-only model-family invariance."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch

from research.tracking_audit import common
from research.joint_budget.analytic_bounds import factor_domain
from . import native


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()


def run(output):
    case = common.Case('attention','nvdla',(128,1,64))
    shapes = sorted({(p.px,p.py) for p in factor_domain().points})
    # A virtual envelope is audited separately; it is not a physical candidate.
    shapes.append((6144,6144))
    anchor,records = None,[]
    started = time.perf_counter()
    original_build = native.build
    try:
        for policy in ('original','relaxed'):
            def build(*args,**kwargs):
                spec = original_build(*args,**kwargs)
                if policy=='relaxed':
                    for dim in spec.arch.find('ArrayFanout').spatial:
                        dim.min_usage = 0
                return spec
            for shape in shapes:
                for capacity in (4096,32768):
                    # Fresh envelope disables both raw-catalog and symbolic
                    # model reuse. Every physical source is actually extracted.
                    env = native.NativeEnvelope(case)
                    with patch.object(native,'build',build):
                        env.prepare(shape,capacity)
                    if env.stats['unsupported']:
                        raise AssertionError(f'unsupported native extraction: {env.unsupported}')
                    content = dict(catalog=env.catalogs[shape],models=env.serialize_models(),
                        source={key:prepared[0].source_contract for key,prepared in env.models.items()})
                    digest = fingerprint(content)
                    if anchor is None:
                        anchor = (digest,content)
                    if digest!=anchor[0]:
                        mismatch = {section:fingerprint(content[section]) for section in content}
                        raise AssertionError(f'RHS-only invariance fails: {policy}, {shape}, {capacity}: {mismatch}')
                    records.append(dict(policy=policy,shape=shape,capacity_bytes=capacity,
                        virtual_envelope=shape==(6144,6144),fingerprint=digest,
                        ordinary_templates=env.stats['raw_instances'],all_symbolic_models_equal=True))
                    print(json.dumps(dict(checked=len(records),policy=policy,shape=shape,
                        capacity_bytes=capacity,elapsed_s=time.perf_counter()-started)),flush=True)
        report = dict(status='complete',source_scope='frozen Attention128 native model',
            records=records,anchor=anchor[1],fingerprint=anchor[0],
            raw_catalog_equal=True,normalized_symbolic_costs_equal=True,
            factor_capacity_spatial_constraints_equal=True,matrices_objectives_upper_bounds_equal=True,
            only_rhs_varies=True,elapsed_s=time.perf_counter()-started,
            policy_coverage='both original and relaxed; every 6144-PE factor pair, two SRAM endpoints, virtual envelope')
    except Exception as error:
        report = dict(status='failed',records=records,error=f'{type(error).__name__}: {error}',
            elapsed_s=time.perf_counter()-started,anchor_fingerprint=anchor[0] if anchor else None)
        raise
    finally:
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,default=str,separators=(',',':'))+'\n',encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    run(args.output)


if __name__=='__main__':
    main()
