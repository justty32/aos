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
root,p,err=start('daemon-array-op')
write(root/'.aosd/ctl/bad.json',{'op':[]})
await_(lambda:p.poll() is not None or (root/'.aosd/ctl-done/bad.json').exists())
emit('daemon-array-op',returncode=p.poll(),receipt=read(root/'.aosd/ctl-done/bad.json'),stderr=(root/'stderr.log').read_text())
cleanup(root,p,err)
heartbeat="import pathlib,time; p=pathlib.Path('heartbeat.txt'); i=0\nwhile True:\n i+=1; p.write_text(str(i)); time.sleep(.04)"
root,p,err=start('pause-heartbeat',[{'name':'busy','mode':'keep','argv':[sys.executable,'-c',heartbeat]}])
await_(lambda:(root/'n/heartbeat.txt').exists())
write(root/'.aosd/ctl/pause.json',{'op':'pause','node':'n'})
await_(lambda:((read(root/'.aosd/status.json') or {}).get('nodes',{}).get('n',{}).get('phase'))=='paused')
td=next(root.glob('n/.aos/tasks/*'))
write(td/'ctl.json',{'op':'kill','why':'while paused'})
r1=read(root/'n/.aos/round.json');h1=(root/'n/heartbeat.txt').read_text();t1=read(td/'tock.json')
time.sleep(.5)
emit('paused',before_round=r1,after_round=read(root/'n/.aos/round.json'),heartbeat_before=h1,heartbeat_after=(root/'n/heartbeat.txt').read_text(),tock_before=t1,tock_after=read(td/'tock.json'),pending=(td/'ctl.json').exists(),receipt=read(td/'ctl-done.json'),exit=read(td/'exit.json'))
write(root/'.aosd/ctl/resume.json',{'op':'resume','node':'n'})
await_(lambda:(td/'ctl-done.json').exists())
emit('resumed',round=read(root/'n/.aos/round.json'),receipt=read(td/'ctl-done.json'),exit=read(td/'exit.json'))
cleanup(root,p,err)
(OUT/'pause-events.json').write_text(json.dumps(EVENTS,ensure_ascii=False,indent=2))
