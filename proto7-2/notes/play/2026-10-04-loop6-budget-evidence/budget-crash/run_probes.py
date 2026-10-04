#!/usr/bin/env python3
"""Independent subprocess QA driver; run from repository root. Never edits source/tests.
Snapshots copied intact before temporary roots are removed. External injector writes
only to its own hit logs, and SIGKILLs the currently executing subprocess by PID.
"""
import json, os, sys, time, signal, subprocess as sp, tempfile, shutil, hashlib, traceback
from pathlib import Path
SCRIPT=Path(__file__).resolve().parent
E=Path(os.environ.get('QA_OUTPUT',str(SCRIPT))).resolve()
E.mkdir(parents=True,exist_ok=True)
REPO=SCRIPT.parents[3]
CLI=REPO/'packs/budget/bin/aos7-budget'
ROOT=Path(tempfile.mkdtemp(prefix='astra5-budget-crash-'))
PROCS=[]; RESULTS=[]; MANIFEST=[]
def write(p,o):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(o,ensure_ascii=False,indent=1))
def load(p): return json.loads(p.read_text()) if p.exists() else None
def wait(pred, timeout=15):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        v=pred()
        if v:return v
        time.sleep(.01)
    raise TimeoutError('predicate')
def setup(name,amount=100):
    n=ROOT/name; b=n/'budget/demo'
    write(n/'.aos/round.json',dict(round=5,open=False))
    write(b/'grant.json',{'v':1,'grant':'g1','budget':'demo','holder':'api','resource':'fakeapi.calls','gateway':'fakeapi','amount':amount,'clock':'completed_tock','from':0,'until':1000,'delegate':False})
    r=cmd(n,'init'); assert r['rc']==0,r
    return n,b
def pop(n,op,request=None,inject=None,extra=()):
    a=[sys.executable,str(CLI),op,'budget/demo']
    if request is not None:a += ['--holder','api','--request',request]
    a+=list(extra)
    env=os.environ.copy(); env.pop('AOS7_TASK',None)
    if inject:
        mode,target=inject; marker=n/('hit-'+mode+'-'+target.replace('/','_')+'.jsonl')
        env.update(PYTHONPATH=str(SCRIPT), QA_MODE=mode,QA_TARGET=target,QA_MARKER=str(marker))
    p=sp.Popen(a,cwd=n,env=env,stdout=sp.PIPE,stderr=sp.PIPE,text=True,start_new_session=True)
    PROCS.append(p);return p
def finish(p,timeout=20):
    out,err=p.communicate(timeout=timeout)
    try:r=json.loads(out.strip().splitlines()[-1])
    except (ValueError,IndexError):r=None
    return dict(pid=p.pid,rc=p.returncode,result=r,stdout=out,stderr=err)
def cmd(n,op,request=None,**kw):return finish(pop(n,op,request,**kw))
def stop(p):
    if p.poll() is None:p.send_signal(signal.SIGKILL)
    p.wait(10)
def snap(b,name,final=True,**meta):
    d=E/'snapshots'/name
    if d.exists(): raise RuntimeError('snapshot already exists: '+name)
    shutil.copytree(b,d)
    MANIFEST.append(dict(name=name,final=final,**meta))
    return d
def basic(b,used=None):
    l=load(b/'ledger.json');assert l['available']+l['inflight']+l['used']==l['initial'],l
    assert min(l[k] for k in ('available','inflight','used'))>=0
    if used is not None:assert l['used']==used and l['inflight']==0,l
    return {k:l[k] for k in ('available','inflight','used','seq')}
def case(name,fn):
    start=time.monotonic()
    try: data=fn(); row=dict(name=name,ok=True,data=data)
    except Exception as ex:row=dict(name=name,ok=False,error=repr(ex),traceback=traceback.format_exc())
    row['seconds']=round(time.monotonic()-start,3);RESULTS.append(row)
    write(E/'results.json',RESULTS);write(E/'snapshots.json',MANIFEST)
    print(json.dumps(row,ensure_ascii=False),flush=True)
def hook(point):
    n,b=setup('hook-'+point); ledger=pop(n,'ledger');(b/'.crash').write_text(point)
    c=pop(n,'call','r')
    if point.startswith(('reserve-','settle-')):
        assert ledger.wait(15)==-9
        snap(b,'hook-'+point+'-interrupted',False)
        ledger=pop(n,'ledger');first=finish(c)
        assert first['rc']==0,first
    else:
        first=finish(c);assert first['rc']==-9,first
        snap(b,'hook-'+point+'-interrupted',False)
    assert not (b/'.crash').exists()
    replay=cmd(n,'call','r');assert replay['rc']==0,replay
    assert cmd(n,'call','r')['rc']==0
    stop(ledger);out=basic(b,1);snap(b,'hook-'+point+'-final');return dict(hit=True,first=first,final=out)
def window(target,mode):
    name='window-'+target+'-'+mode;n,b=setup(name)
    who='ledger' if target.startswith(('ledger-','receipt-')) else 'call'
    ledger=pop(n,'ledger',inject=(mode,target) if who=='ledger' else None)
    c=pop(n,'call','r',inject=(mode,target) if who=='call' else None,extra=('--out',str(n/'out.json')))
    victim=ledger if who=='ledger' else c
    assert victim.wait(15)==-9
    hits=[json.loads(x) for f in n.glob('hit-*.jsonl') for x in f.read_text().splitlines()];assert len(hits)==1,hits
    snap(b,name+'-interrupted',False)
    if who=='ledger':ledger=pop(n,'ledger');assert finish(c)['rc']==0
    replay=cmd(n,'call','r');assert replay['rc']==0,replay
    assert cmd(n,'call','r')['rc']==0
    stop(ledger);out=basic(b,1);snap(b,name+'-final');return dict(hits=hits,final=out)
def concurrent(kind):
    n,b=setup('concurrent-'+kind,17 if kind=='different' else 100)
    ledger=pop(n,'ledger')
    if kind=='same': jobs=[pop(n,'call','same') for _ in range(40)]
    elif kind=='different':jobs=[pop(n,'call','r'+str(i)) for i in range(60)]
    elif kind=='conflict':
        write(n/'p.json',{'mode':'fail'})
        jobs=[pop(n,'call','same',extra=('--payload',str(n/'p.json')) if i%2 else ()) for i in range(40)]
    else:
        jobs=[]
        for i in range(40):
            jobs.extend([pop(n,'call','r'+str(i)),pop(n,'cancel','r'+str(i))])
    outputs=[finish(p) for p in jobs]
    assert all(x['rc'] in (0,1) for x in outputs),outputs
    if kind=='cancel':
        for i in range(40): assert cmd(n,'call','r'+str(i))['rc'] in (0,1)
    stop(ledger);summary=basic(b);l=load(b/'ledger.json');backend=load(b/'backend.json') or {'accepted':0,'effects':{}}
    assert l['inflight']==0
    if kind=='same':assert all(x['rc']==0 for x in outputs) and l['used']==1 and l['seq']==2
    if kind=='different':assert l['used']==17 and backend['accepted']==17 and sum(x['rc']==0 for x in outputs)==17
    if kind=='conflict':assert len(l['ops'])==1 and l['seq']==2 and backend['accepted']==1 and sum(x['result']['outcome']=='conflict' for x in outputs)==20
    if kind=='cancel':
        assert len(l['ops'])==40
        for f in (b/'gateway').glob('*.json'):
            g=load(f);assert g['outcome'] in ('accepted','cancelled')
            assert (g['outcome']=='accepted')==(f.stem in backend['effects'])
    snap(b,'concurrent-'+kind+'-final');return dict(summary=summary,outputs=outputs)
def cancel_at(point):
    n,b=setup('cancel-'+point);l=pop(n,'ledger');(b/'.crash').write_text(point)
    assert cmd(n,'call','r')['rc']==-9
    unknown=cmd(n,'settle','r')
    if point in ('call-after-reserve','gateway-after-intent'):assert unknown['rc']==3
    elif point=='backend-after-effect':assert unknown['rc']==3
    before=basic(b);cancel=cmd(n,'cancel','r')
    expect='accepted' if point=='backend-after-effect' else 'cancelled'
    assert cancel['result']['outcome']==expect,cancel
    late=[cmd(n,'call','r') for _ in range(3)]
    assert all(x['result']['outcome']==expect for x in late),late
    stop(l);final=basic(b,1 if expect=='accepted' else 0);snap(b,'cancel-'+point+'-final')
    return dict(unknown=unknown,before=before,cancel=cancel,late=late,final=final)
def unknown_gateway():
    n,b=setup('unknown-gateway');l=pop(n,'ledger');(b/'.crash').write_text('call-after-reserve')
    assert cmd(n,'call','r')['rc']==-9
    path=n/'.aos/round.json';saved=path.read_bytes();path.write_text('{bad')
    a=cmd(n,'call','r');assert a['rc']==3,a
    assert not list((b/'gateway').glob('*.json'))
    path.write_bytes(saved);z=cmd(n,'call','r');assert z['rc']==0
    stop(l);snap(b,'unknown-gateway-final');return dict(unknown=a,recovered=z,final=basic(b,1),classification='M clock hand-edit probe; demonstrates documented unknown behavior')
def corrupt_ledger(mode):
    n,b=setup('ledger-'+mode);lp=b/'ledger.json';saved=lp.read_bytes()
    if mode=='missing':lp.unlink()
    else:lp.write_text('{bad')
    l=pop(n,'ledger');c=pop(n,'call','r',extra=('--patience','1'))
    wait(lambda:(b/'error.json').exists());assert c.poll() is None
    assert len(list((b/'inbox').glob('*.json')))==1
    write(n/'.aos/round.json',dict(round=6,open=False));r=finish(c);assert r['rc']==3,r
    if mode=='missing':assert not lp.exists()
    else:assert lp.read_text()=='{bad'
    error=load(b/'error.json');lp.write_bytes(saved)
    z=cmd(n,'call','r');assert z['rc']==0,z
    stop(l);snap(b,'ledger-'+mode+'-recovered');return dict(classification='M hand modification/deletion explicitly excluded by spec §8',pending=r,error=error,final=basic(b,1))
def eio(target):
    name='eio-'+target.replace('/','_');n,b=setup(name)
    # Persist reserve or intent before injecting read error; never alter affected data.
    l=pop(n,'ledger');point='gateway-after-intent' if target=='backend.json' else 'call-after-reserve'
    (b/'.crash').write_text(point);assert cmd(n,'call','r')['rc']==-9
    if target=='ledger.json':
        stop(l);l=pop(n,'ledger',inject=('EIO',target));c=pop(n,'call','new',extra=('--patience','1'))
        wait(lambda:(b/'error.json').exists());write(n/'.aos/round.json',dict(round=6,open=False));r=finish(c)
        stop(l);l=pop(n,'ledger')
    else:r=cmd(n,'call','r',inject=('EIO',target))
    hits=[json.loads(x) for f in n.glob('hit-*.jsonl') for x in f.read_text().splitlines()];assert hits,hits
    preserved=basic(b);assert preserved['inflight']==1 and preserved['used']==0
    snap(b,name+'-interrupted',False)
    z=cmd(n,'call','r');assert z['rc']==0,z
    if target=='ledger.json':assert cmd(n,'call','new')['rc']==0
    stop(l);snap(b,name+'-final');return dict(classification='X injected EIO with valid untouched data',failure=r,hits=hits,recovered=z,final=basic(b),unknown_exit_contract=(r['rc']==3))
try:
    for kind in ('same','different','conflict','cancel'):case('concurrent-'+kind,lambda kind=kind:concurrent(kind))
    for point in ('reserve-before-commit','reserve-after-commit','settle-before-commit','settle-after-commit','call-after-reserve','gateway-after-intent','backend-after-effect','gateway-after-receipt','call-after-settle'):case('hook-'+point,lambda p=point:hook(p))
    for target in ('ledger-reserve','ledger-settle','gateway-intent','backend','gateway-done','receipt-reserve','receipt-settle','inbox-reserve','inbox-settle','output'):
        for mode in ('before','after'):case('window-'+target+'-'+mode,lambda t=target,m=mode:window(t,m))
    for point in ('call-after-reserve','gateway-after-intent','backend-after-effect'):case('cancel-'+point,lambda p=point:cancel_at(p))
    case('unknown-gateway',unknown_gateway)
    for mode in ('missing','malformed'):case('ledger-'+mode,lambda m=mode:corrupt_ledger(m))
    for target in ('ledger.json','backend.json'):
        case('eio-'+target,lambda t=target:eio(t))
finally:
    for p in PROCS:stop(p)
    ps=sp.run(['ps','-eo','pid,ppid,pgid,stat,args'],capture_output=True,text=True).stdout
    (E/'cleanup-ps.txt').write_text(ps)
    write(E/'cleanup.json',dict(root=str(ROOT),tracked_pids=[p.pid for p in PROCS],all_waited=all(p.poll() is not None for p in PROCS),remaining_mentions=[x for x in ps.splitlines() if str(ROOT) in x],root_removed=True))
    shutil.rmtree(ROOT)
    write(E/'results.json',RESULTS);write(E/'snapshots.json',MANIFEST)
