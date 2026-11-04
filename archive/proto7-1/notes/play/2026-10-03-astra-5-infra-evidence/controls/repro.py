#!/usr/bin/env python3
"""No real LLM; all roots /tmp/astra5-controls-*; bounded subprocess cleanup."""
import json, os, sys, time, tempfile, shutil, subprocess, signal
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO/'lib'))
from aos7_fs import write_json, read_json
import aos7_task
BIN=REPO/'bin'
RESULT=[]
def wait(fn, timeout=8):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        v=fn()
        if v:return v
        time.sleep(.01)
    raise TimeoutError(str(fn))
def root():return Path(tempfile.mkdtemp(prefix='astra5-controls-'))
def setup(r,interval=80,tasks=None,paused=False):
    write_json(str(r/'.aos/tasks.json'),{'tasks':tasks or []})
    write_json(str(r/'.aos/timeline.json'),{'interval_ms':interval})
    if paused:write_json(str(r/'.aosd/paused.json'),{'paused':['.']})
def start(r):return subprocess.Popen([sys.executable,str(BIN/'aos7-daemon'),str(r)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
def status(r):return (read_json(str(r/'.aosd/status.json'),{}) or {}).get('nodes',{}).get('.',{})
def ctl(r,op,**kw):
    n=str(time.time_ns())+'.json';write_json(str(r/'.aosd/ctl'/n),dict(op=op,node='.',**kw));return n
def done(r,n):return read_json(str(r/'.aosd/ctl-done'/n))
def cleanup(r,p=None):
    if p and p.poll() is None:
        p.terminate()
        try:p.wait(timeout=6)
        except subprocess.TimeoutExpired:p.kill();p.wait()
    aos7_task.kill_node_procs(str(r), [])
    shutil.rmtree(r)
def save(name,**kw):
    d=dict(case=name,**kw);RESULT.append(d);print(json.dumps(d,ensure_ascii=False),flush=True)

# 1. paused resume rounds, pending pause, ordering and count reset
r=root();p=None
try:
    setup(r,350,[{'name':'sleep','mode':'each','argv':['sleep','2'],'max_live':2}],True);p=start(r)
    wait(lambda: status(r).get('phase')=='paused')
    ctl(r,'resume',rounds=2)
    wait(lambda: status(r).get('phase')=='running')
    n=ctl(r,'pause');wait(lambda:done(r,n))
    pending=wait(lambda:status(r) if status(r).get('pause_pending') else None)
    settled=wait(lambda:status(r) if status(r).get('phase')=='paused' else None)
    before=settled['round'];ctl(r,'resume',rounds=2)
    final=wait(lambda:status(r) if status(r).get('phase')=='paused' and status(r).get('round',0)>=before+2 else None)
    save('resume_pause_resume',pending=pending,settled=settled,final=final,exact_two=final['round']==before+2)
    # at active round, resume rounds=1 counts current round completion
    ctl(r,'resume');wait(lambda:status(r).get('phase')=='running')
    n=ctl(r,'pause');wait(lambda:done(r,n));active=status(r)['round']
    n=ctl(r,'resume',rounds=1);wait(lambda:done(r,n))
    final=wait(lambda:status(r) if status(r).get('phase')=='paused' else None)
    save('pending_pause_then_resume_one',active_round=active,final=final)
finally:cleanup(r,p)

# 2. wake flood: queue overrun freezes status and delays a newly queued stop.
r=root();p=None
try:
    setup(r,5000,paused=True);p=start(r);wait(lambda:status(r).get('phase')=='paused')
    p.send_signal(signal.SIGSTOP)
    for i in range(10000):write_json(str(r/'.aosd/ctl'/('000-flood-%05d.json'%i)),{'op':'wake','node':'.'})
    old=read_json(str(r/'.aosd/status.json'))['at'];t=time.monotonic();p.send_signal(signal.SIGCONT)
    wait(lambda:(r/'.aosd/ctl-done/000-flood-00000.json').exists())
    stop=ctl(r,'stop',kill=True);st=time.monotonic();observations=[]
    while not done(r,stop) and time.monotonic()-st<15:
        observations.append({'seconds':round(time.monotonic()-t,3),'status_unchanged':read_json(str(r/'.aosd/status.json'))['at']==old})
        time.sleep(.1)
    save('wake_flood',files=10000,stop_receipt_delay_s=round(time.monotonic()-st,3),total_drain_s=round(time.monotonic()-t,3),observations=observations,receipt=done(r,stop))
finally:cleanup(r,p)

# 3. wake before node exists is accepted with promise but no stored kick.
r=root()
try:
    from aos7_daemon import Daemon
    d=Daemon(str(r));accepted=d.apply({'op':'wake','node':'future'})
    setup(r/'future',5000)
    from aos7_daemon_timeline import Timeline
    tl=Timeline(d,'future')
    save('wake_unknown',accepted=accepted,new_timeline_kick=tl.kick,daemon_fields=sorted(d.__dict__))
finally:cleanup(r)

# 4. edit_json lock owner killed before publish; lock released, successful next writer.
r=root();holder=None
try:
    target=r/'tasks.json';write_json(str(target),{'n':0})
    code="import sys,time;sys.path.insert(0,sys.argv[1]);from aos7_fs import edit_json;from pathlib import Path\ndef fn(x):\n Path(sys.argv[3]).write_text('locked');time.sleep(60);return {'n':99}\nedit_json(sys.argv[2],fn)"
    holder=subprocess.Popen([sys.executable,'-c',code,str(REPO/'lib'),str(target),str(r/'locked')])
    wait(lambda:(r/'locked').exists());holder.kill();holder.wait();t=time.monotonic()
    from aos7_fs import edit_json
    got=edit_json(str(target),lambda x:{'n':x['n']+1})
    save('edit_json_kill_owner',killed_rc=holder.returncode,after=got,acquire_ms=round((time.monotonic()-t)*1000,3),lock_exists=Path(str(target)+'.lock').exists())
finally:
    if holder and holder.poll() is None:holder.kill();holder.wait()
    cleanup(r)

# 5. wait-tock timeout/new round and malformed tock JSON shape.
r=root()
try:
    for tag,value in [('timeout',{'round':0}),('new',{'round':3}),('array',[1]),('scalar',2),('bad_round',{'round':'3'})]:
        write_json(str(r/'tock.json'),value)
        q=subprocess.run([sys.executable,str(BIN/'aos7-wait-tock'),'--task',str(r),'--after','1','--timeout','.05'],capture_output=True,text=True,timeout=2)
        save('wait_tock_'+tag,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr)
finally:cleanup(r)

# 6. max_live cap and healthy batch all enter same round.
r=root()
try:
    setup(r,100,[{'name':'s','mode':'each','argv':['sleep','60'],'max_live':2}])
    for n in range(4):
        q=subprocess.run([sys.executable,str(BIN/'aos7-tick'),str(r),'.'],capture_output=True,text=True,timeout=3)
        time.sleep(.06)
    before=aos7_task.live_tasks(str(r))
    write_json(str(r/'.aos/spawn/batch.json'),{'batch':[{'name':'b'+str(i),'argv':['true']} for i in range(3)]})
    q=subprocess.run([sys.executable,str(BIN/'aos7-tick'),str(r),'.'],capture_output=True,text=True,timeout=3)
    save('max_live_and_batch',live_after_four=before,batch_stdout=q.stdout,batch_rc=q.returncode,birth_rounds=[aos7_task.birth_of(str(r/'.aos/tasks'/t)).get('round') for t in json.loads(q.stdout)['started']])
finally:cleanup(r)

# 7. One malformed item in batch poisons the rest of batch and ordinary tasks.
r=root()
try:
    setup(r,80,[{'name':'regular','argv':['true']}])
    write_json(str(r/'.aos/spawn/poison.json'),{'batch':[{'name':'prefix','argv':['true']},{'name':7,'argv':['true']},{'name':'suffix','argv':['true']}]})
    attempts=[]
    for n in range(2):
        q=subprocess.run([sys.executable,str(BIN/'aos7-tick'),str(r),'.'],capture_output=True,text=True,timeout=3)
        attempts.append({'rc':q.returncode,'stderr':q.stderr[-1100:],'round':read_json(str(r/'.aos/round.json'))})
        time.sleep(.08)
    save('poison_spawn_batch',attempts=attempts,tasks=aos7_task.list_tasks(str(r)),spawn_remains=(r/'.aos/spawn/poison.json').exists())
finally:cleanup(r)
Path(__file__).with_name('results.json').write_text(json.dumps(RESULT,ensure_ascii=False,indent=2)+'\n')
