"""Plain-GEMM fidelity of the capacity-traffic model on repaired PyTorchSim.

Protocol: GEMM_FIDELITY_PROTOCOL.md (frozen before any run of this module).

The PyTorchSim GEMM template tiles M and N outside, K inside, and keeps the
output tile stationary. For tile (tm, tn, tk), without subtile splits:
- predicted useful DRAM bytes = 4 (M K N/tn + K N M/tm + M N);
- predicted scratchpad cells per lane (lane padding to 128) =
  tm r(tk)/128 + tk r(tn)/128 + tm r(tn)/128, with r(x) = 128 ceil(x/128).
Neither depends on cycles. tk does not enter the traffic at all.

Commands:
  plan OUT.json            enumerate the frozen cases and their predictions
  run PLAN.json DIR        run every case not yet present in DIR (serial)
  score PLAN.json DIR      score accepted runs against the predictions
"""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

# Real layer GEMMs, (M, N, K): Y[M,N] = X[M,K] W[K,N].
SHAPES = {
    'bert_qkv': (128, 768, 768),        # BERT-base, sequence 128, Q/K/V or output projection
    'bert_ffn_up': (128, 3072, 768),     # BERT-base FFN 768 -> 3072
    'bert_ffn_down': (128, 768, 3072),   # BERT-base FFN 3072 -> 768
    'resnet_c3': (784, 512, 128),        # ResNet-50 stage 3 1x1 conv, 28x28 -> GEMM
    'resnet_c2': (3136, 256, 64),        # ResNet-50 stage 2 1x1 conv, 56x56 -> GEMM
}
BUDGETS = (128, 512, 2048, 8192)  # scratchpad cells per lane (x 128 lanes x 4 bytes)
LANES, BYTES = 128, 4


def tiles(n):
    """Tile values: powers of two >= 8 dividing n, and n itself."""
    out = {n}
    t = 8
    while t < n:
        if n % t == 0:
            out.add(t)
        t *= 2
    return sorted(out)


def pad(x):
    return LANES * math.ceil(x / LANES)


def cells(tile):
    tm, tn, tk = tile
    return (tm * pad(tk) + tk * pad(tn) + tm * pad(tn)) // LANES


def useful_bytes(shape, tile):
    (m, n, k), (tm, tn, tk) = shape, tile
    return BYTES * (m * k * (n // tn) + k * n * (m // tm) + m * n)


def plan():
    cases, runs = [], {}
    for name, shape in SHAPES.items():
        m, n, k = shape
        runs[f'{name}_heuristic'] = dict(shape=shape, mode='heuristic', tile=None)
        legal_all = [(tm, tn, tk) for tm in tiles(m) for tn in tiles(n) for tk in tiles(k)]
        for budget in BUDGETS:
            legal = [t for t in legal_all if cells(t) <= budget]
            if not legal:
                continue
            key = lambda t: (useful_bytes(shape, t), cells(t), -t[0], -t[1])
            model = min(legal, key=key)          # min traffic, then min capacity
            per_tk = {}
            for t in sorted(legal, key=key):
                per_tk.setdefault(t[2], t)       # best traffic for each tk
            chosen = sorted(set(per_tk.values()) | {model}, key=lambda t: t[2])
            cell = dict(shape_name=name, shape=shape, budget=budget, model_choice=model, tiles=[])
            for t in chosen:
                run = f'{name}_t{t[0]}_{t[1]}_{t[2]}'
                runs[run] = dict(shape=shape, mode='external', tile=t)
                cell['tiles'].append(dict(run=run, tile=t, predicted_useful_bytes=useful_bytes(shape, t),
                                          predicted_cells_per_lane=cells(t)))
            cases.append(cell)
    return dict(shapes=SHAPES, budgets=BUDGETS, cells=cases, runs=runs)


def run(plan_path, out_dir, seconds, bundle, overlay):
    p = json.loads(Path(plan_path).read_text())
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, r in p['runs'].items():
        target = out_dir / name
        if target.exists():
            continue
        args = [sys.executable, '-u', '-m', 'research.dnn_benchmarks.run_rootless_pilot', '--bundle', bundle,
                '--source-overlay', overlay, '--out', str(target), '--mode', r['mode'],
                '--shape', *map(str, r['shape']), '--seconds', str(seconds),
                '--backend-lock', 'repaired_backend_lock.json', '--fixed-timing-addresses']
        if r['tile']:
            args += ['--tile', *map(str, r['tile']), *map(str, r['tile'])]
        code = subprocess.run(args).returncode
        print(json.dumps(dict(run=name, exitcode=code)), flush=True)


def load(out_dir, name):
    d = Path(out_dir) / name
    try:
        launch = json.loads((d / 'launch_result.json').read_text())
        audit = json.loads((d / 'dma_audit.json').read_text())
    except (OSError, ValueError):
        return None
    return dict(launch=launch, audit=audit)


def score(plan_path, out_dir):
    p = json.loads(Path(plan_path).read_text())
    records, rejected = {}, []
    for name in p['runs']:
        rec = load(out_dir, name)
        if rec is None or not rec['audit'].get('timing_accepted') or not rec['audit'].get('numerical_equal'):
            rejected.append(name)
            continue
        records[name] = rec['audit']
    h1 = h2 = total = 0
    for c in p['cells']:
        for t in c['tiles']:
            a = records.get(t['run'])
            if a is None:
                continue
            total += 1
            h1 += a['useful_bytes'] == t['predicted_useful_bytes']
            h2 += sum(a['float_array_cells_per_lane'].values()) == t['predicted_cells_per_lane']
    h3_cells = h3_not_optimal = h3_larger_tk = 0
    per_tk_rank = []
    for c in p['cells']:
        ran = [(t, records[t['run']]) for t in c['tiles'] if t['run'] in records]
        if len(ran) < 2:
            continue
        h3_cells += 1
        best = min(ran, key=lambda x: x[1]['total_cycles'])
        model = next((x for x in ran if tuple(x[0]['tile']) == tuple(c['model_choice'])), None)
        if model is None:
            continue
        if best[1]['total_cycles'] < model[1]['total_cycles']:
            h3_not_optimal += 1
            h3_larger_tk += best[0]['tile'][2] >= model[0]['tile'][2]
    # H4: within one shape and one tk, rank agreement of traffic and cycles.
    groups = {}
    for name, a in records.items():
        r = p['runs'][name]
        if r['tile']:
            groups.setdefault((tuple(r['shape']), r['tile'][2]), {})[tuple(r['tile'])] = a
    for (shape, tk), runs in groups.items():
        pts = [(useful_bytes(shape, t), a['total_cycles']) for t, a in runs.items()]
        if len(pts) >= 3:
            per_tk_rank.append(spearman(pts))
    heuristic = {}
    for name in p['runs']:
        if name.endswith('_heuristic') and name in records:
            a = records[name]
            heuristic[name] = dict(cycles=a['total_cycles'], useful_bytes=a['useful_bytes'],
                                   cells_per_lane=sum(a['float_array_cells_per_lane'].values()))
    return dict(accepted=len(records), rejected=rejected,
                h1_traffic_exact=f'{h1}/{total}', h2_cells_exact=f'{h2}/{total}',
                h3=dict(cells=h3_cells, model_not_cycle_optimal=h3_not_optimal,
                        cycle_optimal_has_tk_at_least_model=h3_larger_tk),
                h4_spearman_by_shape_tk=sorted(round(x, 3) for x in per_tk_rank),
                heuristic=heuristic)


def spearman(pts):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for t in range(i, j + 1):
                r[order[t]] = (i + j) / 2
            i = j + 1
        return r
    x, y = ranks([p[0] for p in pts]), ranks([p[1] for p in pts])
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return sxy / (sx * sy) if sx and sy else float('nan')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('plan').add_argument('out')
    r = sub.add_parser('run')
    r.add_argument('plan')
    r.add_argument('out_dir')
    r.add_argument('--seconds', type=int, default=900)
    r.add_argument('--bundle', required=True)
    r.add_argument('--source-overlay', required=True)
    s = sub.add_parser('score')
    s.add_argument('plan')
    s.add_argument('out_dir')
    a = p.parse_args()
    if a.command == 'plan':
        Path(a.out).write_text(json.dumps(plan(), indent=1) + '\n')
    elif a.command == 'run':
        run(a.plan, a.out_dir, a.seconds, a.bundle, a.source_overlay)
    else:
        print(json.dumps(score(a.plan, a.out_dir), indent=1))


if __name__ == '__main__':
    main()
