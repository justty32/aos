#!/usr/bin/env python3
"""Offline kernel edge probes. Run from any cwd; all worlds cleaned in finally."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

BASE = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(BASE / 'lib'))
import aos7_fs as fs
from aos7_kernel_rules import run_rules

OUT = Path(__file__).resolve().parent

def wait(pred, timeout=12):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = pred()
        if result:
            return result
        time.sleep(.02)
    raise AssertionError('timeout')

class World:
    def __init__(self, name, cfg, deny_b=False):
        self.root = Path(tempfile.mkdtemp(prefix='astra3-kernel-' + name + '-'))
        self.name, self.cfg = name, cfg
        for node in ['team', 'team/a', 'team/b']:
            fs.write_json(str(self.root / node / '.aos/timeline.json'), {'interval_ms': 180})
            tasks = [{'name': 'kernel', 'mode': 'keep', 'argv': ['aos7-kernel'],
                      'mounts': {'daemon': '.aosd', 'a': 'team/a/.aos', 'b': 'team/b/.aos'}}] if node == 'team' else []
            task_config = {'tasks': tasks}
            if node == 'team' and deny_b:
                del tasks[0]['mounts']['b']
                task_config['mount_allow'] = ['.aosd', 'team/a/.aos']
            fs.write_json(str(self.root / node / '.aos/tasks.json'), task_config)
        self.usage(0)
        self.config(cfg)
        self.log = open(self.root / 'daemon.out', 'w')
        self.p = subprocess.Popen([sys.executable, str(BASE / 'bin/aos7-daemon'), str(self.root)],
                                  stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        wait(lambda: self.state().get('round', 0) >= 2)
        self.events = []

    def config(self, cfg):
        self.cfg = dict(cfg)
        fs.write_json(str(self.root / 'team/kernel.json'), cfg)

    def usage(self, n):
        task = self.root / 'team/a/.aos/tasks/old-r0'
        fs.write_json(str(task / 'birth.json'), {'tid': 'old-r0', 'name': 'old', 'round': 0})
        fs.write_json(str(task / 'exit.json'), {'code': 0})
        fs.write_json(str(task / 'usage.json'), {'tokens': n, 'calls': 1})

    def kdirs(self):
        return sorted((self.root / 'team/.aos/tasks').glob('kernel-*'))

    def state(self):
        states = [fs.read_json(str(p / 'kernel-state.json'), {}) for p in self.kdirs()]
        return max(states, key=lambda s: s.get('round', 0), default={})

    def decisions(self):
        return [x for d in self.kdirs() for x in fs.read_jsonl(str(d / 'decisions.jsonl'))]

    def paused(self):
        return 'team/a' in fs.read_json(str(self.root / '.aosd/paused.json'), {}).get('paused', [])

    def capture(self, label):
        self.events.append({'label': label, 'state': self.state(), 'paused': self.paused(),
                            'status': fs.read_json(str(self.root / '.aosd/status.json')),
                            'decisions': self.decisions(),
                            'roster_a': fs.read_json(str(self.root / 'team/a/.aos/roster.json'))})

    def rounds(self, n):
        rnd = self.state()['round']
        wait(lambda: self.state().get('round', 0) >= rnd + n)

    def close(self):
        if self.p.poll() is None:
            self.p.terminate()
        try:
            self.p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(self.p.pid, signal.SIGKILL)
            self.p.wait()
        # Include moved nodes and runner groups in final cleanup.
        groups = []
        for pidfile in self.root.rglob('pid.json'):
            data = fs.read_json(str(pidfile), {})
            pgid = data.get('pgid')
            if isinstance(pgid, int):
                groups.append(pgid)
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        logs = {str(d.relative_to(self.root)): (d / 'out.log').read_text()[-12000:]
                for d in self.kdirs() if (d / 'out.log').exists()}
        exits = {str(d.relative_to(self.root)): fs.read_json(str(d / 'exit.json')) for d in self.kdirs()}
        fs.write_json(str(OUT / (self.name + '.json')), {'events': self.events, 'kernel_logs': logs,
                     'kernel_exits': exits, 'daemon_exit': self.p.returncode, 'cleanup_groups': groups,
                     'temporary_root': str(self.root), 'cleaned': True})
        self.log.close()
        shutil.rmtree(self.root)

def readd_case():
    w = World('removed-readd', {'members': ['a'], 'budget_tokens': 10, 'cool_rounds': 5})
    try:
        w.usage(20)
        wait(w.paused)
        w.capture('budget pause 20 tokens')
        w.config(dict(w.cfg, members=[]))
        wait(lambda: not w.paused())
        w.capture('removed member resumed, acc remains 20')
        w.config(dict(w.cfg, members=['a']))
        wait(w.paused)
        w.capture('readded unchanged usage, incorrectly paused again')
        assert len([d for d in w.decisions() if d['op'] == 'pause']) == 2
        w.config(dict(w.cfg, members=[]))
        wait(lambda: not w.paused())
        w.capture('second removal resumes, same acc still retained')
        w.config(dict(w.cfg, members=['a']))
        wait(w.paused)
        w.capture('second readd: third pause with the same 20 tokens')
        assert len([d for d in w.decisions() if d['op'] == 'pause']) == 3
    finally:
        w.close()

def cap_case():
    w = World('cap-budget', {'members': ['a'], 'budget_tokens': 10, 'cool_rounds': 8, 'cap_tokens': 100})
    try:
        w.usage(20)
        wait(w.paused)
        w.capture('budget paused')
        w.usage(120)
        wait(lambda: w.state().get('paused', {}).get('team/a', {}).get('cap'))
        w.capture('cap takes over rate pause')
        w.rounds(10)
        assert w.paused()
        w.capture('still cap paused beyond original cooldown')
        w.config(dict(w.cfg, cap_tokens=200))
        wait(lambda: not w.paused())
        w.capture('raising cap resumes; usage accumulation reset')
    finally:
        w.close()

def roster_case():
    w = World('roster-broken-mount', {'members': ['a', 'b'], 'cap_tokens': 100})
    try:
        w.usage(120)
        wait(w.paused)
        w.capture('a paused by cap; roster mounted normally')
        old_kernel = w.kdirs()[0]
        # A paused member can be moved without a tick concurrently recreating it.
        (w.root / 'team/a').rename(w.root / 'team/moved-a')
        wait(lambda: (old_kernel / 'exit.json').exists())
        wait(lambda: len(w.kdirs()) >= 2)
        w.rounds(3)
        w.capture('moved member makes roster write crash whole kernel; restart creates old path')
        w.events[-1]['original_kernel_exit'] = fs.read_json(str(old_kernel / 'exit.json'))
        w.events[-1]['new_old_path_exists'] = (w.root / 'team/a/.aos').is_dir()
        w.events[-1]['moved_a_usage'] = fs.read_json(str(w.root / 'team/moved-a/.aos/tasks/old-r0/usage.json'))
        assert fs.read_json(str(old_kernel / 'exit.json'))['code'] == 1
    finally:
        w.close()

def roster_projection_case():
    w = World('roster-denied-known', {'members': ['a', 'b']}, deny_b=True)
    try:
        w.rounds(3)
        w.capture('known M-15: roster is config projection, b remains listed despite denied mount')
        w.events[-1]['kernel_birth'] = fs.read_json(str(w.kdirs()[0] / 'birth.json'))
        w.events[-1]['mount_receipts'] = [fs.read_json(str(p)) for p in (w.kdirs()[0] / 'mount-done').glob('*.json')]
        assert any(x['node'] == 'team/b' for x in w.events[-1]['roster_a']['members'])
        assert any(not x['result']['ok'] for x in w.events[-1]['mount_receipts'])
    finally:
        w.close()

def rules_case():
    cfg = {'members': ['a'], 'budget_tokens': 10, 'cool_rounds': 2}
    state, out = {}, []
    for rnd, total, present in [(1, 0, True), (2, 20, True), (3, 20, False),
                                 (4, 20, False), (5, 20, True), (6, 20, False),
                                 (7, 20, False), (8, 20, True)]:
        snap = {'round': rnd, 'node_id': 'team', 'self_tid': 'kernel-r1', 'self_tasks': [],
                'members': {'team/a': {'exists': True, 'usage_total': total, 'tasks': [], 'round': rnd}}
                if present else {}}
        ds, state = run_rules(cfg, state, snap)
        out.append({'round': rnd, 'total': total, 'member_present': present, 'decisions': ds, 'state': state})
    fs.write_json(str(OUT / 'pure-rules.json'), out)
    assert [(d['round'], d['op']) for x in out for d in x['decisions']] == [
        (2, 'pause'), (4, 'resume'), (5, 'pause'), (7, 'resume'), (8, 'pause')]
    state, out = {}, []
    for rnd, cap, present in [(1, 100, True), (2, 100, False), (3, 200, False),
                              (4, 200, True)]:
        cfg = {'members': ['a'] if present else [], 'cap_tokens': cap}
        snap = {'round': rnd, 'node_id': 'team', 'self_tid': 'kernel-r1', 'self_tasks': [],
                'members': {'team/a': {'exists': True, 'usage_total': 120, 'tasks': [], 'round': rnd}}
                if present else {}}
        ds, state = run_rules(cfg, state, snap)
        out.append({'round': rnd, 'cap': cap, 'member_present': present, 'decisions': ds, 'state': state})
    fs.write_json(str(OUT / 'pure-cap-removed-known.json'), out)
    assert [(d['round'], d['op']) for x in out for d in x['decisions']] == [(1, 'pause'), (4, 'resume')]

if __name__ == '__main__':
    rules_case()
    for fun in [readd_case, cap_case, roster_case, roster_projection_case]:
        fun()
        print(fun.__name__, 'PASS (observed assertions)', flush=True)
