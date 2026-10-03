#!/usr/bin/env python3
"""Black-box mount request/restart checks using documented files and tick/tock."""
import json, os, pathlib, shutil, signal, subprocess, sys, tempfile, time
HERE = pathlib.Path(__file__).resolve().parent
REPO = next(p for p in HERE.parents if (p/'proto7-1/bin/aos7-tick').exists())
BIN = REPO/'proto7-1/bin'
ROOT = pathlib.Path(tempfile.mkdtemp(prefix='astra2-requests-'))
EVENTS=[]

def read(p):
    if not p.exists(): return None
    try: return json.loads(p.read_text())
    except (ValueError, OSError): return p.read_text()

def write(p,obj,raw=False):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix('.tmp'); tmp.write_text(obj if raw else json.dumps(obj)); tmp.replace(p)

def call(prog):
    r=subprocess.run([sys.executable,str(BIN/prog),str(ROOT),'n'],capture_output=True,text=True,timeout=8)
    return dict(rc=r.returncode,stdout=r.stdout,stderr=r.stderr)

def tick(): return call('aos7-tick')
def tock(): return call('aos7-tock')
def snapshot(td):
    return dict(birth=read(td/'birth.json'),done={p.name:read(p) for p in (td/'mount-done').glob('*.json')},pending={p.name:read(p) for p in (td/'mount-req').glob('*.json')},links={p.name:os.readlink(p) if p.is_symlink() else 'NOT_LINK' for p in (td/'mnt').glob('*')},ctl_done=read(td/'ctl-done.json'),exit=read(td/'exit.json'))

def wait_pid(td):
    for _ in range(100):
        if (td/'pid.json').exists(): return
        time.sleep(.01)
    raise RuntimeError('no pid')

def req(td,label,obj,raw=False):
    p=td/'mount-req'/f'{label}.json'; write(p,obj,raw=raw)
    result=tick(); after=snapshot(td)
    EVENTS.append(dict(case=label,request=obj,tick=result,after=after))
    p.unlink(missing_ok=True)
    tock()

try:
    write(ROOT/'n/.aos/timeline.json',{'interval_ms':100})
    task={'name':'worker','mode':'keep','argv':['python3','-c','import time;time.sleep(120)']}
    write(ROOT/'n/.aos/tasks.json',{'tasks':[task],'mount_allow':['allowed/']})
    EVENTS.append({'case':'start','tick':tick()}); td=ROOT/'n/.aos/tasks/worker-r1'; wait_pid(td); tock()
    cases=[('syntax','{',True),('array',[],False),('null',None,False),('string','hello',False),('number',42,False),('empty',{},False),('path-list',{'name':'x','path':['allowed/a']},False),('path-object',{'name':'x','path':{'p':'allowed/a'}},False),('name-list',{'name':['x'],'path':'allowed/a'},False),('name-number',{'name':4,'path':'allowed/a'},False),('name-empty',{'name':'','path':'allowed/a'},False),('name-slash',{'name':'x/y','path':'allowed/a'},False),('name-dot',{'name':'.hidden','path':'allowed/a'},False),('absolute',{'name':'absolute','path':str(ROOT/'allowed/a')},False),('escape',{'name':'escape','path':'../escape'},False),('denied',{'name':'deny','path':'forbidden/a'},False),('ok',{'name':'shared','path':'allowed/a'},False),('duplicate',{'name':'shared','path':'allowed/a'},False),('conflict',{'name':'shared','path':'allowed/b'},False),('prefix-sibling',{'name':'sib','path':'allowed_evil/a'},False)]
    for label,obj,raw in cases: req(td,label,obj,raw)
    write(td/'mount-req/01-compete.json',{'name':'race','path':'allowed/race-first'})
    write(td/'mount-req/02-compete.json',{'name':'race','path':'allowed/race-second'})
    result=tick(); EVENTS.append({'case':'same-tick-conflict','tick':result,'after':snapshot(td)}); tock()
    # One receipt filename reused with a new request; caller can explicitly retry.
    req(td,'denied',{'name':'deny','path':'allowed/now'})
    # Restart is processed before pending mounts. Existing grants transfer, queued and denied requests do not.
    write(td/'mount-req/pending.json',{'name':'pending','path':'allowed/pending'})
    write(td/'ctl.json',{'op':'restart','why':'pending mount lifecycle'})
    result=tick(); newids=json.loads(result['stdout'])['started']; td2=ROOT/'n/.aos/tasks'/newids[0]; wait_pid(td2); tock()
    EVENTS.append({'case':'restart-with-pending','tick':result,'old':snapshot(td),'new':snapshot(td2)})
    for _ in range(3): tick(); tock()
    EVENTS.append({'case':'pending-after-three-more-ticks','old':snapshot(td),'new':snapshot(td2)})
    # Name handling when a request path itself is a symlink to a directory is independent of target path checks.
    # Deliberately non-JSON request files should remain untouched by the documented *.json scanner.
    write(td2/'mount-req/not-json.txt',{'name':'ignored','path':'allowed/ignored'})
    result=tick(); EVENTS.append({'case':'non-json-extension','tick':result,'pending_txt_exists':(td2/'mount-req/not-json.txt').exists()}); tock()
finally:
    # Kill every task via its documented ctl, remove keep table first.
    write(ROOT/'n/.aos/tasks.json',{'tasks':[]})
    pids=[]
    for td in (ROOT/'n/.aos/tasks').glob('*'):
        d=read(td/'pid.json') or {}
        pids.extend(d.get(k) for k in ['pid','runner_pid'] if d.get(k))
        if not (td/'exit.json').exists(): write(td/'ctl.json',{'op':'kill','why':'cleanup'})
    cleanup_tock=tock()
    time.sleep(.2)
    def alive(pid):
        try: return pathlib.Path(f'/proc/{pid}/stat').read_text().split(') ')[1].split()[0] != 'Z'
        except (OSError,IndexError): return False
    survivors=[pid for pid in pids if alive(pid)]
    for pid in survivors:
        try: os.kill(pid,signal.SIGKILL)
        except ProcessLookupError: pass
    EVENTS.append({'case':'cleanup','root':str(ROOT),'tock':cleanup_tock,'pids':pids,'live_before_emergency_kill':survivors,'live_after':[p for p in pids if alive(p)]})
    shutil.rmtree(ROOT)
    EVENTS[-1]['root_removed']=not ROOT.exists()
    write(HERE/'results.json',EVENTS)
print(json.dumps({'cases':len(EVENTS),'failures':[(e['case'],e['tick']['rc']) for e in EVENTS if e.get('tick',{}).get('rc')], 'cleanup':EVENTS[-1]},indent=2))
