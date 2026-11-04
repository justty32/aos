#!/usr/bin/env python3
"""Pause the requesting timeline before its next mount-review tick."""
import json, pathlib, shutil, subprocess, time
from reproduce import Space, HERE, BIN, put, read, wait, events

s = Space('pending-paused-sender')
p = None
try:
    put(s.n / '.aos/timeline.json', {'interval_ms': 1000})
    s.goal('receiver', 'waiting for my next tick')
    with open(s.root / 'daemon.log', 'w') as log:
        p = subprocess.Popen(['python3', str(BIN / 'aos7-daemon'), str(s.root)], stdout=log, stderr=log, env=s.env)
        wait(lambda: list((s.n / 'outbox').glob('*.json')), 10)
        put(s.root / '.aosd/ctl/pause.json', {'op': 'pause', 'node': 'sender'})
        wait(lambda: ((read(s.root / '.aosd/status.json') or {}).get('nodes', {}).get('sender', {}).get('phase')) == 'paused', 10)
        s.round = read(s.n / '.aos/round.json')['round']; s.snap('before-wait')
        time.sleep(1.5)
        s.round = read(s.n / '.aos/round.json')['round']; s.snap('after-wait')
        assert list((s.n / 'outbox').glob('*.json'))
        assert list(s.task().glob('mount-req/*.json'))
        put(s.root / '.aosd/ctl/resume.json', {'op': 'resume', 'node': 'sender'})
        wait(lambda: list((s.root / 'receiver/inbox').glob('*.json')), 10)
        s.round = read(s.n / '.aos/round.json')['round']; s.snap('resumed')
        put(s.root / '.aosd/ctl/stop.json', {'op': 'stop', 'kill': True})
        p.wait(timeout=10)
finally:
    if p is not None and p.poll() is None:
        p.terminate(); p.wait(timeout=10)
    survivors = []
    for pidfile in s.root.rglob('pid.json'):
        for key in ('pid', 'runner_pid'):
            pid = read(pidfile).get(key)
            if not pid: continue
            def dead():
                try: return pathlib.Path('/proc', str(pid), 'stat').read_text().split(')')[1].split()[0] == 'Z'
                except OSError: return True
            try: wait(dead)
            except RuntimeError: survivors.append(pid)
    events.append({'cleanup_survivors': survivors, 'daemon_rc': p.returncode if p else None, 'removed_root': str(s.root)})
    shutil.rmtree(s.root)
    (HERE / 'pending-pause-index.json').write_text(json.dumps(events, ensure_ascii=False, indent=2))
    assert not survivors
print(json.dumps(events, ensure_ascii=False))
