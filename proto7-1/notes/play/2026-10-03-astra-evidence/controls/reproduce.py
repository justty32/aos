import json, os, pathlib, shutil, signal, subprocess, sys, tempfile, time
REPO = pathlib.Path(__file__).resolve().parents[5]
BIN = REPO/'proto7-1/bin'
OUT = pathlib.Path(__file__).resolve().parent
BASE = pathlib.Path(tempfile.mkdtemp(prefix='astra-controls-'))
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
for case,control in [('daemon-invalid-json','{oops'),('daemon-null','null'),('daemon-array','[]'),('daemon-unknown-op','{"op":"typo"}'),('daemon-pause-object-node','{"op":"pause","node":{}}')]:
    root,p,err=start(case)
    f=root/'.aosd/ctl/bad.json';f.parent.mkdir(parents=True,exist_ok=True);f.write_text(control)
    await_(lambda:p.poll() is not None or (root/'.aosd/ctl-done/bad.json').exists())
    time.sleep(.2)
    emit(case,returncode=p.poll(),receipt=read(root/'.aosd/ctl-done/bad.json'),control_pending=f.exists(),round=read(root/'n/.aos/round.json'),stderr=(root/'stderr.log').read_text())
    cleanup(root,p,err)
for case,control in [('task-invalid-json','{oops'),('task-null','null'),('task-array','[]'),('task-unknown-op','{"op":"typo"}')]:
    root,p,err=start(case,[{'name':'sleeper','mode':'keep','argv':[sys.executable,'-c','import time; time.sleep(60)']}])
    await_(lambda:len(list(root.glob('n/.aos/tasks/*/pid.json')))>0)
    td=next(root.glob('n/.aos/tasks/*'));f=td/'ctl.json';f.write_text(control)
    time.sleep(.6)
    emit(case,returncode=p.poll(),receipt=read(td/'ctl-done.json'),control_pending=f.exists(),round=read(root/'n/.aos/round.json'),status=read(root/'.aosd/status.json'),stderr=(root/'stderr.log').read_text())
    cleanup(root,p,err)
root,p,err=start('crash-and-ignore',[
 {'name':'crash','mode':'keep','argv':[sys.executable,'-c','raise RuntimeError("intentional crash")']},
 {'name':'ignore','mode':'keep','argv':[sys.executable,'-c','import time; time.sleep(60)']},
])
await_(lambda:(read(root/'n/.aos/round.json') or {}).get('round',0)>=12)
emit('crash-and-ignore',round=read(root/'n/.aos/round.json'),tasks=[{'tid':f.name,'exit':read(f/'exit.json'),'tock':read(f/'tock.json'),'ended':read(f/'ended.json')} for f in sorted(root.glob('n/.aos/tasks/*'))])
cleanup(root,p,err)
(OUT/'events.json').write_text(json.dumps(EVENTS,ensure_ascii=False,indent=2))
(OUT/'workspace.txt').write_text(str(BASE)+'\n')
