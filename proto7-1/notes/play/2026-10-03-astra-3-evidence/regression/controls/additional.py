import json, os, pathlib, shutil, signal, subprocess, sys, tempfile, time
REPO = next(p for p in pathlib.Path(__file__).resolve().parents if (p/'proto7-1/bin/aos7-tick').exists())
BIN = REPO/'proto7-1/bin'
OUT = pathlib.Path(__file__).resolve().parent
BASE = pathlib.Path(tempfile.mkdtemp(prefix='astra3-reg-controls-extra-'))
EVENTS=[]
def emit(case, **kw):
    v={'case':case, **kw}; EVENTS.append(v); print(json.dumps(v,ensure_ascii=False),flush=True)
def read(p):
    try: return json.loads(p.read_text())
    except Exception: return None
def write(p,v):
    p.parent.mkdir(parents=True,exist_ok=True); tmp=p.with_suffix('.tmp'); tmp.write_text(json.dumps(v)); tmp.replace(p)
def await_(f,timeout=3):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if f(): return True
        time.sleep(.02)
    return False
def start(name,tasks=None):
    root=BASE/name; write(root/'n/.aos/timeline.json',{'interval_ms':120})
    write(root/'n/.aos/tasks.json',{'tasks':tasks or []})
    err=(root/'stderr.log').open('w'); p=subprocess.Popen([sys.executable,str(BIN/'aos7-daemon'),str(root)],stdout=err,stderr=err,start_new_session=True)
    await_(lambda:read(root/'n/.aos/round.json'))
    return root,p,err
def cleanup(root,p,err):
    if p.poll() is None:
        p.send_signal(signal.SIGTERM)
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
    # A malformed daemon control may exit before it cleans live tasks.
    for f in root.glob('n/.aos/tasks/*/pid.json'):
        d=read(f) or {}
        if not (f.parent/'exit.json').exists():
            for pid in [d.get('pgid'),d.get('runner_pid')]:
                if pid:
                    try:os.killpg(pid,signal.SIGKILL)
                    except ProcessLookupError:pass
    err.close()
    shutil.copytree(root,OUT/name_for(root),dirs_exist_ok=True)
def name_for(root):return root.name
for case,control in [('daemon-pause-list-node',{'op':'pause','node':['n']}),('daemon-pause-missing-node',{'op':'pause','node':'ghost'})]:
    root,p,err=start(case)
    write(root/'.aosd/ctl/bad.json',control)
    await_(lambda:p.poll() is not None or (root/'.aosd/ctl-done/bad.json').exists())
    time.sleep(.2)
    emit(case,returncode=p.poll(),receipt=read(root/'.aosd/ctl-done/bad.json'),pending=(root/'.aosd/ctl/bad.json').exists(),stderr=(root/'stderr.log').read_text())
    cleanup(root,p,err)
root,p,err=start('task-array-recovery',[{'name':'sleeper','mode':'keep','argv':[sys.executable,'-c','import time; time.sleep(60)']}])
write(root/'healthy/.aos/timeline.json',{'interval_ms':120})
write(root/'healthy/.aos/tasks.json',{'tasks':[]})
await_(lambda:len(list(root.glob('n/.aos/tasks/*/pid.json')))>0)
td=next(root.glob('n/.aos/tasks/*'));write(td/'ctl.json',[])
time.sleep(.7)
emit('before-repair',round=read(root/'n/.aos/round.json'),status=read(root/'.aosd/status.json'),tock=read(td/'tock.json'),summaries=sorted(f.name for f in (root/'n/.aos/rounds').glob('*.json')))
write(td/'ctl.json',{'op':'kill','why':'repair malformed control'})
await_(lambda:(td/'ctl-done.json').exists())
time.sleep(.3)
emit('after-repair',round=read(root/'n/.aos/round.json'),status=read(root/'.aosd/status.json'),receipt=read(td/'ctl-done.json'),exit=read(td/'exit.json'),summaries=sorted(f.name for f in (root/'n/.aos/rounds').glob('*.json')))
cleanup(root,p,err)
(OUT/'additional-events.json').write_text(json.dumps(EVENTS,ensure_ascii=False,indent=2))

shutil.rmtree(BASE)
