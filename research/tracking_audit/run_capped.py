"""POSIX process-group watchdog used by run_capped.sh (standard library only).

RSS is sampled, not a hard aggregate limit. Descendants that leave the process group
escape supervision; use a cgroup when a hard process-tree limit is required.
"""
import argparse
import math
import os
import resource
import signal
import subprocess
import time


def positive_number(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('must be finite and positive')
    return number


def group_rss_kib(pgid):
    """Return live member count and RSS, excluding zombies awaiting reaping.

    Select PGID explicitly: `ps -g` means session ID on Linux and process group on
    some other systems. A failed sample is an error, never a fictitious empty group.
    """
    output = subprocess.run(
        ['ps', '-axo', 'pgid=,rss=,stat='], check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5,
    ).stdout
    members = rss = 0
    for line in output.splitlines():
        group, size, state = line.split()
        if int(group) == pgid and not state.startswith('Z'):
            members += 1
            rss += int(size)
    return members, rss


def kill_group(pgid):
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def supervise(cap_gib, timeout_s, log_path, command, *, poll_interval=2, orphan_grace=5):
    """Preserve child status, clean up on cancellation, and fail closed on errors."""
    cap_bytes = int(cap_gib * 2**30)
    started = time.monotonic()
    peak_kib = 0
    proc = None
    status = 125
    cancelled = None
    handlers = {}

    def on_signal(signum, frame):
        nonlocal cancelled
        # Recording rather than raising also covers a signal during Popen startup.
        cancelled = signum

    def set_limit():
        _, hard = resource.getrlimit(resource.RLIMIT_AS)
        limit = cap_bytes if hard == resource.RLIM_INFINITY else min(cap_bytes, hard)
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))

    with open(log_path, 'w', buffering=1) as log:
        def report(message):
            print('[watchdog] ' + message, file=log, flush=True)

        try:
            for sig in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
                handlers[sig] = signal.signal(sig, on_signal)
            # Popen waits for exec (or failure). Its returned PID reliably identifies
            # the new group, unlike racing a background setsid against the first ps.
            proc = subprocess.Popen(
                command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                preexec_fn=None if os.environ.get('NO_VLIMIT') == '1' else set_limit,
            )
            main_exit = None
            while True:
                if cancelled is not None:
                    report(f'cancelled signal={cancelled}; killing pgid {proc.pid}')
                    status = 128 + cancelled
                    break
                members, rss_kib = group_rss_kib(proc.pid)
                main_rc = proc.poll()
                peak_kib = max(peak_kib, rss_kib)
                now = time.monotonic()
                if main_rc is not None and not members:
                    status = main_rc if main_rc >= 0 else 128 - main_rc
                    break
                if rss_kib * 1024 > cap_bytes or now - started >= timeout_s:
                    report(f'killing pgid {proc.pid} rss_kb={rss_kib} elapsed={now-started:.3f}s')
                    status = 137
                    break
                if main_rc is not None:
                    if main_exit is None:
                        main_exit = now
                    if now - main_exit >= orphan_grace:
                        report(f'command exited but left processes in pgid {proc.pid}; killing them')
                        status = 4
                        break
                delay = min(poll_interval, timeout_s - (now - started))
                if main_exit is not None:
                    delay = min(delay, orphan_grace - (now - main_exit))
                time.sleep(max(0, delay))
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            report(f'supervision failed: {type(error).__name__}: {error}')
        finally:
            if proc is not None:
                kill_group(proc.pid)
                proc.wait()
            if cancelled is not None:
                status = 128 + cancelled
            report(f'done rc={status} peak_group_rss_GB={peak_kib / 2**20:.6f} '
                   f'elapsed={time.monotonic()-started:.3f}s')
            for sig, previous in handlers.items():
                signal.signal(sig, previous)
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cap_gib', type=positive_number)
    parser.add_argument('timeout_s', type=positive_number)
    parser.add_argument('log')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('a command is required after LOG --')
    try:
        return supervise(args.cap_gib, args.timeout_s, args.log, command)
    except OSError as error:
        parser.exit(125, f'watchdog: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
