"""Print a compact table of one or more capacity_audit.py logs.

usage: summarize_audit.py LOG [LOG ...]

For each log: the case, the watchdog status, and per capacity the EDP of each variant
with flags for invalid (!), suboptimal (<) and min_usage shortfall (~) picks, then the
median search seconds and speedups. A log without a SUMMARY line (the run crashed or was
killed) shows its last error line instead.
"""
import json
import sys


def read(path):
    def empty():
        return {'RUN': [], 'watchdog': None, 'last': None, 'parse_errors': []}

    lines = empty()
    with open(path) as f:
        for number, line in enumerate(f, 1):
            line = line.rstrip('\n').lstrip('\r')
            kind, _, rest = line.partition(' ')
            if kind in ('CONFIG', 'RUN', 'SUMMARY'):
                if kind == 'CONFIG':
                    # Appended runs must not inherit an earlier run's successful
                    # SUMMARY or watchdog status if the latest run crashes.
                    lines = empty()
                try:
                    record = json.loads(rest)
                    if not isinstance(record, dict):
                        raise ValueError('record must be a JSON object')
                except (ValueError, TypeError) as error:
                    lines['parse_errors'].append(f'line {number}: {kind}: {error}')
                    lines['last'] = line
                    if kind == 'SUMMARY':
                        lines.pop('SUMMARY', None)
                    continue
                if kind == 'RUN':
                    lines['RUN'].append(record)
                else:
                    lines[kind] = record
            elif line.startswith('[watchdog] done'):
                lines['watchdog'] = line[len('[watchdog] '):]
            elif line.strip():
                lines['last'] = line.strip()
    return lines


def flags(q, v):
    return ''.join(f for f, key in (('!', 'invalid'), ('<', 'suboptimal'), ('~', 'min_usage_shortfall'))
                   if v in q.get(key, []))


def show(path):
    log = read(path)
    s = log.get('SUMMARY')
    # Logs before the Case refactor (1cd29857) record GLU's 'shape' instead of 'case'.
    case = s.get('case', f'glu{tuple(s.get("shape", ()))}@tpu_v4i') if s else '?'
    print(f'== {path}: {case}  [{log["watchdog"]}]')
    for error in log['parse_errors']:
        print(f'   incomplete/corrupt record: {error}')
    if s is None:
        print(f'   no SUMMARY; {len(log["RUN"])} RUN lines; last line: {log["last"]}')
        return
    variants = list(s['median_seconds'])
    print('   cap_mib  ' + '  '.join(f'{v:>14}' for v in variants))
    for cap, q in s['quality'].items():
        cells = [f'{q["edp"][v]:.6e}{flags(q, v):<3}' if q['edp'][v] is not None else f'{"none":>12}{flags(q, v):<3}'
                 for v in variants]
        print(f'   {cap:>7}  ' + '  '.join(f'{c:>14}' for c in cells))
    speed = s.get('speedup_vs_indep', {})
    print('   median s ' + '  '.join(f'{v}={s["median_seconds"][v]:.1f}'
                                     + (f' ({speed[v]:.2f}x)' if v in speed else '') for v in variants))
    fields = [('valid', 'all_picks_valid'), ('consistent', 'all_repeats_consistent'),
              ('best_known', 'all_picks_best_known'), ('usage_checked', 'all_min_usage_checks_completed')]
    # Historical logs did not record every flag. Missing means unknown, not passed.
    print('   ' + ' '.join(f'{label}={s.get(key, "unknown")}' for label, key in fields))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for p in sys.argv[1:]:
        show(p)
