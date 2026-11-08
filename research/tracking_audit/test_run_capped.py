"""Exercise real supervised child/grandchild processes; never touch other jobs."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from unittest.mock import patch

import pytest

pytest.importorskip('resource', reason='POSIX process-group watchdog requires resource and signals')

import run_capped

SCRIPT = Path(__file__).with_name('run_capped.sh')
TREE = '''
import json, os, subprocess, sys, time
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
Path(sys.argv[1]).write_text(json.dumps([os.getpid(), child.pid]))
time.sleep(60)
'''


def live(pid):
    result = subprocess.run(['ps', '-p', str(pid), '-o', 'stat='], capture_output=True, text=True)
    return result.returncode == 0 and result.stdout.strip() and not result.stdout.strip().startswith('Z')


def wait_for(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.03)
    raise AssertionError('condition did not become true before deadline')


def launch(tmp_path, code, *, cap=1, timeout=10, extra=()):
    log = tmp_path / 'run.log'
    env = dict(os.environ, NO_VLIMIT='1',
               PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'])
    proc = subprocess.Popen(
        ['bash', str(SCRIPT), str(cap), str(timeout), str(log), '--', sys.executable, '-c', code, *extra],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return proc, log


@pytest.mark.parametrize('exit_code', [0, 7])
def test_command_exit_status_is_preserved(tmp_path, exit_code):
    proc, log = launch(tmp_path, f'raise SystemExit({exit_code})')
    proc.communicate(timeout=8)
    assert proc.returncode == exit_code
    assert f'done rc={exit_code}' in log.read_text()


@pytest.mark.parametrize('sig', [signal.SIGTERM, signal.SIGINT, signal.SIGHUP])
def test_cancel_supervisor_cleans_up_entire_group(tmp_path, sig):
    ready = tmp_path / 'ready.json'
    proc, log = launch(tmp_path, TREE, extra=[str(ready)])
    pids = []
    try:
        wait_for(ready.exists)
        pids = json.loads(ready.read_text())
        proc.send_signal(sig)
        proc.communicate(timeout=8)
        assert proc.returncode == 128 + sig
        wait_for(lambda: not any(live(pid) for pid in pids))
        assert f'done rc={128 + sig}' in log.read_text()
    finally:
        if pids:
            run_capped.kill_group(pids[0])
        if proc.poll() is None:
            proc.kill()
        proc.communicate(timeout=8)


def test_timeout_cleans_up_grandchild(tmp_path):
    ready = tmp_path / 'ready.json'
    proc, log = launch(tmp_path, TREE, timeout=.5, extra=[str(ready)])
    proc.communicate(timeout=8)
    assert proc.returncode == 137
    pids = json.loads(ready.read_text())
    wait_for(lambda: not any(live(pid) for pid in pids))
    assert 'done rc=137' in log.read_text()


def test_rss_cap_still_applies_with_no_vlimit(tmp_path):
    proc, log = launch(tmp_path, 'import time; time.sleep(60)', cap=.000001)
    proc.communicate(timeout=8)
    assert proc.returncode == 137
    assert 'rss_kb=' in log.read_text()


def test_orphaned_child_is_terminated(tmp_path, monkeypatch):
    monkeypatch.setenv('NO_VLIMIT', '1')
    ready = tmp_path / 'ready.json'
    # Run with a short grace period; the CLI uses five seconds.
    code = TREE.replace('time.sleep(60)\n', '')  # only remove the parent's final sleep
    status = run_capped.supervise(1, 5, tmp_path/'run.log',
                                 [sys.executable, '-c', code, str(ready)],
                                 poll_interval=.03, orphan_grace=.1)
    assert status == 4
    pids = json.loads(ready.read_text())
    wait_for(lambda: not any(live(pid) for pid in pids))


def test_monitor_failure_is_not_mistaken_for_empty_group(tmp_path, monkeypatch):
    monkeypatch.setenv('NO_VLIMIT', '1')
    with patch.object(run_capped, 'group_rss_kib', side_effect=OSError('ps unavailable')):
        status = run_capped.supervise(1, 5, tmp_path/'run.log',
                                     [sys.executable, '-c', 'import time; time.sleep(60)'])
    assert status == 125
    assert 'supervision failed' in (tmp_path/'run.log').read_text()


def test_vlimit_only_disabled_by_one(tmp_path, monkeypatch):
    monkeypatch.setenv('NO_VLIMIT', '0')
    with patch.object(run_capped.subprocess, 'Popen', side_effect=OSError('stop before launch')) as popen:
        assert run_capped.supervise(1, 5, tmp_path/'run.log', ['unused']) == 125
    assert popen.call_args.kwargs['preexec_fn'] is not None


@pytest.mark.parametrize('value', ['0', '-1', 'nan', 'inf'])
def test_invalid_budget_rejected_before_launch(tmp_path, value):
    with pytest.raises(SystemExit) as error:
        run_capped.main([value, '1', str(tmp_path/'run.log'), '--', 'unused'])
    assert error.value.code == 2
    assert not (tmp_path/'run.log').exists()
