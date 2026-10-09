"""Long-lived real task; records readiness, TERM and prior-generation identity."""
import json
import os
from pathlib import Path
import signal
import sys
import time

def stat(pid):
    try:
        f = Path('/proc/%d/stat' % pid).read_bytes().rsplit(b')',1)[1].split()
        return {'pid':pid, 'starttime':int(f[19]), 'state':f[0].decode()}
    except OSError:
        return None

ready, term, old_json = sys.argv[1:]
def ignore(*_):
    with open(term, 'a') as f:
        f.write(json.dumps({'pid':os.getpid(),'monotonic':time.monotonic()})+'\n')
signal.signal(signal.SIGTERM, ignore)
old = json.loads(old_json)
v = stat(os.getpid())
v.update(run=os.environ.get('AOS7_RUN'), monotonic=time.monotonic(), prior=stat(old['pid']) if old else None)
p = Path(ready)
tmp = p.with_suffix('.tmp')
tmp.write_text(json.dumps(v))
tmp.replace(p)
time.sleep(600)
