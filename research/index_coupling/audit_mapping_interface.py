"""Source-only audit of the pinned PyTorchSim external GEMM selector.

Executes the original selector function with a recording kernel stand-in, not
the compiler or simulator. No runtime, vendor source, or integration branch is
modified. The ledger below describes the plain source template before passes.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace

PIN = '509f42554202edb29cf8d31ddf619776f465e717'
TEMPLATE = 'PyTorchSimFrontend/mlir/mlir_gemm_template.py'
SOURCES = (TEMPLATE, 'PyTorchSimFrontend/extension_config.py',
           'PyTorchSimFrontend/mlir/mlir_template.py',
           'PyTorchSimFrontend/mlir/mlir_codegen_backend.py',
           'PyTorchSimFrontend/mlir/mlir_common.py', 'AsmParser/tog_generator.py',
           'TOGSim/src/TileGraphParser.cc')
FIELDS = ('TILE_M', 'TILE_N', 'TILE_K', 'SUB_TILE_M', 'SUB_TILE_N', 'SUB_TILE_K')


def canonical_request(shape, values):
    """Conservative pilot subset; not a backend SRAM/layout feasibility check."""
    if len(shape) != 3 or any(type(n) is not int or n <= 0 for n in shape):
        raise ValueError('positive integer M,N,K required')
    if set(values) != set(FIELDS) or any(type(values[k]) is not int or values[k] <= 0 for k in FIELDS):
        raise ValueError('all six named positive integer tile fields required')
    tile, sub = [values[k] for k in FIELDS[:3]], [values[k] for k in FIELDS[3:]]
    if any(t > n or n % t for n, t in zip(shape, tile)):
        raise ValueError('pilot requires tiles dividing each dimension')
    if any(s > t or t % s for t, s in zip(tile, sub)):
        raise ValueError('pilot requires subtiles dividing each tile')
    return {'_'.join(map(str, shape)): {k: values[k] for k in FIELDS}}


def template_ledger(shape, tile, element_bytes=4):
    """Plain M,N,K template: no fusion, reuse passes, padding or DMA overlap."""
    m, n, k = shape
    tm, tn, tk = tile
    canonical_request(shape, dict(zip(FIELDS, (*tile, *tile))))
    return dict(mac_count=m*n*k,
        useful_input_elements=dict(X=m*k*(n//tn), W=k*n*(m//tm)),
        useful_output_elements=m*n,
        useful_bytes=element_bytes*(m*k*(n//tn)+k*n*(m//tm)+m*n),
        logical_buffer_bytes=element_bytes*(tm*tk+tk*tn+tm*tn),
        source_dma_operations=(m//tm)*(n//tn)*(2*(k//tk)+1),
        partial_sum_dram_reads=0, partial_sum_dram_writes=0,
        caveat='Pre-pass logical quantities, not compiled DMA/DRAM transactions or physical SRAM allocation.')


def audit(source):
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise ValueError('requires the pinned PyTorchSim revision')
    hashes = {}
    for name in SOURCES:
        raw = (source/name).read_bytes()
        committed = subprocess.check_output(['git', '-C', str(source), 'show', f'{PIN}:{name}'])
        if raw != committed:
            raise ValueError(f'modified audited source: {name}')
        hashes[name] = hashlib.sha256(raw).hexdigest()
    tree = ast.parse((source/TEMPLATE).read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MLIRGemmTemplate')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'select_tile')
    # This method has no annotations/decorators and is copied without rewriting.
    assert not method.decorator_list and not method.returns
    assert all(a.annotation is None for a in method.args.args)
    code = compile(ast.Module(body=[method], type_ignores=[]), '<pinned-select-tile>', 'exec')
    templates = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
                 if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                 and n.targets[0].id in ('GEMM_TEMPLATE', 'GEMM_REDUCTION_TEMPLATE')}
    plain = templates['GEMM_TEMPLATE']
    assert plain.index('affine.for %index0') < plain.index('affine.for %index1') < plain.index('affine.for %index2')
    assert 'accumulation_loop=true' in plain
    shape = (64, 128, 32)
    good = dict(zip(FIELDS, (16, 32, 8, 8, 16, 8)))
    key = '_'.join(map(str, shape))
    rows = []
    with TemporaryDirectory() as temp:
        path = Path(temp)/'mapping.json'
        def query(label, data, subtile=False):
            path.write_text(json.dumps(data))
            calls = []
            def heuristic(*args, **kwargs):
                calls.append(dict(args=args, kwargs=kwargs))
                return [[32, 64, 16]]
            env = dict(json=json, Path=Path, extension_config=SimpleNamespace(
                codegen_mapping_strategy='external-then-heuristic',
                codegen_external_mapping_file=str(path), CONFIG_SUBTILE=subtile))
            exec(code, env)
            row = dict(case=label, file=data, subtile_enabled=subtile)
            try:
                row['selected_candidates'] = env['select_tile'](None,
                    SimpleNamespace(vector_lane=8, gemm_combination_mapping=heuristic),
                    *shape, 0, 0, 0, 4)
            except Exception as exc:
                row['exception'] = type(exc).__name__
            row['heuristic_calls'] = len(calls)
            rows.append(row)
            return row
        ordered = query('canonical_six', {key: good}, True)
        permuted = {k: good[k] for k in ('TILE_K','TILE_N','TILE_M',*FIELDS[3:])}
        swapped = query('same_named_values_different_order', {key: permuted}, True)
        sorted_keys = query('json_sort_keys', json.loads(json.dumps({key:good}, sort_keys=True)), True)
        missing = query('shape_key_miss', {})
        three = query('three_fields_subtile', {key:{k:good[k] for k in FIELDS[:3]}}, True)
        bad = query('zero_tile_accepted_by_selector', {key:dict(good, TILE_M=0)}, True)
        oversize = query('oversize_subtile_accepted_by_selector', {key:dict(good, SUB_TILE_M=32)}, True)
        malformed = query('four_fields', {key:{k:good[k] for k in FIELDS[:4]}})
        assert ordered['selected_candidates'] == [list(good.values())]
        assert swapped['selected_candidates'] != ordered['selected_candidates']
        assert sorted_keys['selected_candidates'] != ordered['selected_candidates']
        assert missing['heuristic_calls'] == 1
        assert len(three['selected_candidates']) == 2 and three['heuristic_calls'] == 0
        assert bad['selected_candidates'][0][0] == 0 and bad['heuristic_calls'] == 0
        assert oversize['selected_candidates'][0][3] == 32
        assert malformed['exception'] == 'UnboundLocalError'
    return dict(upstream_revision=PIN, source_sha256=hashes,
        audit_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        evidence='Original select_tile function executed in isolation; template source inspected. '
                 'No PyTorch compiler, TOG execution, cycles, energy or hardware validity tested.',
        findings=dict(named_field_order_changes_selection=True, missing_shape_falls_back=True,
            three_fields_can_create_two_candidates=True, six_fields_skip_geometry_validation=True,
            plain_template_loop_order=['M','N','K'], plain_template_output_retained_across_K=True),
        cases=rows, template_only_ledger=template_ledger(shape, (16,32,8)),
        kernel_standin=dict(vector_lane=8, heuristic_result=[[32,64,16]]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.source)
    with args.out.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result['findings']))


if __name__ == '__main__':
    main()
