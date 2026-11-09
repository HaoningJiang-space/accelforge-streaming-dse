"""Archived FFM frontiers used as references (no AccelForge run needed)."""
import json
from pathlib import Path

from research.index_coupling.graph.model import attention, coupling, ffn

RESULTS = Path(__file__).resolve().parent.parent / 'results'

COUPLING_SHAPES = {'n4': (4,) * 4, 'n8': (8,) * 4, 'n16': (16,) * 4, 'T1': (32,) * 4, 'T2': (64, 8, 8, 8),
                   'T3': (8, 32, 32, 32), 'C1': (16, 4, 32, 8), 'C2': (8, 16, 4, 32)}


def cases():
    # (name, graph, FFM frontier) for the 16 coupling and 3 attention cases.
    for key, dims in COUPLING_SHAPES.items():
        for variant in ('same', 'cross'):
            report = json.loads((RESULTS / f'{key}_{variant}.json').read_text())
            yield f'{key} {variant}', coupling(*dims, variant == 'cross'), \
                [(p['capacity_bytes'], p['traffic_bytes']) for p in report['graph']['points']]
    for line in (RESULTS / 'attention_heldout.jsonl').read_text().splitlines():
        record = json.loads(line)
        d = record['dims']
        yield f"attention {d['M']},{d['P']},{d['E']},{d['F']}", attention(d['M'], d['P'], d['E'], d['F']), \
            [tuple(p) for p in record['frontier']]


def ffn_case():
    for line in (RESULTS / 'upstream_nodetail.jsonl').read_text().splitlines():
        record = json.loads(line)
        if record['case'] == 'ffn_full_copy':
            return 'FFN M8 D4 F8', ffn(8, 4, 8), [tuple(p) for p in record['frontier']]
