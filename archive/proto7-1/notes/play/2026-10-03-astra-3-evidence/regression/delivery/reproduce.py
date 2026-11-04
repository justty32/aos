#!/usr/bin/env python3
"""File-protocol probes; no product imports. Temporary spaces are removed."""
import json, os, pathlib, shutil, signal, subprocess, tempfile, time

HERE = pathlib.Path(__file__).resolve().parent
REPO = next(p for p in HERE.parents if (p/'proto7-1/bin/aos7-tick').exists())
BIN = REPO / 'proto7-1/bin'
events = []

def read(p):
    try: return json.loads(p.read_text())
    except (OSError, ValueError): return None

def put(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    q = p.with_name(p.name + '.tmp')
    q.write_text(json.dumps(value, ensure_ascii=False))
    q.replace(p)

def wait(fn, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = fn()
        if value: return value
        time.sleep(.015)
    raise RuntimeError('timeout')

class Space:
    def __init__(self, name, allow=None, mounts=None):
        self.name = name
        self.root = pathlib.Path(tempfile.mkdtemp(prefix='astra3-reg-delivery-' + name + '-'))
        self.n = self.root / 'sender'
        self.round = 0
        put(self.n / '.aos/timeline.json', {'interval_ms': 100})
        self.tasks = {'tasks': [{'name': 'agent', 'mode': 'keep', 'argv': ['aos7-agent'], 'mounts': mounts or {}}]}
        if allow is not None: self.tasks['mount_allow'] = allow
        put(self.n / '.aos/tasks.json', self.tasks)
        put(self.n / 'agent.json', {'name': 'sender', 'llm': 'fake', 'max_ping': 2})
        self.env = dict(os.environ, AOS7_AUDIT='1')
    def command(self, prog):
        p = subprocess.run(['python3', str(BIN / prog), str(self.root), 'sender'], capture_output=True, text=True, env=self.env, timeout=10)
        if p.returncode: raise RuntimeError(prog + p.stderr)
        return json.loads(p.stdout)
    def task(self):
        tasks = sorted((self.n / '.aos/tasks').glob('*/birth.json'), key=lambda p: read(p)['round'])
        return tasks[-1].parent if tasks else None
    def step(self):
        out = self.command('aos7-tick'); self.round = out['round']
        td = self.task()
        wait(lambda: (td / 'state.json').exists() or (td / 'exit.json').exists())
        self.command('aos7-tock')
        wait(lambda: (read(td / 'progress.json') or {}).get('round', 0) >= self.round or (td / 'exit.json').exists())
    def goal(self, to, body): put(self.n / 'goal.json', {'say_first': {'to': to, 'body': body}})
    def snap(self, label):
        files = {}
        for p in sorted(self.root.rglob('*')):
            if p.is_symlink(): files[str(p.relative_to(self.root))] = {'symlink': os.readlink(p), 'exists': p.exists()}
            elif p.is_file() and (p.suffix == '.json' or p.name == 'out.log'):
                if '/rounds/' in str(p): continue
                files[str(p.relative_to(self.root))] = read(p) if p.suffix == '.json' else p.read_text()[-18000:]
        event = {'case': self.name, 'label': label, 'round': self.round, 'files': files}
        path = HERE / (self.name + '-' + label + '.json')
        path.write_text(json.dumps(event, ensure_ascii=False, indent=2))
        events.append({'case': self.name, 'label': label, 'round': self.round, 'evidence': path.name})
    def close(self):
        put(self.n / '.aos/tasks.json', {'tasks': []})
        for td in (self.n / '.aos/tasks').glob('*'):
            if not (td / 'exit.json').exists(): put(td / 'ctl.json', {'op': 'kill', 'why': 'probe cleanup'})
        self.command('aos7-tick')
        survivors = []
        for pidfile in self.n.glob('.aos/tasks/*/pid.json'):
            for key in ('pid', 'runner_pid'):
                pid = read(pidfile).get(key)
                if pid:
                    def dead():
                        try: return pathlib.Path('/proc', str(pid), 'stat').read_text().split(')')[1].split()[0] == 'Z'
                        except OSError: return True
                    try: wait(dead)
                    except RuntimeError: survivors.append(pid)
        events.append({'case': self.name, 'cleanup_survivors': survivors, 'removed_root': str(self.root)})
        shutil.rmtree(self.root)
        assert not survivors

def missing():
    s = Space('missing')
    try:
        s.goal('ghost', 'delivery to nonexistent node')
        for _ in range(12): s.step()
        s.snap('after-12')
    finally: s.close()

def denied():
    s = Space('denied', allow=[])
    try:
        s.goal('blocked', 'denied letter')
        for _ in range(8): s.step()
        s.snap('failed')
        s.tasks['mount_allow'] = ['.']; put(s.n / '.aos/tasks.json', s.tasks)
        for p in s.task().glob('mount-done/*.json'): p.unlink()
        for _ in range(8): s.step()
        s.snap('allow-and-delete-receipt')
        put(s.task() / 'ctl.json', {'op': 'restart'})
        for _ in range(8): s.step()
        s.snap('restart')
    finally: s.close()

def target_lifecycle(kind):
    s = Space(kind)
    try:
        put(s.root / 'receiver/.aos/timeline.json', {'interval_ms': 100})
        put(s.root / '.aosd/paused.json', {'paused': ['receiver']})
        s.goal('receiver', 'initial letter')
        for _ in range(5): s.step()
        s.snap('initial')
        if kind == 'deleted': shutil.rmtree(s.root / 'receiver/inbox')
        else: (s.root / 'receiver').rename(s.root / 'moved')
        s.snap('broken-link')
        s.goal('receiver', 'letter after ' + kind)
        for _ in range(8): s.step()
        s.snap('after-change')
    finally: s.close()

def restart_pending():
    s = Space('pending-restart')
    try:
        s.goal('receiver', 'preserve me')
        for _ in range(2): s.step()
        s.snap('queued')
        assert list((s.n / 'outbox').glob('*.json'))
        put(s.task() / 'ctl.json', {'op': 'restart'})
        for _ in range(6): s.step()
        s.snap('after-restart')
    finally: s.close()

if __name__ == '__main__':
    try:
        missing(); denied(); target_lifecycle('deleted'); target_lifecycle('moved'); restart_pending()
    finally:
        (HERE / 'index.json').write_text(json.dumps(events, ensure_ascii=False, indent=2))
    print(json.dumps(events, ensure_ascii=False))
