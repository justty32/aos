#!/usr/bin/env python3
"""Read-only production regression: 3 suites, 10 concurrent G3 cases. Own /tmp only."""
import ctypes
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[4]
TOP = REPO / 'proto7-2'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.path.insert(0, str(TOP / 'lib'))
from aos7_fs import write_json

# Adopt killed experiment children so PID 1 does not have to reap them.
assert ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) == 0
TMP = Path(tempfile.mkdtemp(prefix='astra5-subd-stress-'))
RESULT = {'tmp': str(TMP), 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(), 'suites': [], 'g3': []}


def save():
    (OUT / 'stress-parallel.json').write_text(json.dumps(RESULT, ensure_ascii=False, indent=2) + '\n')


def read(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def proc(pid):
    try:
        raw = Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()
        return {'pid': pid, 'state': raw[0], 'ppid': int(raw[1]), 'pgid': int(raw[2]), 'starttime': int(raw[19])}
    except OSError:
        return {'pid': pid, 'state': 'gone'}


def alive(pid):
    return proc(pid)['state'] not in ('gone', 'Z')


def belonging(root):
    found = []
    prefix = ('AOS7_ROOT=' + str(root)).encode()
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name) == os.getpid():
            continue
        try:
            env = (p / 'environ').read_bytes().split(b'\0')
            cmd = (p / 'cmdline').read_bytes().split(b'\0')
            if any(e == prefix or e.startswith(prefix + b'/') for e in env) or str(root).encode() in cmd:
                found.append(int(p.name))
        except OSError:
            pass
    return sorted(found)


def wait(pred, timeout=25):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = pred()
        if value:
            return value
        time.sleep(.01)
    raise TimeoutError('predicate timed out')


def ctl(root, op, *args):
    p = subprocess.run([sys.executable, str(TOP / 'bin/aos7-ctl'), 'daemon', str(root), op, *args], capture_output=True, text=True, timeout=15)
    if p.returncode:
        raise RuntimeError(p.stderr)
    return json.loads(p.stdout)['wrote']


def cleanup(root, daemon, known):
    before = belonging(root)
    if daemon.poll() is None:
        daemon.send_signal(signal.SIGTERM)
        try:
            daemon.wait(10)
        except subprocess.TimeoutExpired:
            daemon.kill()
            daemon.wait(5)
    killed = []
    for _ in range(5):
        pids = belonging(root)
        known.update(pids)
        for pid in pids:
            if alive(pid):
                try:
                    os.kill(pid, signal.SIGKILL)
                    killed.append(pid)
                except ProcessLookupError:
                    pass
        time.sleep(.1)
        for pid in known:
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass
        if not belonging(root):
            break
    after = belonging(root)
    ps = subprocess.run(['ps', '-o', 'pid,ppid,pgid,stat,args', '-p', ','.join(map(str, sorted(known)))], text=True, capture_output=True).stdout if known else ''
    return {'before': before, 'pid_sigkill': killed, 'after': after, 'ps_known_pids': ps, 'known_alive': [pid for pid in known if alive(pid)]}


def g3(case, suite):
    root = TMP / f'g3-{case:02d}'
    parent = root / 'a'
    sub = parent / 'sub'
    node = sub / 'n1'
    pslot = parent / '.aos/tasks/sub'
    cslots = [node / '.aos/tasks' / f's{i}' for i in range(3)]
    for n in (parent, node):
        (n / '.aos').mkdir(parents=True, exist_ok=True)
        write_json(str(n / '.aos/timeline.json'), {'interval_ms': 100})
    worker = root / 'ignore_term.py'
    worker.write_text("import json, os, pathlib, signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\np=pathlib.Path(os.environ['AOS7_TASK']) / 'ready.json'\np.write_text(json.dumps({'pid':os.getpid(), 'run':int(os.environ['AOS7_RUN']), 'ignores_sigterm':True}))\nwhile True: time.sleep(.02)\n")
    boot = ['sh', '-c', 'aos7-ctl daemon "$AOS7_SUBROOT" register n1 --by boot > /dev/null && exec aos7-daemon "$AOS7_SUBROOT"']
    write_json(str(parent / '.aos/tasks.json'), {'tasks': [{'name': 'sub', 'mode': 'keep', 'argv': [sys.executable, str(TOP / 'modules/subd/aos7-subd'), 'a/sub', '--', *boot]}]})
    write_json(str(node / '.aos/tasks.json'), {'tasks': [{'name': f's{i}', 'mode': 'keep', 'argv': [sys.executable, str(worker)]} for i in range(3)]})
    ctl(root, 'register', 'a')
    log = (OUT / f'parallel-g3-{case:02d}.log').open('w')
    daemon = subprocess.Popen([sys.executable, str(TOP / 'bin/aos7-daemon'), str(root)], cwd=REPO, stdout=log, stderr=log)
    known = {daemon.pid}
    row = {'case': case, 'suite_pid': suite.pid, 'suite_running_at_start': suite.poll() is None, 'root': str(root)}
    start = time.monotonic()
    try:
        wait(lambda: all(read(s / 'ready.json').get('run') == read(s / 'birth.json').get('run') and read(s / 'ready.json').get('pid') for s in cslots))
        status = read(sub / '.aosd/status.json')
        old_daemon = status['pid']
        old_pids = [read(s / 'ready.json')['pid'] for s in cslots]
        known.update(belonging(root))
        known.update(old_pids + [old_daemon])
        row.update(old_daemon=old_daemon, old_tasks=[proc(p) for p in old_pids], ready=[read(s / 'ready.json') for s in cslots], before_round=read(node / '.aos/round.json'), parent_run=read(pslot / 'birth.json')['run'])
        kill_at = time.monotonic()
        write_json(str(pslot / 'ctl.json'), {'op': 'kill', 'run': row['parent_run'], 'by': 'astra5-g3'})
        events = []
        previous = None
        new_start_round = None
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status = read(sub / '.aosd/status.json')
            rnd = read(node / '.aos/round.json')
            current_pid = status.get('pid')
            current_round = rnd.get('round', 0)
            live = [p for p in old_pids if alive(p)]
            old_daemon_alive = alive(old_daemon)
            new = current_pid and current_pid != old_daemon and alive(current_pid)
            state = (old_daemon_alive, tuple(live), current_pid, current_round, rnd.get('open'))
            if state != previous:
                events.append({'t_s': round(time.monotonic()-kill_at, 4), 'old_daemon_alive': old_daemon_alive, 'old_tasks_alive': live, 'status_pid': current_pid, 'round': current_round, 'open': rnd.get('open')})
                previous = state
            if not old_daemon_alive and 'at_old_daemon_exit' not in row:
                row['at_old_daemon_exit'] = events[-1]
            if new and new_start_round is None:
                new_start_round = current_round
                row['new_daemon_seen'] = events[-1]
            if new and not live:
                row['recovery'] = events[-1]
                row['pass'] = current_round <= new_start_round + 2
                break
            if new and current_round > new_start_round + 2:
                row['pass'] = False
                row['failure'] = 'old task still alive beyond two rounds after replacement daemon'
                break
            time.sleep(.01)
        else:
            row['pass'] = False
            row['failure'] = 'replacement or collection timeout'
        row['events'] = events
        row['kill_receipt'] = read(pslot / 'ctl-done.json')
        row['suite_running_at_end'] = suite.poll() is None
        row['had_orphans'] = bool(row.get('at_old_daemon_exit', {}).get('old_tasks_alive'))
    except Exception:
        row.update({'pass': False, 'harness_error': traceback.format_exc()})
    finally:
        known.update(belonging(root))
        row['cleanup'] = cleanup(root, daemon, known)
        log.close()
        if not row['cleanup']['after'] and not row['cleanup']['known_alive']:
            shutil.rmtree(root)
        row['tmp_removed'] = not root.exists()
        row['elapsed_s'] = round(time.monotonic() - start, 3)
        RESULT['g3'].append(row)
        save()
        print(json.dumps({'case': case, 'pass': row.get('pass'), 'orphans': row.get('had_orphans'), 'elapsed': row['elapsed_s'], 'error': row.get('harness_error')}, ensure_ascii=False), flush=True)


class ConcurrentSuite:
    @property
    def pid(self):
        for p in Path('/proc').iterdir():
            if p.name.isdigit() and int(p.name) != os.getpid():
                try:
                    args=(p/'cmdline').read_bytes().split(b'\0')
                    if any(a.endswith(b'proto7-2/tests/run_all.py') or a.endswith(b'/tests/run_all.py') for a in args):
                        return int(p.name)
                except OSError: pass
        return None
    def poll(self):
        return None if self.pid else 0


def main():
    for i in range(1,11):
        g3(i, ConcurrentSuite())
    RESULT['tmp_remaining'] = [p.name for p in TMP.iterdir()]
    if not RESULT['tmp_remaining']: TMP.rmdir()
    RESULT['tmp_removed'] = not TMP.exists()
    RESULT['final_proc_remaining'] = belonging(TMP)
    save()


if __name__ == '__main__': main()
