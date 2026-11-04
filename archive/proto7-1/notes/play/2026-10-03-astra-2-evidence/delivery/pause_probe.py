#!/usr/bin/env python3
"""Real daemon: dynamically mount a paused recipient, then resume."""
import json, pathlib, shutil, subprocess, time
from reproduce import Space, HERE, BIN, put, read, wait, events

s = Space('paused-recipient')
p = None
try:
    put(s.root / 'receiver/.aos/timeline.json', {'interval_ms': 100})
    put(s.root / 'receiver/.aos/tasks.json', {'tasks': [{'name': 'agent', 'mode': 'keep', 'argv': ['aos7-agent']}]})
    put(s.root / 'receiver/agent.json', {'name': 'receiver', 'llm': 'fake', 'max_ping': 2})
    put(s.root / '.aosd/paused.json', {'paused': ['receiver']})
    s.goal('receiver', 'ping 2')
    with open(s.root / 'daemon.log', 'w') as log:
        p = subprocess.Popen(['python3', str(BIN / 'aos7-daemon'), str(s.root)], stdout=log, stderr=log, env=s.env)
        wait(lambda: (read(s.n / '.aos/round.json') or {}).get('round', 0) >= 30, 15)
        s.round = read(s.n / '.aos/round.json')['round']; s.snap('paused-30')
        assert list((s.root / 'receiver/inbox').glob('*.json'))
        assert not (s.root / 'receiver/work/done.txt').exists()
        put(s.root / '.aosd/ctl/resume.json', {'op': 'resume', 'node': 'receiver'})
        wait(lambda: (s.root / 'receiver/work/done.txt').exists(), 10)
        s.round = read(s.n / '.aos/round.json')['round']; s.snap('resumed')
        put(s.root / '.aosd/ctl/stop.json', {'op': 'stop', 'kill': True})
        p.wait(timeout=10)
        assert p.returncode == 0
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
    (HERE / 'pause-index.json').write_text(json.dumps(events, ensure_ascii=False, indent=2))
    assert not survivors
print(json.dumps(events, ensure_ascii=False))
