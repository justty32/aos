# Build isolated real-daemon fixtures and retain evidence for the B lifecycle tests.
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
PROTO = ROOT / 'proto8'
SCRATCH = Path(os.environ.get('AOS_DAEMON_B_SCRATCH') or subprocess.check_output(
    ['mktemp', '-d', '/tmp/aos-daemon-b.XXXXXX'], text=True).strip())
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
ENV['PATH'] = ':'.join(str(p) for p in sorted((PROTO / 'impls').glob('*/bin'))) + ':' + ':'.join(
    str(p) for p in sorted((PROTO / 'cmd').glob('*/bin'))) + ':' + ENV['PATH']
EVIDENCE = []
sys.path.insert(0, str(PROTO / 'py'))
import daemon_ctl as dc


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('.' + path.name)
    tmp.write_text(json.dumps(value) + '\n')
    tmp.replace(path)


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def until(fn, timeout=7):
    end = time.monotonic() + timeout
    while True:
        got = fn()
        if got:
            return got
        if time.monotonic() >= end:
            raise AssertionError('timed out waiting for fixture state')
        time.sleep(.025)


class Fixture:
    def __init__(self, name):
        self.root = SCRATCH / name
        self.root.mkdir(parents=True, exist_ok=True)
        self.stack = self.root / 'stack'
        self.stack.mkdir(exist_ok=True)
        self.cell = self.stack / 'procs' / 'job'
        self.script = self.root / 'body.py'
        self.script.write_text('''#!/usr/bin/env python3
# Signal completion or fail without reading the control window.
import os, pathlib, sys, time
s = pathlib.Path(os.environ['AOS_STACK'])
(s / 'ready').write_text('ready')
time.sleep(float(sys.argv[1]))
code = int(sys.argv[2])
if code:
    print('fixture: error: Failed body failed', file=sys.stderr)
sys.exit(code)
''')
        self.script.chmod(0o755)
        self.config = self.root / 'daemon.json'
        write(self.config, {'interval_ms': 20, 'procs': {}})
        self.proc = None
        self.commands = []

    def start(self):
        self.log = open(self.root / 'daemon.log', 'a')
        self.err = open(self.root / 'daemon.err', 'a')
        self.proc = subprocess.Popen(['aos-daemon', '--enable-logs', str(self.config)], cwd=self.root,
            env=dict(ENV, AOS_STACK=str(self.stack)), stdout=self.log, stderr=self.err)
        until(lambda: read(self.stack / 'procs_state.json', {}).get('pid') == self.proc.pid)
        until(lambda: read(self.stack / 'state_flux.json'))
        return self

    def close(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            self.proc.wait(timeout=15)
        if self.proc is not None:
            self.log.close()
            self.err.close()

    def ctl(self, *args, ok=0):
        p = subprocess.run(['aos-daemon-ctl', '--daemon', str(self.stack), *args], cwd=self.root,
                           env=ENV, capture_output=True, text=True, timeout=10)
        self.commands.append({'argv': list(args), 'code': p.returncode, 'stdout': p.stdout.strip(),
                              'stderr': p.stderr.strip()})
        if ok is not None:
            assert p.returncode == ok, self.commands[-1]
        return p

    def rows(self):
        return read(self.stack / 'procs_state.json', {}).get('procs', {})

    def row(self):
        return self.rows().get('job')

    def phase(self, phase):
        return until(lambda: (r if (r := self.row()) and r['phase'] == phase else None))

    def body(self, kind, case, seconds=None):
        code = 7 if case == 'fail' else 0
        seconds = seconds if seconds is not None else (1.5 if kind == 'script' else .35)
        args = [str(self.script), str(seconds), str(code)]
        if kind == 'script':
            target = self.root / 'body.json'
            write(target, args)
        else:
            ex = args
            if kind == 'fsm':
                fsm = self.root / 'fsm.json'
                write(fsm, {'_entry': ['aos-fsm', {'$env': 'AOS_CF'}], 'start': 'work',
                            'states': {'work': {'exec': args, 'next': 'work'}}})
                ex = str(fsm)
            loop = {'_entry': ['aos-loop', {'$env': 'AOS_CF'}], 'exec': ex, 'interval_ms': 30}
            if case == 'zero':
                loop['max'] = 1
            write(self.root / 'loop.json', loop)
            target = self.root / 'body.json'
            value = {'argv': ['aos-loop', 'loop.json']} if kind == 'loop_object' else ['aos-loop', 'loop.json']
            write(target, value)
        return target

    def add(self, target):
        self.ctl('add', '--name', 'job', str(target))
        self.phase('running')
        until(lambda: (self.cell / 'ready').exists())

    def record(self, kind, case, row=None):
        lines = [json.loads(s) for s in (self.root / 'daemon.log').read_text().splitlines()]
        ends = [v for v in lines if v.get('name') == 'job' and v['phase'] != 'running']
        EVIDENCE.append({'body': kind, 'case': case, 'commands': list(self.commands),
            'phase': row['phase'] if row else 'off_table', 'reason': row.get('reason') if row else None,
            'code': row.get('code') if row else (ends[-1]['code'] if ends else None),
            'off_table': row is None, 'last_log': ends[-1] if ends else None,
            'fixture': str(self.root)})
