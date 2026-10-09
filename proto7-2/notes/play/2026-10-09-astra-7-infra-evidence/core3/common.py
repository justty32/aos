"""Independent core3 probe support; stdlib only. Each entry point scopes itself."""
import ctypes
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import traceback

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
TOP = REPO / 'proto7-2'
BIN = TOP / 'bin'
LIB = TOP / 'lib'
HOOKS = TOP / 'tests/_hooks.py'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

def scoped():
    if os.environ.get('ASTRA7_CORE3_SCOPED') != '1':
        os.chdir(REPO)
        os.execvp('systemd-run', ['systemd-run', '--user', '--scope', '-q', '-p', 'TasksMax=800', '-p',
                  'RuntimeMaxSec=1800', 'env', 'ASTRA7_CORE3_SCOPED=1', 'PYTHONDONTWRITEBYTECODE=1',
                  sys.executable, *sys.argv])
    ctypes.CDLL(None).prctl(36, 1, 0, 0, 0)  # adopt and reap only our descendants

def read(p, default=None):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return default

def write(p, value):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name('.' + p.name + '.probe-tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n')
    tmp.replace(p)

def wait(pred, timeout=15, what='condition'):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = pred()
        if v:
            return v
        time.sleep(.01)
    raise AssertionError('timeout: ' + what)

def ident(pid):
    try:
        fields = Path('/proc/%d/stat' % pid).read_bytes().rsplit(b')', 1)[1].split()
        return {'pid': pid, 'starttime': int(fields[19]), 'state': fields[0].decode(),
                'ppid': int(fields[1]), 'pgid': int(fields[2])}
    except (OSError, IndexError, ValueError):
        return None

def alive(identity):
    cur = ident(identity['pid']) if identity else None
    return bool(cur and cur['starttime'] == identity['starttime'] and cur['state'] != 'Z')

def scan(root=None, node=None, tid=None):
    out = []
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            env = dict(x.split(b'=', 1) for x in (p/'environ').read_bytes().split(b'\0') if b'=' in x)
            if root and env.get(b'AOS7_ROOT') != str(root).encode():
                continue
            if node and env.get(b'AOS7_NODE') != str(node).encode():
                continue
            if tid and env.get(b'AOS7_TID') != tid.encode():
                continue
            st = ident(int(p.name))
            if st and st['state'] != 'Z':
                st.update(run=env.get(b'AOS7_RUN', b'').decode(), cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')[:240])
                out.append(st)
        except (OSError, ValueError):
            pass
    return out

class Case:
    def __init__(self, name):
        self.name = name
        self.root = Path(tempfile.mkdtemp(prefix='astra7-core3-' + name + '-'))
        self.procs = []
        self.checks = []
        self.data = {'scenario': name, 'root': str(self.root), 'injection': {}, 'assertions': self.checks}
        self.env = dict(os.environ, AOS7_TEST_HOOKS=str(HOOKS), AOS7_TEST_FAULT='@' + str(self.root/'rules'),
                        AOS7_TEST_FAULT_HITS=str(self.root/'hits'))
        self.counter = 0
        self.files = []
        self.snapshots = []
        self.monitor_stop = threading.Event()
        self.monitor_thread = None
    def check(self, assertion, actual, expected=True):
        ok = actual == expected
        self.checks.append({'assertion': assertion, 'actual': actual, 'expected': expected, 'pass': ok})
        return ok
    def start(self, argv, env=None, name='process'):
        log = open(self.root/(name + '-' + str(len(self.procs)) + '.log'), 'ab')
        self.files.append(log)
        p = subprocess.Popen([str(x) for x in argv], env=env or self.env, stdout=log, stderr=log,
                             start_new_session=True, cwd=REPO)
        self.procs.append(p)
        return p
    def cli(self, prog, *args, env=None):
        p = subprocess.run([sys.executable, str(BIN/prog), *map(str,args)], env=env or self.env,
                           capture_output=True, text=True, timeout=30, cwd=REPO)
        value = {'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}
        self.data.setdefault('commands', []).append({'program':prog, 'args': list(map(str,args)), **value})
        if p.returncode != 0:
            raise AssertionError(value)
        return json.loads(p.stdout.splitlines()[-1]) if p.stdout.strip() else None
    def node(self, label='old', nid='a', old=None, inst=False, empty=False):
        node = self.root/nid
        (node/'.aos').mkdir(parents=True, exist_ok=True)
        argv = [sys.executable, str(HERE/'worker.py'), str(self.root/(label+'.ready')), str(self.root/(label+'.term')),
                json.dumps(old)]
        task = {'name':'s', 'mode':'keep', 'argv':argv}
        if inst:
            os.mkfifo(self.root/'stdin.fifo')
            write(node/'inst.json', {'argv':argv, 'stdin':str(self.root/'stdin.fifo')})
            task = {'name':'s', 'mode':'keep', 'inst':'inst.json'}
        write(node/'.aos/tasks.json', {'tasks': [] if empty else [task]})
        write(node/'.aos/timeline.json', {'interval_ms':1000})
        return node
    def daemon(self, env=None):
        (self.root/'.aosd').mkdir(exist_ok=True)
        (self.root/'.aosd/log.on').touch()
        p = self.start([sys.executable, BIN/'aos7-daemon', self.root], env=env, name='daemon')
        wait(lambda: self.status().get('pid') == p.pid or p.poll() is not None, what='daemon start')
        if p.poll() is not None:
            raise AssertionError('daemon exited %s' % p.returncode)
        return p
    def ctl(self, op, node='a', **kw):
        self.counter += 1
        name = 'core3-%04d.json' % self.counter
        payload = dict(op=op, by='astra7-core3', **kw)
        if node is not None:
            payload['node'] = node
        write(self.root/'.aosd/ctl'/name, payload)
        result = wait(lambda: read(self.root/'.aosd/ctl-done'/name), what='receipt '+op)
        self.data.setdefault('receipts', []).append(result)
        return result['result']
    def status(self):
        return read(self.root/'.aosd/status.json', {})
    def nodes(self):
        return read(self.root/'.aosd/nodes.json', {})
    def ready(self, label='old'):
        return wait(lambda: read(self.root/(label+'.ready')), what=label+' ready')
    def running(self):
        return wait(lambda: self.status().get('nodes',{}).get('a',{}).get('phase') == 'running', what='running timeline')
    def kill(self, p):
        p.kill()
        p.wait(10)
    def monitor(self, old):
        start = time.monotonic()
        def run():
            while not self.monitor_stop.is_set():
                new = read(self.root/'new.ready')
                self.snapshots.append({'t': round(time.monotonic()-start,5), 'old':ident(old['pid']),
                                       'old_alive':alive(old), 'new':new, 'new_alive':alive(new),
                                       'phase': self.status().get('nodes',{}).get('a',{}).get('phase'),
                                       'reaping':self.nodes().get('reaping'),
                                       'new_round':read(self.root/'a/.aos/round.json')})
                time.sleep(.02)
        self.monitor_thread = threading.Thread(target=run)
        self.monitor_thread.start()
    def finish(self, exc=None):
        self.monitor_stop.set()
        if self.monitor_thread:
            self.monitor_thread.join(3)
        if exc:
            self.data['error'] = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        if self.snapshots:
            write(self.root/'snapshots.json', self.snapshots)
            self.data['observation'] = {'samples':len(self.snapshots), 'span_s':self.snapshots[-1]['t']-self.snapshots[0]['t'],
                                        'overlap_samples':sum(s['old_alive'] and s['new_alive'] for s in self.snapshots)}
        # Only our Popen handles, identities marked AOS7_ROOT and our adopted children are signalled.
        for p in self.procs:
            if p.poll() is None:
                p.kill()
        killed = []
        for _ in range(5):
            own = scan(root=self.root)
            for st in own:
                if alive(st):
                    try: os.kill(st['pid'], signal.SIGKILL); killed.append(st)
                    except ProcessLookupError: pass
            time.sleep(.08)
        for p in self.procs:
            p.wait(10)
        while True:
            try:
                if os.waitpid(-1, os.WNOHANG)[0] == 0: break
            except ChildProcessError: break
        remaining = scan(root=self.root)
        for f in self.files:
            f.close()
        self.data['cleanup'] = {'killed':killed, 'remaining':remaining}
        self.check('no owned live process after cleanup', remaining, [])
        archive = HERE/(self.name+'.tar.gz')
        with tarfile.open(archive, 'w:gz') as t:
            t.add(self.root, arcname=self.name, filter=lambda ti: ti if ti.isfile() or ti.isdir() else None)
        self.data['snapshot_archive'] = archive.name
        self.data['archive_bytes'] = archive.stat().st_size
        self.check('archive <= 300 KB', archive.stat().st_size <= 300_000)
        shutil.rmtree(self.root)
        self.data['cleanup']['tmp_removed'] = not self.root.exists()
        self.data['pass'] = not exc and all(x['pass'] for x in self.checks)
        write(HERE/(self.name+'.json'), self.data)
        print(json.dumps({'case':self.name, 'pass':self.data['pass'], 'failed':[x for x in self.checks if not x['pass']],
                          'error':str(exc) if exc else None}), flush=True)
        return self.data

def run_cases(cases):
    scoped()
    results = []
    for name, fn in cases:
        c = Case(name)
        error = None
        try: fn(c)
        except Exception as e: error = e
        results.append(c.finish(error))
    if not all(r['pass'] for r in results):
        raise SystemExit(1)
    return results
