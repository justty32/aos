#!/usr/bin/env python3
"""Bounded offline probes; run from repository root. No production edits."""
import ctypes, datetime, json, os, pathlib, shutil, signal, statistics, subprocess, sys, tempfile, time

REPO = pathlib.Path.cwd()
BIN = REPO / 'proto7-1/bin'
OUT = pathlib.Path(__file__).resolve().parent
ctypes.CDLL(None).prctl(36, 1, 0, 0, 0)  # adopt/reap own orphaned descendants

PAYLOAD = r'''
import json, os, pathlib, shutil, signal, sys, time
node = pathlib.Path(os.environ['AOS7_NODE'])
td = pathlib.Path(os.environ['AOS7_TASK'])
kind = sys.argv[1]
def mark(name, value):
    (node / (name+'.json')).write_text(json.dumps(value))
mark('ready', {'pid':os.getpid(), 'kind':kind})
if kind == 'ignore':
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    mark('ready', {'pid':os.getpid(), 'handler':'SIG_IGN'})
    time.sleep(12)
elif kind in ('fork', 'forksetsid'):
    pid = os.fork()
    if pid == 0:
        if kind == 'forksetsid': os.setsid()
        mark('grandchild', {'pid':os.getpid(), 'pgid':os.getpgrp()})
        time.sleep(12)
        os._exit(0)
    time.sleep(.08)
elif kind == 'cpu':
    begin=time.monotonic(); cpu=time.process_time()
    while time.monotonic()-begin < 1.2: pass
    mark('cpu', {'wall_s':time.monotonic()-begin, 'cpu_s':time.process_time()-cpu})
elif kind == 'output':
    begin=time.monotonic()
    for _ in range(128): os.write(1, b'x'*65536)
    mark('output', {'bytes':8388608, 'wall_s':time.monotonic()-begin})
elif kind == 'chdir':
    os.chdir('/')
    time.sleep(.35)
    mark('cwd', {'cwd':os.getcwd(), 'taskdir_exists':td.exists()})
elif kind in ('delete', 'deletekeep'):
    time.sleep(.05)
    shutil.rmtree(td)
    mark('deleted', {'pid':os.getpid(), 'taskdir_exists':td.exists()})
    time.sleep(12)
elif kind == 'birtharray':
    (td/'birth.json').write_text('[1]')
    time.sleep(12)
elif kind == 'birthsyntax':
    (td/'birth.json').write_text('{broken')
    time.sleep(12)
elif kind == 'tocksyntax':
    (td/'tock.json').write_text('{broken')
    time.sleep(12)
elif kind in ('tockdir', 'tockdirpeer'):
    (td/'tock.json').mkdir(exist_ok=True)
    time.sleep(12)
'''

def write(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    q=p.with_name(p.name+'.probe-tmp'); q.write_text(json.dumps(x)); q.replace(p)

def read(p):
    try: return json.loads(p.read_text())
    except Exception: return None

def live(pid):
    try: return pathlib.Path('/proc', str(pid), 'stat').read_text().rsplit(')',1)[1].split()[0] != 'Z'
    except Exception: return False

def owned(root):
    found=[]
    marker=('AOS7_ROOT='+str(root)).encode()+b'\0'
    for p in pathlib.Path('/proc').iterdir():
        if not p.name.isdigit(): continue
        try:
            if marker in (p/'environ').read_bytes() and live(int(p.name)): found.append(int(p.name))
        except Exception: pass
    return found

def wait(test, seconds=3):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        if test(): return True
        time.sleep(.01)
    return False

def reap():
    while True:
        try:
            if os.waitpid(-1, os.WNOHANG)[0]==0: break
        except ChildProcessError: break

def snapshot(root):
    data={}
    for p in sorted(root.rglob('*')):
        if not p.is_file(): continue
        rel=str(p.relative_to(root))
        if p.name.endswith('.json') or p.name.endswith('.jsonl'):
            if p.stat().st_size<50000:
                data[rel]=read(p) if p.suffix=='.json' else [json.loads(x) for x in p.read_text().splitlines()]
        if p.name=='out.log': data[rel]={'bytes':p.stat().st_size}
    return data

def run(kind):
    root=pathlib.Path(tempfile.mkdtemp(prefix='astra4-tasks-'+kind+'-'))
    node=root/'n'; node.mkdir(); (node/'payload.py').write_text(PAYLOAD)
    interval=100 if kind=='short' else 200
    write(node/'.aos/timeline.json', {'interval_ms':interval})
    tasks=[{'name':f's{i}', 'mode':'each', 'argv':['/bin/sleep','.01']} for i in range(20)] if kind=='short' else [{'name':kind,'mode':'keep','argv':[sys.executable,'payload.py',kind]}]
    if kind=='tockdirpeer': tasks.append({'name':'zzhealthy','mode':'keep','argv':['/bin/sleep','12']})
    write(node/'.aos/tasks.json', {'tasks':tasks})
    err=open(root/'daemon.stderr','w+')
    daemon=subprocess.Popen([sys.executable,str(BIN/'aos7-daemon'),str(root)],stdout=subprocess.DEVNULL,stderr=err)
    result={'case':kind,'root':str(root),'interval_ms':interval}
    try:
        if kind=='short':
            wait(lambda: (read(node/'.aos/round.json') or {}).get('round',0)>=5, 8)
            write(node/'.aos/tasks.json', {'tasks':[]})
            time.sleep(.5)
        else:
            wait(lambda: (node/'ready.json').exists())
            # One instance; no keep respawning, except deliberate name corruption tests.
            if kind not in ('birtharray','birthsyntax','deletekeep'):
                write(node/'.aos/tasks.json', {'tasks':[]})
            time.sleep(1.4 if kind in ('cpu','output') else .65)
            if kind in ('ignore','fork','forksetsid'):
                td=node/'.aos/tasks'/f'{kind}-r1'
                start=time.monotonic(); write(td/'ctl.json', {'op':'kill','by':'probe'})
                wait(lambda:(td/'ctl-done.json').exists(),3)
                result['kill_control_latency_ms']=(time.monotonic()-start)*1000
                result['ctl_done']=read(td/'ctl-done.json')
                gc=read(node/'grandchild.json')
                if gc: result['grandchild_alive_after_task_kill']=live(gc['pid'])
            write(node/'.aos/tasks.json', {'tasks':[]})
        result['before_stop']=snapshot(root)
        result['owned_before_stop']=owned(root)
        start=time.monotonic(); daemon.terminate()
        try: daemon.wait(timeout=5)
        except subprocess.TimeoutExpired:
            result['stop_timeout']=True; daemon.kill(); daemon.wait()
        result['stop_ms']=(time.monotonic()-start)*1000
        time.sleep(.08)
        result['daemon_rc']=daemon.returncode
        result['survivors_after_stop']=owned(root)
        result['after_stop']=snapshot(root)
        err.flush(); err.seek(0); result['daemon_stderr']=err.read()[-5000:]
        write(OUT/(kind+'.json'),result)
        print(kind, 'survivors',result['survivors_after_stop'], 'stop_ms',round(result['stop_ms'],1),flush=True)
    finally:
        if daemon.poll() is None: daemon.kill(); daemon.wait()
        for pid in owned(root):
            try: os.kill(pid,signal.SIGKILL)
            except ProcessLookupError: pass
        time.sleep(.08); reap(); err.close(); shutil.rmtree(root)
    return result

if __name__=='__main__':
    cases=sys.argv[1:] or ['short','ignore','fork','forksetsid','cpu','output','chdir','delete','birtharray','birthsyntax','tocksyntax','tockdir']
    for case in cases: run(case)
