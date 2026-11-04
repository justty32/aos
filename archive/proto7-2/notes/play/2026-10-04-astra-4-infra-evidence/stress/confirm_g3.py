#!/usr/bin/env python3
"""Supplemental G3 evidence: identity, generation, closed rounds and runner ownership."""
import ctypes
import json
import os
from pathlib import Path
import sys
import time

import run_stress as h

h.OUT = h.OUT / 'confirm'
h.OUT.mkdir(exist_ok=True)
snapshots = []
baseline = {}
original_proc = h.proc
original_cleanup = h.cleanup


def detailed(pid):
    result = original_proc(pid)
    if result['state'] == 'gone':
        return result
    try:
        result['sid'] = os.getsid(pid)
        result['cmdline'] = Path(f'/proc/{pid}/cmdline').read_bytes().decode().replace('\0', ' ').strip()
        env = Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
        result['identity'] = [e.decode() for e in env if e.startswith(b'AOS7_')]
        result['status_signals'] = [x for x in Path(f'/proc/{pid}/status').read_text().splitlines() if x.startswith(('SigIgn:', 'SigCgt:'))]
    except (OSError, UnicodeError):
        pass
    return result


def recording_proc(pid):
    result = original_proc(pid)
    baseline.setdefault(pid, result)
    return result


def recording_cleanup(root, daemon, known):
    sub = root / 'a/sub'
    node = sub / 'n1'
    start_round = h.read(node / '.aos/round.json').get('round', 0)
    # Keep observing three additional complete rounds after original >=2-round failure.
    h.wait(lambda: h.read(node / '.aos/last-round.json').get('round', 0) >= start_round + 3)
    snapshot = {'root': str(root), 'generation': h.read(sub / '.aosd/gen.json'), 'status': h.read(sub / '.aosd/status.json'), 'round': h.read(node / '.aos/round.json'), 'last_round': h.read(node / '.aos/last-round.json'), 'processes': [detailed(p) for p in h.belonging(root)], 'slots': []}
    for i in range(3):
        slot = node / '.aos/tasks' / f's{i}'
        snapshot['slots'].append({'name': f's{i}', 'birth': h.read(slot / 'birth.json'), 'pid': h.read(slot / 'pid.json'), 'exit': h.read(slot / 'exit.json'), 'ready': h.read(slot / 'ready.json')})
    snapshots.append(snapshot)
    (h.OUT / 'identity.json').write_text(json.dumps({'baseline': baseline, 'snapshots': snapshots}, ensure_ascii=False, indent=2)+'\n')
    return original_cleanup(root, daemon, known)


class Suite:
    pid = int(sys.argv[1])

    def poll(self):
        return None if h.alive(self.pid) else 0


h.proc = recording_proc
h.cleanup = recording_cleanup
h.g3(11, Suite())
h.RESULT['tmp_remaining'] = [p.name for p in h.TMP.iterdir()]
if not h.RESULT['tmp_remaining']:
    h.TMP.rmdir()
h.RESULT['tmp_removed'] = not h.TMP.exists()
h.save()
