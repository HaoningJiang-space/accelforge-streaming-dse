"""Held-out test of a frozen cycle model for selecting PyTorchSim GEMM tiles.

Protocol: GEMM_CYCLE_MODEL_PROTOCOL.md (frozen before any run of this module).

The model was fitted on the accepted runs of GEMM_FIDELITY_RESULTS.md and is
fixed here; it is never refitted on the held-out shapes:

    cycles(tile) = bytes / BETA + iterations * (LAMBDA0 + tm tn / LAMBDA1)

where bytes is the predicted useful DRAM traffic and iterations is
(M/tm)(N/tn)(K/tk). Legality (from the compile failures there): tm <= 128 or
tm a multiple of 128.

Commands:
  plan OUT.json            enumerate the frozen held-out cases and predictions
  run PLAN.json DIR        run every case not yet present in DIR (serial)
  score PLAN.json DIR      score accepted runs against the predictions
"""
import argparse
import json
from pathlib import Path

from .gemm_fidelity import BUDGETS, cells, load, run, tiles, useful_bytes

BETA, LAMBDA0, LAMBDA1 = 390, 80, 448
SYSTOLIC = 128

# Held-out real layer GEMMs, (M, N, K); none appears in GEMM_FIDELITY_PROTOCOL.md.
SHAPES = {
    'bertl_qkv': (128, 1024, 1024),       # BERT-large, sequence 128, Q/K/V projection
    'bertl_ffn_up': (128, 4096, 1024),     # BERT-large FFN 1024 -> 4096
    'bertl_ffn_down': (128, 1024, 4096),   # BERT-large FFN 4096 -> 1024
    'gpt2_qkv': (256, 2304, 768),          # GPT-2 small, sequence 256, fused QKV
    'resnet_s3_3x3': (784, 128, 1152),     # ResNet-50 stage 3 3x3 conv, im2col (28x28, 128, 128*9)
}
ILLEGAL_PROBE = ('resnet_s3_3x3', (784, 128, 64))  # predicted to fail to compile


def legal(tile):
    return tile[0] <= SYSTOLIC or tile[0] % SYSTOLIC == 0


def predicted_cycles(shape, tile):
    (m, n, k), (tm, tn, tk) = shape, tile
    iterations = (m // tm) * (n // tn) * (k // tk)
    return useful_bytes(shape, tile) / BETA + iterations * (LAMBDA0 + tm * tn / LAMBDA1)


def plan():
    cases, runs = [], {}
    for name, shape in SHAPES.items():
        m, n, k = shape
        runs[f'{name}_heuristic'] = dict(shape=shape, mode='heuristic', tile=None)
        candidates = [(tm, tn, tk) for tm in tiles(m) for tn in tiles(n) for tk in tiles(k)]
        for budget in BUDGETS:
            within = [t for t in candidates if legal(t) and cells(t) <= budget]
            if not within:
                continue
            traffic_key = lambda t: (useful_bytes(shape, t), cells(t), -t[0], -t[1])
            traffic_pick = min(within, key=traffic_key)
            model_pick = min(within, key=lambda t: (predicted_cycles(shape, t), cells(t)))
            chosen = {traffic_pick, model_pick}
            for tk in {t[2] for t in within}:
                same = [t for t in within if t[2] == tk]
                chosen.add(min(same, key=traffic_key))
                chosen.add(min(same, key=lambda t: (predicted_cycles(shape, t), cells(t))))
            cell = dict(shape_name=name, shape=shape, budget=budget, traffic_pick=traffic_pick,
                        model_pick=model_pick, tiles=[])
            for t in sorted(chosen, key=lambda t: (t[2], t[0], t[1])):
                run_name = f'{name}_t{t[0]}_{t[1]}_{t[2]}'
                runs[run_name] = dict(shape=shape, mode='external', tile=t)
                cell['tiles'].append(dict(run=run_name, tile=t, predicted_useful_bytes=useful_bytes(shape, t),
                                          predicted_cells_per_lane=cells(t),
                                          predicted_cycles=round(predicted_cycles(shape, t), 1)))
            cases.append(cell)
    name, tile = ILLEGAL_PROBE
    runs[f'{name}_t{tile[0]}_{tile[1]}_{tile[2]}_illegal_probe'] = dict(shape=SHAPES[name], mode='external',
                                                                         tile=tile, predicted_compile_failure=True)
    return dict(model=dict(beta=BETA, lambda0=LAMBDA0, lambda1=LAMBDA1, systolic=SYSTOLIC),
                shapes=SHAPES, budgets=BUDGETS, cells=cases, runs=runs)


def score(plan_path, out_dir):
    p = json.loads(Path(plan_path).read_text())
    accepted, rejected = {}, []
    for name in p['runs']:
        rec = load(out_dir, name)
        if rec and rec['audit'].get('timing_accepted') and rec['audit'].get('numerical_equal'):
            accepted[name] = rec['audit']
        else:
            rejected.append(name)
    legal_ok = sum(1 for n, r in p['runs'].items() if r['tile'] and not r.get('predicted_compile_failure')
                   and n in accepted)
    legal_total = sum(1 for r in p['runs'].values() if r['tile'] and not r.get('predicted_compile_failure'))
    probe = [n for n, r in p['runs'].items() if r.get('predicted_compile_failure')]
    probe_failed = [n for n in probe if n not in accepted]
    exact_bytes = exact_cells = errors = 0
    rel = []
    seen = set()
    for c in p['cells']:
        for t in c['tiles']:
            a = accepted.get(t['run'])
            if a is None or t['run'] in seen:
                continue
            seen.add(t['run'])
            exact_bytes += a['useful_bytes'] == t['predicted_useful_bytes']
            exact_cells += sum(a['float_array_cells_per_lane'].values()) == t['predicted_cells_per_lane']
            rel.append(abs(t['predicted_cycles'] - a['total_cycles']) / a['total_cycles'])
    rel.sort()
    ratios, speedups, rows = [], [], []
    for c in p['cells']:
        ran = {tuple(t['tile']): accepted[t['run']]['total_cycles'] for t in c['tiles'] if t['run'] in accepted}
        mp, tp = tuple(c['model_pick']), tuple(c['traffic_pick'])
        if len(ran) < 2 or mp not in ran:
            continue
        best = min(ran.values())
        ratios.append(ran[mp] / best)
        if tp in ran:
            speedups.append(ran[tp] / ran[mp])
        rows.append(dict(shape=c['shape_name'], budget=c['budget'], model_pick=mp, model_cycles=ran[mp],
                         best_cycles=best, traffic_pick=tp, traffic_cycles=ran.get(tp)))
    heuristic = {n: dict(cycles=a['total_cycles'], cells_per_lane=sum(a['float_array_cells_per_lane'].values()))
                 for n, a in accepted.items() if n.endswith('_heuristic')}
    return dict(accepted=len(accepted), rejected=rejected,
                g1_legal_compiled=f'{legal_ok}/{legal_total}', g1_illegal_probe_failed=f'{len(probe_failed)}/{len(probe)}',
                g2_bytes_exact=f'{exact_bytes}/{len(seen)}', g2_cells_exact=f'{exact_cells}/{len(seen)}',
                g3_cells=len(ratios), g3_within_1_10=sum(r <= 1.10 for r in ratios),
                g3_max_ratio=round(max(ratios), 3) if ratios else None,
                g4_cells=len(speedups), g4_at_least_1_5x=sum(s >= 1.5 for s in speedups),
                g5_median_rel_error=round(rel[len(rel) // 2], 3) if rel else None,
                g5_p90_rel_error=round(rel[int(0.9 * len(rel))], 3) if rel else None,
                per_cell=rows, heuristic=heuristic)


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
