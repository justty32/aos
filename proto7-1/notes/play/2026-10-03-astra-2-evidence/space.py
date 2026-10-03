#!/usr/bin/env python3
"""從 README/spec 檔案協議自建三 agent 空間；無產品內部 import。"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

P71 = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent

def read(p, default=None):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return default

def write(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.tmp')
    tmp.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(p)

def wait(fn, seconds=25):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        v = fn()
        if v:
            return v
        time.sleep(.02)
    raise TimeoutError(str(fn))

def processes(root):
    found = []
    for p in Path('/proc').glob('[0-9]*/environ'):
        try:
            if ('AOS7_ROOT=' + str(root)).encode() in p.read_bytes().split(b'\0'):
                found.append(int(p.parent.name))
        except OSError:
            pass
    return found

def main():
    root = Path(tempfile.mkdtemp(prefix='astra2-space-'))
    events = []
    d = None
    team = root / 'lab'
    ids = ['lab/agents/' + n for n in ('ada', 'ben', 'cy')]
    cfg = {'members': ['agents/ada', 'agents/ben'], 'budget_tokens': 100000,
           'cool_rounds': 12, 'stuck_rounds': 100}
    def roundof(n):
        return (read(root/n/'.aos/round.json', {}) or {}).get('round', 0)
    def kt():
        return next(team.glob('.aos/tasks/kernel-*/kernel-state.json'))
    def snap(label):
        events.append({'label': label, 'rounds': {n: roundof(n) for n in ['lab']+ids},
                       'config': read(team/'kernel.json'), 'kernel_state': read(kt()),
                       'status': read(root/'.aosd/status.json'),
                       'kernel_birth': read(kt().parent/'birth.json')})
    try:
        write(team/'.aos/timeline.json', {'interval_ms': 170})
        write(team/'.aos/tasks.json', {'tasks': [{'name': 'kernel', 'mode': 'keep', 'argv': ['aos7-kernel']}],
                                     'mount_allow': ['.aosd', 'lab/agents']})
        write(team/'kernel.json', cfg)
        for i, nid in enumerate(ids):
            node = root/nid
            write(node/'.aos/timeline.json', {'interval_ms': [145, 160, 180][i]})
            write(node/'.aos/tasks.json', {'tasks': [{'name': 'agent', 'mode': 'keep', 'argv': ['aos7-agent']}],
                                         'mount_allow': ['lab/agents']})
            write(node/'agent.json', {'name': nid.rsplit('/',1)[-1], 'llm': 'fake', 'max_ping': 60})
            write(node/'goal.json', {'say_first': {'to': ids[(i+1)%3], 'body': 'ping 1'}})
        env = dict(os.environ, AOS7_AUDIT='1', PYTHONDONTWRITEBYTECODE='1')
        d = subprocess.Popen([sys.executable, str(P71/'bin/aos7-daemon'), str(root)],
                             env=env, stdout=(root/'daemon.out').open('w'), stderr=subprocess.STDOUT)
        wait(lambda: roundof('lab') >= 12)
        snap('initial-two-members')
        cfg['members'].append('agents/cy')
        write(team/'kernel.json', cfg)
        wait(lambda: roundof('lab') >= 20)
        snap('added-cy-and-mounted')
        cfg['members'].remove('agents/ben')
        write(team/'kernel.json', cfg)
        wait(lambda: roundof('lab') >= 26)
        snap('removed-ben-normal')
        cfg['members'].append('agents/ben')
        cfg['budget_tokens'] = 0
        write(team/'kernel.json', cfg)
        def ben_paused():
            st = read(root/'.aosd/status.json', {})
            return st.get('nodes', {}).get(ids[1], {}).get('paused') and ids[1] in read(kt(), {}).get('paused', {})
        wait(ben_paused)
        snap('ben-paused-by-kernel')
        paused_at = read(kt())['paused'][ids[1]]['at']
        cfg['members'].remove('agents/ben')
        cfg['budget_tokens'] = 100000
        write(team/'kernel.json', cfg)
        wait(lambda: roundof('lab') >= paused_at + 25)
        snap('removed-paused-ben-after-25-kernel-rounds')
        cfg['members'].append('agents/ben')
        write(team/'kernel.json', cfg)
        wait(lambda: not read(root/'.aosd/status.json', {}).get('nodes', {}).get(ids[1], {}).get('paused', True))
        snap('readd-ben-resumed')
        wait(lambda: roundof('lab') >= paused_at + 38)
        snap('final-running')
    finally:
        if d:
            write(root/'.aosd/ctl/zz-stop.json', {'op': 'stop', 'kill': True, 'by': 'astra2-space'})
            try:
                d.wait(timeout=12)
            except subprocess.TimeoutExpired:
                d.terminate()
                d.wait(timeout=8)
        time.sleep(.3)
        left = processes(root)
        for pid in left:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        write(OUT/'space-events.json', events)
        summary = {'root': str(root), 'daemon_rc': d.returncode if d else None,
                   'left_before_cleanup': left, 'nodes': {}, 'audit': {'writes': 0, 'bad': []}}
        for nid in ['lab'] + ids:
            node = root/nid
            files = {}
            for pat in ['.aos/tasks/*/birth.json', '.aos/tasks/*/mount-done/*.json',
                        '.aos/tasks/*/state.json', '.aos/tasks/*/kernel-state.json',
                        'inbox/done/*.json', 'outbox/*.json', 'outbox/failed/*.json']:
                for p in node.glob(pat):
                    files[str(p.relative_to(node))] = read(p)
            for p in node.glob('.aos/tasks/*/decisions.jsonl'):
                files[str(p.relative_to(node))] = p.read_text()
            write(OUT/('space-' + nid.rsplit('/',1)[-1] + '-files.json'), files)
            summary['nodes'][nid] = {'round': roundof(nid), 'received_done': len(list(node.glob('inbox/done/*.json'))),
                                     'outbox': len(list(node.glob('outbox/*.json'))),
                                     'failed': len(list(node.glob('outbox/failed/*.json')))}
            for p in node.glob('.aos/tasks/*/writes.jsonl'):
                for line in p.read_text().splitlines():
                    item = json.loads(line)
                    summary['audit']['writes'] += 1
                    if not item['ok']:
                        summary['audit']['bad'].append(item)
        shutil.rmtree(root)
        summary['root_removed'] = not root.exists()
        summary['left_after_cleanup'] = processes(root)
        write(OUT/'space-summary.json', summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
