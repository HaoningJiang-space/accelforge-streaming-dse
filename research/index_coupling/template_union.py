"""Per family: templates used at each extent, new ones, and the cumulative union."""
import json
from pathlib import Path
import sys


def main(out):
    rows = [json.loads(p.read_text()) for p in sorted(Path(out).glob('*_s*.json'))]
    for family in dict.fromkeys(r['family'] for r in rows):
        seen = set()
        for r in sorted((r for r in rows if r['family'] == family), key=lambda r: r['extent']):
            if r['status'] != 'complete':
                print(f"{family:8} s={r['extent']:<4} {r['status']} after {r['seconds']} s")
                continue
            used = {json.dumps(t) for t in r['template_list']}
            new = used - seen
            seen |= used
            print(f"{family:8} s={r['extent']:<4} points={r['points']:<4} templates={len(used):<3} "
                  f"new={len(new):<3} union={len(seen):<3} seconds={r['seconds']}")


if __name__ == '__main__':
    main(sys.argv[1])
