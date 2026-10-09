#!/usr/bin/env python3
"""Independent pack4 CLI/file-protocol probes; only Python standard library.
Rerun from repo root: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/pack4/probe.py
The driver re-execs inside a TasksMax=800, RuntimeMaxSec=1800 systemd scope.
All product descendants inherit the scope. No production/test implementation imports.
"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess as sp
import sys
import tarfile
import tempfile
import time
import traceback

HERE = Path(__file__).resolve().parent
TOP = next(p for p in HERE.parents if p.name == 'proto7-2')
REPO = TOP.parent
PY = sys.executable
STEP = TOP/'packs/step/bin/aos7-step'
BUDGET = TOP/'packs/budget/bin/aos7-budget'
HOOK = TOP/'tests/_hooks.py'
ROOT = None
ROWS = []
PROCS = []
SNAPS = []
EVENTS = []

def write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name+'.probe-tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1)+'\n')
    os.replace(tmp, p)

def read(p, default=None):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return default

def wait(pred, why, timeout=12):
    end = time.monotonic()+timeout
    while time.monotonic() < end:
        v = pred()
        if v:
            return v
        time.sleep(.02)
    raise AssertionError('timeout: '+why)

def environment(extra=None):
    env = {k:v for k,v in os.environ.items() if not k.startswith('AOS7_')}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env.update(extra or {})
    return env

def call(argv, cwd=None, extra=None, timeout=20):
    p = sp.run([str(x) for x in argv], cwd=cwd or REPO, env=environment(extra),
               capture_output=True, text=True, timeout=timeout)
    try:
        obj = json.loads(p.stdout)
    except ValueError:
        obj = None
    return dict(rc=p.returncode, stdout=p.stdout, stderr=p.stderr, obj=obj)

def pop(argv, cwd, extra=None):
    out = open(cwd/('process-%s.out'%len(PROCS)), 'w')
    err = open(cwd/('process-%s.err'%len(PROCS)), 'w')
    p = sp.Popen([str(x) for x in argv], cwd=cwd, env=environment(extra),
                 stdout=out, stderr=err, start_new_session=True)
    out.close(); err.close(); PROCS.append(p)
    return p

def stop(p):
    if p.poll() is None:
        p.kill()
    p.wait(10)

def own_live(root):
    out = []
    for d in Path('/proc').iterdir():
        if not d.name.isdigit() or int(d.name) == os.getpid():
            continue
        try:
            env = (d/'environ').read_bytes().split(b'\0')
            match = any(e.startswith(b'AOS7_ROOT=') and
                        (e.split(b'=',1)[1] == str(root).encode() or
                         e.split(b'=',1)[1].startswith(str(root).encode()+b'/')) for e in env)
            if match:
                raw = (d/'stat').read_text().rsplit(')',1)[1].split()
                if raw[0] != 'Z':
                    out.append(dict(pid=int(d.name), start=raw[19], state=raw[0]))
        except OSError:
            pass
    return out

def clean_procs(root):
    killed = []
    for _ in range(4):
        live = own_live(root)
        for p in live:
            try:
                raw = Path('/proc/%d/stat'%p['pid']).read_text().rsplit(')',1)[1].split()
                if raw[19] == p['start']:
                    os.kill(p['pid'], signal.SIGKILL)
                    killed.append(p)
            except (OSError, ProcessLookupError):
                pass
        time.sleep(.05)
    for p in PROCS:
        if p.poll() is None and str(root) == str(ROOT):
            stop(p)
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
            if pid == 0: break
        except ChildProcessError:
            break
    return dict(killed=killed, remaining=own_live(root))

def snapshot(b, name, final):
    dst = HERE/'snapshots'/name
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(b, dst)
    SNAPS[:]=[s for s in SNAPS if s['name']!=name]
    SNAPS.append(dict(name=name, final=final))
    write(HERE/'snapshots.json', SNAPS)

def hookenv(n, rules):
    return {'AOS7_TEST_HOOKS':str(HOOK), 'AOS7_TEST_FAULT':rules,
            'AOS7_TEST_FAULT_HITS':str(n/'hits.tsv')}

def envargv(env, argv):
    return ['/usr/bin/env']+['%s=%s'%x for x in env.items()]+[str(x) for x in argv]

class Node:
    def __init__(self, name, budget=False):
        self.root = ROOT/name
        self.n = self.root/'n'
        self.jd = self.n/'jobs/j'
        self.b = self.n/'budget/demo'
        write(self.n/'.aos/tasks.json', {'tasks':[]})
        write(self.n/'.aos/timeline.json', {'interval_ms':50})
        self.rounds=[]
        if budget:
            write(self.b/'grant.json', dict(v=1, grant='g1', budget='demo', holder='api',
                resource='fakeapi.calls', gateway='fakeapi', amount=10, clock='completed_tock',
                **{'from':0,'until':10000,'delegate':False}))
            r=self.bcli('init'); assert r['rc']==0, r

    def bcli(self, op, request=None, args=(), extra=None):
        a=[PY,BUDGET,op,'budget/demo']
        if request is not None: a+=['--holder','api','--request',request]
        return call(a+list(args), self.n, extra)

    def scli(self, op, *args):
        return call([PY,STEP,op,'jobs/j',*args], self.n)

    def frame(self): return read(self.jd/'frame.json', {})
    def hits(self):
        p=self.n/'hits.tsv'
        return p.read_text().splitlines() if p.exists() else []

    def install(self, run, budget=False, interp_env=None, **fields):
        step=dict(run=[str(x) for x in run], finite=True, idempotent=True, ok='done', **fields)
        write(self.jd/'steps.json', {'job':'j','start':'call','steps':{'call':step,'done':{'end':'ok'}}})
        items=[]
        if budget: items.append({'name':'ledger','mode':'keep','argv':[PY,str(BUDGET),'ledger','budget/demo']})
        argv=[PY,str(STEP),'run','jobs/j']
        if interp_env: argv=envargv(interp_env,argv)
        items.append({'name':'interp','mode':'keep','argv':argv})
        write(self.n/'.aos/tasks.json', {'tasks':items})

    def tick(self):
        r=call([PY,TOP/'bin/aos7-tick',self.root,'n'])
        assert r['rc']==0, r
        self.rounds.append({'tick':r['obj']})
        return r['obj']

    def tock(self):
        r=call([PY,TOP/'bin/aos7-tock',self.root,'n'])
        assert r['rc']==0, r
        self.rounds[-1]['tock']=r['obj']
        return r['obj']

    def cycle(self, sync=True):
        r=self.tick(); rnd=r['round']
        if any(x.startswith('interp#') for x in r.get('started',[])):
            wait(lambda:(self.frame().get('seen') or 0)>=rnd or
                 self.frame().get('phase')=='ended' or
                 (self.n/'.aos/tasks/interp/exit.json').exists() or
                 (self.jd/'error.json').exists(), 'interpreter startup')
        time.sleep(.075)
        self.tock()
        if sync:
            wait(lambda:self.frame().get('phase')=='ended' or
                 (self.frame().get('tock') or 0)>=rnd or
                 (read(self.jd/'error.json',{}).get('tock') or 0)>=rnd or
                 (self.n/'.aos/tasks/interp/exit.json').exists(), 'interpreter tock %d'%rnd)
        return rnd

    def until(self, pred, limit=20):
        for _ in range(limit):
            if pred(): return
            self.cycle()
        assert pred(), self.frame()

    def kill_task(self, task):
        slot=self.n/'.aos/tasks'/task
        birth=read(slot/'birth.json'); assert birth, str(slot)
        r=call([PY,TOP/'bin/aos7-ctl','task',slot,'kill','--run',str(birth['run'])])
        assert r['rc']==0,r
        return r

    def evidence(self):
        d=HERE/'cases'/self.root.name
        if d.exists(): shutil.rmtree(d)
        shutil.copytree(self.n,d)
        write(d/'rounds.json',self.rounds)
        return str(d.relative_to(HERE))

def budget_unknown(mode):
    x=Node('unknown-'+mode,True)
    rule=x.n/'rules'; rule.write_text('open:*/backend.json:EIO')
    run=envargv(hookenv(x.n,'@'+str(rule)), [PY,BUDGET,'call','budget/demo','--holder','api','--request','${request}'])
    fields={'on_unknown':'resend', 'max_resends':1}
    if mode!='default': fields['unknown_codes']=[3]
    x.install(run,budget=True,**fields)
    if mode=='recover':
        x.until(lambda:str((x.frame().get('pending') or {}).get('attempt','')).endswith('-a2'))
        before=x.frame(); req=before['pending']['request']
        r1=read(x.jd/'results/call'/(req+'-a1.json')); assert r1['code']==3,r1
        assert before['resends'][req]==1,before
        snapshot(x.b,x.root.name+'-fault',False)
        rule.write_text('')
    else:
        x.until(lambda:x.frame().get('phase')=='halted')
        before=x.frame()
        req=(before['pending'] or before['accepted']['call'])['request']
        assert before['halt']['kind']==('failed' if mode=='default' else 'unknown'), before
        assert before['tries'][req]==(1 if mode=='default' else 2), before
        if mode!='default': assert before['resends'][req]==1,before
        for _ in range(3): x.cycle()
        assert x.frame()['tries']==before['tries']
        snapshot(x.b,x.root.name+'-fault',False)
        rule.write_text('')
        r=x.scli('resume','--resend'); assert r['rc']==0,r
        resumed=x.frame(); assert resumed['resends'].get(req,0)==0,resumed
    assert x.hits(), 'EIO did not hit'
    x.until(lambda:x.frame().get('phase')=='ended')
    after=x.frame(); L=read(x.b/'ledger.json'); B=read(x.b/'backend.json')
    assert after['accepted']['call']['request']==req and after['end']=='ok',after
    assert (L['used'],L['inflight'],len(L['ops']),B['accepted'])==(1,0,1,1),(L,B)
    if mode=='recover': assert after['accepted']['call']['attempt']==req+'-a2',after
    snapshot(x.b,x.root.name+'-final',True)
    return dict(injection=x.hits(),before=before,after=after,ledger={k:L[k] for k in ('used','inflight','available')},
                backend_accepted=B['accepted'], assertions='same request; rc3; automatic cap; manual reset; settled exactly once',
                evidence=x.evidence())

def direct_budget(kind):
    x=Node(kind,True)
    # These direct CLI cases use a synthetic fixed completed_tock; integration cases above use real tick/tock.
    write(x.n/'.aos/round.json', {'round':5,'open':False})
    p=pop([PY,BUDGET,'ledger','budget/demo'],x.n)
    try:
        if kind=='payload':
            payload=x.n/'payload.json'; write(payload,{'echo':'hello'})
            r=x.bcli('call','eio',args=['--payload',payload],extra=hookenv(x.n,'open:*/payload.json:EIO'))
            assert r['rc']==3 and r['obj']['outcome']=='unknown' and r['obj']['stage']=='payload',r
            assert len(r['stdout'].strip().splitlines())==1 and 'Traceback' not in r['stderr'],r
            bad=x.n/'bad.json';bad.write_text('{')
            controls=[x.bcli('call','missing',args=['--payload',x.n/'absent.json']),x.bcli('call','bad',args=['--payload',bad])]
            assert all(q['rc']==2 for q in controls),controls
            assert read(x.b/'ledger.json')['ops']=={},'payload errors submitted requests'
            assert x.hits()
            data=dict(injection=x.hits(),fault=r,controls=controls,assertions='payload EIO rc3 single unknown JSON, stage payload; missing/bad rc2; no request')
        elif kind=='replay':
            out=x.n/'out.json'; initial=x.bcli('call','r',args=['--out',out]);assert initial['rc']==0,initial
            sha=lambda:hashlib.sha256(out.read_bytes()).hexdigest()
            before=sha()
            r=x.bcli('call','r',args=['--out',out],extra=hookenv(x.n,'open:*/gateway/*.json:EIO'))
            assert r['rc']==3 and r['obj']['stage']=='replay' and sha()==before,r
            assert x.hits()
            after_sha=sha()
            recovered=x.bcli('call','r',args=['--out',out]);assert recovered['rc']==0 and recovered['obj']['response'] is not None,recovered
            assert read(x.b/'ledger.json')['used']==1 and read(x.b/'backend.json')['accepted']==1
            data=dict(injection=x.hits(),fault=r,before_sha256=before,after_sha256=after_sha,recovered=recovered,
                      assertions='gateway replay EIO rc3; output bytes unchanged; restored replay delivers response, one effect')
        else:
            r=[x.bcli('call','r1',args=['--amount','2']),x.bcli('call','r2')]
            assert all(q['rc']==0 for q in r),r
            L=read(x.b/'ledger.json');B=read(x.b/'backend.json')
            assert (L['used'],L['available'],L['inflight'],B['accepted'])==(3,7,0,2),(L,B)
            data=dict(injection='none; real CLI amount 2 + default 1',calls=r,used=L['used'],available=L['available'],accepted=B['accepted'],assertions='weighted cost 3; two requests; initial 10 available 7')
        snapshot(x.b,kind+'-final',True)
        data['evidence']=x.evidence()
        return data
    finally: stop(p)

def counter_run(gate=False,code=0):
    return [PY,HERE/'worker.py','${job}','${request}','${attempt}', 'gate' if gate else str(code)]

def ran(x): return (x.jd/'ran.jsonl').read_text().splitlines() if (x.jd/'ran.jsonl').exists() else []

def intent(mode):
    x=Node('intent-'+mode)
    fields={}
    if mode=='resend': fields['on_unknown']='resend'
    if mode=='receipt': fields['receipt']={'exists':'${job}/receipt'}
    x.install(counter_run(), **fields)
    (x.jd/'.step-crash').write_text('after-intent')
    t=x.tick(); rnd=t['round']
    ex=wait(lambda:read(x.n/'.aos/tasks/interp/exit.json'), 'after-intent death')
    assert ex['code']==-9,ex
    before=x.frame();p=before['pending']; req=p['request']
    assert p['state']=='intent' and not ran(x),before
    tasks=read(x.n/'.aos/tasks.json');assert not any(i['name']=='step-j-call' for i in tasks['tasks'])
    if mode=='same-round':
        # Real tick refuses to relaunch a keep within this already-open round. Restart the real CLI manually,
        # using the six env fields of its just-dead task, with no second interpreter alive.
        env={'AOS7_ROOT':str(x.root),'AOS7_NODE':str(x.n),'AOS7_NODE_ID':'n',
             'AOS7_TASK':str(x.n/'.aos/tasks/interp'),'AOS7_TID':'interp','AOS7_RUN':str(ex['run'])}
        q=pop([PY,STEP,'run','jobs/j'],x.n,env)
        wait(lambda:(x.frame().get('pending') or {}).get('state')=='queued','same-round readd')
        queued=x.frame();assert queued['pending']['attempt']==req+'-a1',queued
        stop(q)
        x.tock()
    else:
        x.tock()
        if mode=='receipt': (x.jd/'receipt').write_text('external durable receipt')
    x.until(lambda:x.frame().get('phase') in ('halted','ended'))
    after=x.frame()
    if mode=='stop':
        assert after['halt']['kind']=='unknown' and after['pending']['attempt']==req+'-a1' and len(ran(x))==0,after
        r=x.scli('resume','--resend');assert r['rc']==0,r
        x.until(lambda:x.frame().get('phase')=='ended')
        assert len(ran(x))==1 and x.frame()['accepted']['call']['attempt']==req+'-a2'
    elif mode=='receipt':
        assert after['accepted']['call']['receipt'] is True and len(ran(x))==0 and after['tries'][req]==1,after
    elif mode=='resend':
        assert after['resends'][req]==1 and after['accepted']['call']['attempt']==req+'-a2' and len(ran(x))==1,after
    else:
        assert after['accepted']['call']['attempt']==req+'-a1' and len(ran(x))==1 and after['tries'][req]==1,after
    return dict(injection={'crash_point':'after-intent','exit':ex,'round':rnd,'table_after_crash':tasks},
                before=before,after=after,final=x.frame(),ran=ran(x),assertions='expired intent policy / same-round readd identity and execution count',evidence=x.evidence())

def resends_write_fail(op='open'):
    x=Node('resend-'+op+'-fail'+os.environ.get('PACK4_REPEAT',''))
    rules=x.n/'rules';rules.write_text('')
    x.install(counter_run(True),interp_env=hookenv(x.n,'@'+str(rules)),on_unknown='resend',max_resends=1)
    x.until(lambda:len(ran(x))==1)
    first=x.frame();req=first['pending']['request']
    # Only writes in the interpreter fail. Real tick/tock can continue reading/writing their table.
    rules.write_text(op+':*/tasks.json:EIO')
    x.kill_task('step-j-call')
    x.until(lambda:bool(x.hits()))
    wait(lambda:(x.jd/'error.json').exists(),'failed dispatch records error')
    broken=x.frame();assert broken['resends'][req]==1 and broken['tries'][req]==2,broken
    assert len(ran(x))==1
    rules.write_text('')
    if op=='write' and broken['pending'] is not None:
        x.until(lambda:x.frame().get('phase')=='halted')
        after=x.frame()
        for _ in range(3):x.cycle()
        actual=dict(injection=x.hits(),first=first,table_write_failed=broken,error=read(x.jd/'error.json'),
                    after=after,ran=ran(x),expected_ran=2,actual_ran=len(ran(x)),
                    assertions='request resend counter survives; write EIO leaves intent; next round stops before second execution',
                    acceptance_pass=False)
        assert after['halt']['kind']=='unknown' and len(ran(x))==1,actual
        (x.jd/'release').write_text('allow manual recovery to finish')
        r=x.scli('resume','--resend');assert r['rc']==0,r
        resumed=x.frame();assert resumed['resends'].get(req,0)==0,resumed
        x.until(lambda:x.frame().get('phase')=='ended')
        final=x.frame();assert len(ran(x))==2 and final['accepted']['call']['request']==req,final
        actual.update(manual_resume=resumed,manual_final=final,manual_final_ran=ran(x),evidence=x.evidence())
        return actual
    assert broken['pending'] is None,broken
    x.until(lambda:len(ran(x))==2)
    second=x.frame()
    x.kill_task('step-j-call')
    x.until(lambda:x.frame().get('phase')=='halted')
    after=x.frame()
    for _ in range(3):x.cycle()
    assert after['halt']['kind']=='unknown' and after['resends'][req]==1 and len(ran(x))==2,after
    return dict(injection=x.hits(),first=first,table_write_failed=broken,second_actual_run=second,after=after,ran=ran(x),
        assertions='max_resends request budget survives failed dispatch; only two executions; halt unknown (failed dispatch still consumes attempt number)',evidence=x.evidence())

def validation():
    x=Node('validation')
    values=[[],[3,3],[0],[256],[-1],[True],[1.5],['3'],[{}],[[3]],None,3,{},[1],[2],[3],[255],[1,2,3,255]]
    rows=[]
    for v in values:
        x.install(counter_run(),unknown_codes=v)
        r=call([PY,STEP,'check',x.jd/'steps.json'],x.n)
        valid=isinstance(v,list) and bool(v) and all(type(c) is int and 1<=c<=255 for c in v) and len(set(v))==len(v)
        assert r['rc']==(0 if valid else 1) and 'Traceback' not in r['stderr'],(v,r)
        rows.append(dict(value=v,expected_valid=valid,result=r))
    for k,s in [('wait',{'wait':{'exists':'x'},'then':'done'}),('count',{'count':1,'then':'done','exhausted':'done'}),('end',{'end':'ok'})]:
        t={'job':'j','start':'call','steps':{'call':dict(s,unknown_codes=[3]),'done':{'end':'ok'}}}
        write(x.jd/'steps.json',t)
        r=call([PY,STEP,'check',x.jd/'steps.json'],x.n);assert r['rc']==1,r
        rows.append(dict(non_run=k,result=r))
    return dict(injection='invalid/valid authored steps files before execution',assertions='18 run values + 3 non-run types validated without traceback',rows=rows)

def misuse(code):
    x=Node('misuse-code-'+str(code))
    x.install(counter_run(code=code),unknown_codes=[code],on_unknown='resend')
    x.until(lambda:x.frame().get('phase')=='halted')
    fr=x.frame();req=fr['pending']['request']
    assert len(ran(x))==2 and fr['halt']['kind']=='unknown' and fr['resends'][req]==1,fr
    return dict(classification='M',injection='non-idempotent append falsely declared idempotent, code listed as unknown',
                assertions='false idempotence declaration repeats effects; finite resend cap holds',frame=fr,ran=ran(x),evidence=x.evidence())

def case(name, fn):
    before=len(EVENTS); start=time.monotonic()
    try: data=fn(); row=dict(scenario=name,pass_=data.get('acceptance_pass',True),data=data)
    except Exception as e: row=dict(scenario=name,pass_=False,error=repr(e),traceback=traceback.format_exc())
    row['seconds']=round(time.monotonic()-start,3)
    ROWS.append(row);write(HERE/'results.json',ROWS)
    print(json.dumps({'scenario':name,'pass':row['pass_'],'seconds':row['seconds'],'error':row.get('error')},ensure_ascii=False),flush=True)
    # Per-case cleanup only targets roots created by this driver, identified by exact AOS7_ROOT prefix.
    clean_procs(ROOT)

def main():
    global ROOT
    if os.environ.get('PACK4_SCOPED') != '1':
        return sp.call(['systemd-run','--user','--scope','-q','-p','TasksMax=800','-p','RuntimeMaxSec=1800',
            '/usr/bin/env','PACK4_SCOPED=1','PYTHONDONTWRITEBYTECODE=1',PY,str(Path(__file__).resolve()),*sys.argv[1:]],cwd=REPO)
    ctypes.CDLL(None).prctl(36,1,0,0,0)  # Adopt/reap only this probe's orphaned product descendants.
    ROOT=Path(tempfile.mkdtemp(prefix='astra7-pack4-probe-'))
    selected=set(sys.argv[1:])
    if selected:
        ROWS.extend(r for r in read(HERE/'results.json',[]) if r['scenario'] not in selected)
        SNAPS.extend(read(HERE/'snapshots.json',[]))
    cases=[('unknown-recover',lambda:budget_unknown('recover')),('unknown-exhaust',lambda:budget_unknown('exhaust')),
        ('unknown-default',lambda:budget_unknown('default'))]
    cases += [(k,lambda k=k:direct_budget(k)) for k in ('payload','replay','weighted')]
    cases += [('intent-'+k,lambda k=k:intent(k)) for k in ('receipt','resend','stop','same-round')]
    cases += [('resend-open-fail',resends_write_fail),('resend-write-fail',lambda:resends_write_fail('write')),('validation',validation)]
    cases += [('misuse-code-'+str(k),lambda k=k:misuse(k)) for k in (1,2)]
    try:
        for name,fn in cases:
            if not selected or name in selected: case(name,fn)
    finally:
        cleanup=clean_procs(ROOT)
        cleanup.update(root=str(ROOT),direct_children=[{'pid':p.pid,'rc':p.poll()} for p in PROCS])
        assert not cleanup['remaining'],cleanup
        shutil.rmtree(ROOT);cleanup['root_removed']=not ROOT.exists()
        write(HERE/'probe-cleanup.json',cleanup)
    return int(any(not r['pass_'] for r in ROWS))

if __name__=='__main__': sys.exit(main())
