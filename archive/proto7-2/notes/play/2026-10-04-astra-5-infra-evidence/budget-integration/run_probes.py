#!/usr/bin/env python3
import contextlib, fcntl, copy, hashlib, json, os, shutil, signal, subprocess, sys, tempfile, time, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
TOP=HERE.parents[3]
BIN=TOP/'packs/budget/bin/aos7-budget'
sys.path.insert(0,str(HERE)); from audit import audit
sys.path[:0]=[str(TOP/'packs/budget/tests'),str(TOP/'tests')]
import test_budget_step as st
RESULT=[]; AUDITS=[]; CLEANUPS=[]; SNAP=HERE/'snapshots'/str(time.time_ns()); SNAP.mkdir(parents=True,exist_ok=True)

def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.new'); tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)); os.replace(tmp,path)
def load(path): return json.loads(path.read_text())
def sha(obj): return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def snapshot(bd,name,final=False):
    dest=SNAP/name; dest.mkdir(parents=True,exist_ok=True)
    # Freeze all budget writers while copying: ledger, each known K's gateway, backend.
    # No package imports: flock the documented lock files directly.
    with contextlib.ExitStack() as stack:
        def lock(path):
            path.parent.mkdir(parents=True,exist_ok=True)
            fh=stack.enter_context(path.open('a')); fcntl.flock(fh,fcntl.LOCK_EX)
        lock(Path(bd)/'ledger.json.lock')
        keys=set(load(Path(bd)/'ledger.json')['ops'])
        keys.update(f.stem for f in (Path(bd)/'gateway').glob('*.json'))
        for k in sorted(keys): lock(Path(bd)/'gateway'/(k+'.json.lock'))
        lock(Path(bd)/'backend.json.lock')
        for f in Path(bd).rglob('*.json'):
            rel=f.relative_to(bd)
            if rel.parts[0] in ('inbox','receipts'): continue
            out=dest/rel; out.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(f,out)
    r=audit(dest,final); AUDITS.append(r); assert r['ok'],r
    return dest

def clock(node,c,open_=False): dump(node/'.aos/round.json',{'round':c+1 if open_ else c,'open':open_})
def cli(node,*args):
    p=subprocess.run([sys.executable,str(BIN),*args],cwd=node,capture_output=True,text=True,timeout=10,start_new_session=True)
    return {'code':p.returncode,'out':json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else None,'err':p.stderr}
def grant(**kw):
    g={'v':1,'grant':'g1','budget':'demo','holder':'api','resource':'fakeapi.calls','gateway':'fakeapi','amount':20,'clock':'completed_tock','from':5,'until':10,'delegate':False}; g.update(kw); return g

def own_clock_probes():
    root=Path(tempfile.mkdtemp(prefix='astra5-budget-integration-')); procs=[]
    try:
        def setup(name,**g):
            node=root/name; bd=node/'budget/demo'; dump(bd/'grant.json',grant(**g)); clock(node,4)
            assert cli(node,'init','budget/demo')['code']==0
            p=subprocess.Popen([sys.executable,str(BIN),'ledger','budget/demo'],cwd=node,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True); procs.append(p)
            return node,bd
        def call(node,request): return cli(node,'call','budget/demo','--holder','api','--request',request)
        node,bd=setup('boundaries')
        before=call(node,'before'); assert before['code']==3
        clock(node,5,True); atfrom=call(node,'from'); assert atfrom['code']==0
        clock(node,9); beforeuntil=call(node,'before-until'); assert beforeuntil['code']==0
        clock(node,10,True); atuntil=call(node,'until'); assert atuntil['code']==1
        clock(node,8); rollback=call(node,'rollback'); assert rollback['code']==3
        RESULT.append({'case':'clock_boundaries_open_closed_rollback_below_success_hw','pass':True,'observed':[before,atfrom,beforeuntil,atuntil,rollback]}); snapshot(bd,'clock-boundaries',True)
        node,bd=setup('intent-expiry'); clock(node,9); (bd/'.crash').write_text('gateway-after-intent')
        killed=call(node,'admitted'); assert killed['code']==-signal.SIGKILL
        snapshot(bd,'intent-before-expiry')
        clock(node,10); resumed=call(node,'admitted'); assert resumed['code']==0
        denied=call(node,'new-after-expiry'); assert denied['code']==1
        RESULT.append({'case':'intent_SIGKILL_recover_at_until','pass':True,'observed':[killed,resumed,denied]}); snapshot(bd,'intent-after-expiry',True)
        node,bd=setup('highwater-denied'); clock(node,5); assert call(node,'seed')['code']==0
        clock(node,10); expired=call(node,'expired'); assert expired['code']==1
        high_after_expired=load(bd/'ledger.json')['clock_hw']
        clock(node,6); regressed=call(node,'after-regress')
        RESULT.append({'case':'clock_highwater_after_expired_observation','classification':'M','rollback_detected':regressed['code']==3,'observed':[expired,{'clock_hw':high_after_expired},regressed], 'note':'synthetic repaired/rebuilt clock; classification must honor README forbids transplanting old grant'})
        snapshot(bd,'highwater-after-denied',True)
        # Observe time at gateway admission above the reservation high-water mark.
        node,bd=setup('highwater-gateway'); clock(node,5); (bd/'.crash').write_text('call-after-reserve')
        assert call(node,'one')['code']==-signal.SIGKILL
        clock(node,9); assert call(node,'one')['code']==0
        high_after_gateway=load(bd/'ledger.json')['clock_hw']
        clock(node,6); regressed=call(node,'two')
        RESULT.append({'case':'clock_highwater_after_gateway_observation','classification':'M','rollback_detected':regressed['code']==3,'observed':[{'admitted_at':9,'clock_hw':high_after_gateway},regressed], 'note':'synthetic repaired/rebuilt clock; classification must honor README forbids transplanting old grant'})
        snapshot(bd,'highwater-after-gateway',True)
        # A paused/unknown clock must not expire patience by wall time.
        node,bd=setup('patience'); p=procs[-1]; p.terminate(); p.wait(5); clock(node,5)
        waiter=subprocess.Popen([sys.executable,str(BIN),'call','budget/demo','--holder','api','--request','wait','--patience','1'],cwd=node,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True); procs.append(waiter)
        time.sleep(.3); paused=waiter.poll() is None
        clock(node,6); out,err=waiter.communicate(timeout=5); assert paused and waiter.returncode==3
        RESULT.append({'case':'patience_paused_clock_then_one_completed_tock','pass':True,'wall_wait_without_timeout':.3,'out':json.loads(out)})
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
                try:p.wait(5)
                except subprocess.TimeoutExpired:p.kill();p.wait(5)
        ids=[p.pid for p in procs]
        ps=subprocess.run(['ps','-o','pid=,stat=,args=','-p',','.join(map(str,ids))],capture_output=True,text=True)
        dump(HERE/'own-cleanup.json',{'root':str(root),'pids':ids,'ps':ps.stdout,'all_reaped':all(p.poll() is not None for p in procs)})
        shutil.rmtree(root)

class Capture:
    def doCleanups(self):
        root=self.root
        result=super().doCleanups()
        live=[]
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit(): continue
            try:
                env=(entry/'environ').read_bytes().split(b'\0')
                target=('AOS7_ROOT='+root).encode()
                if any(e==target or e.startswith(target+b'/') for e in env):
                    stat=(entry/'stat').read_text().split(') ',1)[1].split()[0]
                    if stat!='Z': live.append(int(entry.name))
            except OSError: pass
        ps=subprocess.run(['ps','-o','pid=,stat=,args=','-p',','.join(map(str,live))],capture_output=True,text=True) if live else None
        CLEANUPS.append({'case':self._testMethodName,'root':root,'root_removed':not Path(root).exists(),'live_pids':live,'ps':ps.stdout if ps else ''})
        return result
    def audit(self,bd,final=False):
        number=getattr(self,'snap_n',0)+1; self.snap_n=number
        name=self._testMethodName+'-'+str(number)
        dest=snapshot(bd,name,final)
        node=Path(bd).parents[1]
        for source, label in [(node/'.aos/round.json','node-round.json'),(node/'jobs/api/frame.json','step-frame.json')]:
            if source.exists(): shutil.copy2(source,dest/label)
        return load(Path(bd)/'ledger.json')

class Daemon(Capture,st.TestBudgetDaemon):
    def test_pause_SIGKILL_daemon_restart(self):
        node=self.mknode('a',interval_ms=40)
        self.set_tasks(node,self.install(node,g=st.grant(until=10**6)))
        p=self.start_daemon(register=['a']); self.wait_job_end(node); self.wait_round(5)
        self.prog('aos7-ctl','daemon',self.root,'pause','a','--owner','astra5')
        self.wait_for(lambda:self.nstat().get('phase')=='paused')
        c0=st.bg.completed_tock(node); generation=self.status()['gen']
        time.sleep(.4); self.assertEqual(st.bg.completed_tock(node),c0)
        p.kill(); self.assertEqual(p.wait(5),-signal.SIGKILL)
        self.start_daemon()
        self.wait_for(lambda:self.status().get('gen',0)>generation)
        time.sleep(.2); self.assertEqual(st.bg.completed_tock(node),c0)
        self.prog('aos7-ctl','daemon',self.root,'resume','a','--owner','astra5')
        self.wait_for(lambda:(st.bg.completed_tock(node) or 0)>c0)
        rc,out=self.call(node,'post-SIGKILL'); self.assertEqual(rc,0,out)
        L=self.audit(self.bd,final=True); self.assertEqual(L['used'],2)
        RESULT.append({'case':'true_daemon_pause_SIGKILL_restart','pass':True,'clock_before':c0,'clock_after':st.bg.completed_tock(node),'gen_before':generation,'gen_after':self.status()['gen']})
class Step(Capture,st.TestBudgetStepProbes): pass

def negative_controls():
    source=SNAP/'clock-boundaries'
    tests=[]
    for name in ('double-backend-count','bad-log-balance','duplicate-reserve','wrong-evidence-hash','missing-op'):
        with tempfile.TemporaryDirectory(prefix='astra5-audit-negative-') as tmp:
            target=Path(tmp)/'budget'; shutil.copytree(source,target)
            L=load(target/'ledger.json'); b=load(target/'backend.json')
            if name=='double-backend-count': b['accepted']+=1; dump(target/'backend.json',b)
            if name=='bad-log-balance': L['log'][0]['available']+=1
            if name=='duplicate-reserve': L['log'].append(copy.deepcopy(L['log'][0]))
            if name=='wrong-evidence-hash': next(iter(L['ops'].values()))['settle']['evidence']='0'*64
            if name=='missing-op': L['ops'].pop(next(iter(L['ops'])))
            dump(target/'ledger.json',L); r=audit(target,True); assert not r['ok']; tests.append({'mutation':name,'detected':True,'errors':r['errors']})
    dump(HERE/'negative-controls.json',tests)

if __name__=='__main__':
    started=time.monotonic()
    own_clock_probes(); negative_controls()
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Daemon),unittest.defaultTestLoader.loadTestsFromTestCase(Step)])
    with (HERE/'step-unittest.log').open('w') as stream:r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    dump(HERE/'results.json',{'seconds':time.monotonic()-started,'own_probes':RESULT,'step_tests':{'run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors)},'audits':AUDITS,'cleanups':CLEANUPS})
    print(json.dumps({'seconds':time.monotonic()-started,'own_probes':len(RESULT),'step_tests':r.testsRun,'success':r.wasSuccessful(),'audit_snapshots':len(AUDITS)}))

    raise SystemExit(0 if r.wasSuccessful() else 1)
