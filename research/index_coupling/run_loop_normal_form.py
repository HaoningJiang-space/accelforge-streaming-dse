"""Frozen proof checks; execute on the designated experiment machine."""
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
from time import perf_counter

from .loop_normal_form import (depth_bound, flatten, loop_counts,
                               normalize_witness, refine_once)
from .nest_model import Graph, attention, coupling, ffn
from .simulate_nest import Specification, parse_witness, simulate


SHAPES = ((2,2,2,2), (4,2,4,2), (4,4,4,4),
          (2,4,4,2), (3,2,3,2), (6,2,4,2))
FIELDS = ('peak', 'traffic', 'reads', 'writes', 'steps', 'outputs_checked')


def cases():
    for shape in SHAPES:
        for cross in (False, True):
            yield f'fork_{shape}_{cross}', coupling(*shape, cross)
    mm = [('MM', {'A': ('I','J'), 'B': ('J','K'), 'C': ('I','K')})]
    yield 'matmul_4', Graph(dict(I=4,J=4,K=4), mm)
    yield 'chain_2', Graph(dict(I=2,J=2,K=2,L=2), [
        ('P', {'A': ('I','J'), 'B': ('J','K'), 'X': ('I','K')}),
        ('C', {'X': ('I','K'), 'D': ('K','L'), 'Y': ('I','L')})])
    yield 'attention_elementwise_proxy_2', attention(2,2,2,2)
    yield 'ffn_alias_proxy_2_1_2', ffn(2,1,2)


def allowed_grid(spec, witness):
    """Check actual halving/divisor domain, beyond the parser's divisibility check."""
    def visit(node, ext):
        if node.kind == 'loop':
            choices, b = set(), ext[node.variable] // 2
            while b:
                if ext[node.variable] % b == 0:
                    choices.add(b)
                b //= 2
            assert node.tile in choices
            visit(node.children[0], dict(ext, **{node.variable: node.tile}))
        else:
            for child in node.children:
                visit(child, ext)
    visit(parse_witness(spec, witness), dict(spec.sizes))


def evaluate(index):
    from .curve_model import curve
    name, graph = list(cases())[index]
    spec = Specification(graph)
    started = perf_counter()
    points = curve(graph, witness=True)
    totals = dict(points=0, transformed=0, loops_before=0, loops_after=0,
                  max_depth_before=0, max_depth_after=0, injected_refinements=0)
    for peak, traffic, witness in points:
        original = simulate(graph, witness)
        assert original['peak'] <= peak and original['traffic'] <= traffic
        normalized = normalize_witness(graph, witness)
        assert normalize_witness(graph, normalized) == normalized
        allowed_grid(spec, normalized)
        actual = simulate(graph, normalized)
        assert all(original[k] == actual[k] for k in FIELDS), (name, original, actual)
        before = loop_counts(parse_witness(spec, witness))
        after = loop_counts(parse_witness(spec, normalized))
        assert after[0] <= before[0] and after[1] <= depth_bound(spec)
        totals['points'] += 1
        totals['transformed'] += int(normalized != witness)
        totals['loops_before'] += before[0]
        totals['loops_after'] += after[0]
        totals['max_depth_before'] = max(totals['max_depth_before'], before[1])
        totals['max_depth_after'] = max(totals['max_depth_after'], after[1])
        refined, changed = refine_once(spec, parse_witness(spec, witness))
        if changed:
            injected = flatten(spec, refined)
            allowed_grid(spec, injected)
            injected_actual = simulate(graph, injected)
            reduced = normalize_witness(graph, injected)
            reduced_actual = simulate(graph, reduced)
            assert all(original[k] == injected_actual[k] == reduced_actual[k] for k in FIELDS)
            assert loop_counts(parse_witness(spec, reduced))[0] < loop_counts(refined)[0]
            totals['injected_refinements'] += 1
    return dict(kind='case', index=index, name=name, **totals,
                proven_depth_bound=depth_bound(spec), seconds=perf_counter()-started,
                passed=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', type=int)
    args = parser.parse_args()
    if args.case is not None:
        resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
        try:
            result = evaluate(args.case)
        except Exception as exc:
            result = dict(kind='case', index=args.case, passed=False,
                          error=str(exc).replace(str(Path.cwd()), '<repo>'),
                          error_type=type(exc).__name__)
        print(json.dumps(result), flush=True)
        return
    print(json.dumps(dict(kind='metadata',
        commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
        tracked_dirty=bool(subprocess.check_output(['git','diff','--name-only','HEAD'], text=True)),
        cases=len(list(cases())), python=sys.version.split()[0],
        hash_seed=os.environ.get('PYTHONHASHSEED'), reference_generation=True,
        normalizer_uses_cost_model=False,
        purpose='witness normalization validation; no search acceleration claimed')), flush=True)
    for i in range(len(list(cases()))):
        try:
            run = subprocess.run([sys.executable, '-B', '-m',
                                  'research.index_coupling.run_loop_normal_form', '--case', str(i)],
                                 capture_output=True, text=True, timeout=120)
            if run.returncode:
                record = dict(kind='case', index=i, passed=False, returncode=run.returncode,
                              error=run.stderr[-1500:].replace(str(Path.cwd()), '<repo>'))
            else:
                record = json.loads(run.stdout)
        except subprocess.TimeoutExpired:
            record = dict(kind='case', index=i, passed=False, error='120-second timeout')
        print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
