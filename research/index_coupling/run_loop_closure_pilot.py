"""Fresh-process runner with frozen wall/RSS bounds and complete outcomes.

python -m research.index_coupling.run_loop_closure_pilot --out NEW_DIRECTORY
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ('ffn_forward_l1_m8', 'ffn_forward_l2_m8', 'ffn_training_l1', 'fork_kki')
SECONDS = 120
RSS_KIB = 2 * 1024**2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    sources = ('loop_closure_pilot.py', 'run_loop_closure_pilot.py', 'LOOP_CLOSURE_PROTOCOL.md',
               'graph/curve.py', 'prefix_dominance_audit.py', 'simulate_nest.py', 'census_tools.py')
    manifest = dict(protocol_commit='23095cc9', pythonhashseed=0, seconds_limit=SECONDS,
                    rss_limit_kib=RSS_KIB, python_version=list(sys.version_info[:3]),
                    sources={f: hashlib.sha256((HERE / f).read_bytes()).hexdigest() for f in sources})
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    results = []

    def job(label, command, case, *parameters):
        env = dict(os.environ, PYTHONHASHSEED='0')
        command_line = [sys.executable, '-m', 'research.index_coupling.loop_closure_pilot', command, case, *parameters]
        raw_out, raw_err = args.out / (label + '.stdout'), args.out / (label + '.stderr')
        start = time.perf_counter()
        status, max_rss = 'complete', 0
        with raw_out.open('w') as out, raw_err.open('w') as err:
            proc = subprocess.Popen(command_line, stdout=out, stderr=err, env=env, cwd=ROOT)
            while proc.poll() is None:
                if time.perf_counter() - start > SECONDS:
                    status = 'timeout'
                    proc.kill()
                    break
                sample = subprocess.run(['ps', '-o', 'rss=', '-p', str(proc.pid)], capture_output=True, text=True)
                try:
                    rss = int(sample.stdout.strip())
                except ValueError:
                    rss = 0
                max_rss = max(max_rss, rss)
                if rss > RSS_KIB:
                    status = 'memory_limit'
                    proc.kill()
                    break
                time.sleep(0.1)
            returncode = proc.wait()
        stderr = raw_err.read_text().replace(str(ROOT), '<repo>')
        stdout = raw_out.read_text().replace(str(ROOT), '<repo>')
        raw_err.write_text(stderr)
        raw_out.write_text(stdout)
        if returncode and status == 'complete':
            status = 'error'
        record = dict(job=label, command=command, case=case, parameters=list(parameters),
                      status=status, returncode=returncode, elapsed_seconds=time.perf_counter()-start,
                      sampled_peak_rss_mib=max_rss/1024)
        if status == 'complete':
            try:
                record['result'] = json.loads(stdout.strip().splitlines()[-1])
            except (ValueError, IndexError):
                record['status'] = 'invalid_output'
        if stderr:
            record['error_tail'] = stderr.splitlines()[-1]
        results.append(record)
        (args.out / (label + '.json')).write_text(json.dumps(record, indent=2) + '\n')
        with (args.out / 'jobs.jsonl').open('a') as stream:
            stream.write(json.dumps(record) + '\n')
        short = dict(job=label, status=record['status'])
        if 'result' in record:
            r = record['result']
            short.update({k: r[k] for k in ('seconds', 'construction_seconds', 'max_labels', 'state_pairs') if k in r})
        print(json.dumps(short), flush=True)
        return record

    census_ok = {}
    for case in CASES:
        rows = [job(f'A_{case}_{depth}', 'census', case, depth) for depth in ('2', '3', '4', 'full')]
        census_ok[case] = all(r['status'] == 'complete' for r in rows)
    control_a = job('A_prefix_control_full', 'census', 'prefix_control', 'full')
    validation, references = {}, {}
    for case in ('prefix_control', *CASES):
        if (case == 'prefix_control' and control_a['status'] != 'complete') or (case in CASES and not census_ok[case]):
            validation[case] = False
            continue
        base = job(f'V_{case}_baseline', 'solve', case, 'baseline', 'witness')
        fast = job(f'V_{case}_factorized', 'solve', case, 'factorized', 'witness')
        ok = base['status'] == fast['status'] == 'complete'
        if ok:
            references[case] = base['result']['frontier']
            ok = fast['result']['frontier'] == references[case]
        validation[case] = ok
    for case in CASES:
        if not validation.get(case) or not validation.get('prefix_control'):
            continue
        for witness in ('frontier', 'witness'):
            for repeat in range(3):
                modes = ('baseline', 'factorized') if repeat % 2 == 0 else ('factorized', 'baseline')
                for mode in modes:
                    job(f'B_{case}_{witness}_{repeat}_{mode}', 'solve', case, mode, witness)

    scores = []
    for case in CASES:
        for witness in ('frontier', 'witness'):
            modes = {}
            for mode in ('baseline', 'factorized'):
                rows = [r for r in results if r['job'].startswith(f'B_{case}_{witness}_')
                        and r['parameters'][0] == mode]
                valid = len(rows) == 3 and all(r['status'] == 'complete' and r['result']['frontier'] == references.get(case) for r in rows)
                if not valid:
                    modes[mode] = dict(complete=False, attempts=len(rows))
                    continue
                values = [r['result'] for r in rows]
                assert all(v['work'] == values[0]['work'] and v['caches'] == values[0]['caches'] and
                           v['closure_work'] == values[0]['closure_work'] for v in values)
                modes[mode] = dict(complete=True, median_seconds=statistics.median(v['seconds'] for v in values),
                                   peak_rss_mib=max(v['peak_rss_mib'] for v in values),
                                   work=values[0]['work'], caches=values[0]['caches'],
                                   closure_work=values[0]['closure_work'],
                                   response_cache_misses_total=values[0]['response_cache_misses_total'])
            row = dict(case=case, timing=witness, modes=modes, continuation_pass=False)
            if all(modes[m]['complete'] for m in modes):
                b, f = modes['baseline'], modes['factorized']
                row.update(speedup=b['median_seconds']/f['median_seconds'], rss_ratio=f['peak_rss_mib']/b['peak_rss_mib'])
                row['continuation_pass'] = f['median_seconds'] <= .8*b['median_seconds'] and row['rss_ratio'] <= 2
            scores.append(row)
    primary = [r for r in scores if r['case'] in CASES[:2]]
    score = dict(validation=validation, cases=scores,
                 continuation_pass=len(primary) == 4 and all(r['continuation_pass'] for r in primary),
                 rule='At least 20% lower median time in both timing modes on both M8 cases, RSS <= 2x, exact curves and replay.')
    (args.out / 'score.json').write_text(json.dumps(score, indent=2) + '\n')
    print(json.dumps(dict(done=True, continuation_pass=score['continuation_pass'], validation=validation)), flush=True)


if __name__ == '__main__':
    main()
