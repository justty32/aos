#!/usr/bin/env python3
"""Independent black-box QA. Only fixture files in owned /tmp and evidence are written.
Runs real tasks via unmodified tick/tock; real daemons for timing/pause/restart.
Usage: PYTHONDONTWRITEBYTECODE=1 python3 .../probe.py [matrix|flows]
"""
import os, sys, json, time, tempfile, shutil, signal, subprocess, traceback, tarfile, hashlib
from pathlib import Path
E = Path(__file__).resolve().parent
P = E.parents[3]
sys.path[:0] = [str(P/'lib'), str(P/'modules/tools'), str(P/'packs/adapt')]
import aos7_tick, aos7_tock, aos7_task
from aos7_fs import write_json, read_json
import aos7_adapt as ad
os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ.pop('AOS7_TEST_HOOKS',None)
PY=sys.executable
RESULT=[]
def check(name, yes, **data):
    row=dict(name=name,passed=bool(yes),**data); RESULT.append(row)
    print(json.dumps(row,ensure_ascii=False),flush=True)
def wait(f, timeout=15):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        x=f()
        if x:return x
        time.sleep(.005)
    raise RuntimeError('timeout '+str(f))
def own_pids(root):
    result=[]
    needle=('AOS7_ROOT='+str(root)).encode()
    for p in Path('/proc').iterdir():
        if p.name.isdigit() and int(p.name)!=os.getpid():
            try:
                if needle in (p/'environ').read_bytes().split(b'\0'):result.append(int(p.name))
            except (OSError,ProcessLookupError):pass
    return result
class Space:
    def __init__(self,name,sensor=False,decl=None,src_ms=20,dst_ms=100,step=False):
        self.name=name;self.root=Path(tempfile.mkdtemp(prefix='astra6-adapt-'+name+'-'));self.procs=[]
        self.src=self.root/'src';self.dst=self.root/'dst';self.snap=[]
        self.decl={'sense':'temp','src':'src/out/temp.json','src_clock':'src/.aos/round.json','max_age':None,'patience':2,'stall':None,
            'steps':[{'select':'value.x'},{'scale':{'mul':.1,'q':.05,'round':1,'as':'c'}},{'threshold':{'ge':80,'as':'hot'}}],'need':['c']}
        self.decl.update(decl or {})
        self.sensor=self.root/'sensor.py'
        self.sensor.write_text('import os,sys\nsys.path[:0]='+repr([str(P/'lib'),str(P/'modules/tools')])+'''\nfrom aos7_fs import write_json,read_json
from aos7_taskside import wait_tock
t=os.environ['AOS7_TASK']; last=0;seq=(read_json(t+'/state.json') or {}).get('seq',0)
while True:
 last=wait_tock(t,last,poll=.001);seq+=1
 write_json(t+'/state.json',{'seq':seq})
 write_json('out/temp.json',{'v':1,'round':last,'seq':seq,'value':{'x':801,'other':'omitted'}})
''')
        src_tasks=[{'name':'sensor','mode':'keep','argv':[PY,str(self.sensor)]}] if sensor else []
        dst_tasks=[{'name':'adapter','mode':'keep','max_live':1,'argv':[PY,str(P/'packs/adapt/bin/aos7-adapt'),'run','adapt/temp.json'], 'mounts':{'data':'src/out','clock':'src/.aos'}}]
        if step:
            dst_tasks.append({'name':'gate','mode':'keep','argv':[PY,str(P/'packs/step/bin/aos7-step'),'run','jobs/gate']})
            write_json(str(self.dst/'jobs/gate/steps.json'),{'job':'gate','start':'w','steps':{'w':{'wait':{'num':'in/temp.json','key':'value.c','op':'>=','value':80},'patience':100,'then':'done'},'done':{'end':'ok'}}})
        for n,t,ms in ((self.src,src_tasks,src_ms),(self.dst,dst_tasks,dst_ms)):
            write_json(str(n/'.aos/tasks.json'),{'tasks':t});write_json(str(n/'.aos/timeline.json'),{'interval_ms':ms})
        write_json(str(self.dst/'adapt/temp.json'),self.decl)
    def slot(self,name='adapter',node=None):return Path(aos7_task.slot_dir(str(node or self.dst),name))
    def reg(self):return read_json(str(self.dst/'in/temp.json')) or {}
    def frame(self):return read_json(str(self.slot()/'state.json')) or {}
    def source(self,seq,x=801):
        r=read_json(str(self.src/'.aos/round.json')) or {'round':0,'open':False}
        write_json(str(self.src/'out/temp.json'),{'v':1,'seq':seq,'round':r['round']-int(r['open']),'value':{'x':x,'other':'omitted'}})
    def cycle(self,node='dst'):
        r=aos7_tick.tick(str(self.root),node)['round']
        aos7_tock.tock(str(self.root),node)
        if node=='dst':
            z=wait(lambda:self.reg() if self.reg().get('my_round')==r else None)
            self.snap.append(z);return z
        return r
    def boot(self):self.cycle('src');self.source(1);return self.cycle()
    def ctl(self,op,*args):
        p=subprocess.run([PY,str(P/'bin/aos7-ctl'),'daemon',str(self.root),op,*args],capture_output=True,text=True,timeout=15)
        if p.returncode:raise RuntimeError(p.stderr)
        return json.loads(p.stdout)
    def daemon(self,register=True):
        if register:
            for n in ('src','dst'):self.ctl('register',n)
        log=open(E/(self.name+'-daemon.log'),'a')
        p=subprocess.Popen([PY,str(P/'bin/aos7-daemon'),str(self.root)],stdout=log,stderr=log,start_new_session=True)
        self.procs.append(p);return p
    def pause(self,n):
        self.ctl('pause',n,'--owner','qa')
        wait(lambda:(((read_json(str(self.root/'.aosd/status.json')) or {}).get('nodes') or {}).get(n) or {}).get('phase')=='paused')
        time.sleep(.06)
    def resume(self,n):self.ctl('resume',n,'--owner','qa')
    def collect(self,n,timeout=30):
        rows=[];seen=self.reg().get('my_round',0);end=time.monotonic()+timeout
        while len(rows)<n and time.monotonic()<end:
            z=self.reg()
            if z.get('my_round',0)>seen:seen=z['my_round'];rows.append(z);self.snap.append(z)
            time.sleep(.002)
        if len(rows)<n:raise RuntimeError('collect timeout '+self.name)
        return rows
    def finish(self):
        for p in self.procs:
            if p.poll() is None:p.terminate()
        for p in self.procs:
            try:p.wait(timeout=12)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        killed=[]
        for _ in range(4):
            ps=own_pids(self.root)
            for pid in ps:
                try:os.kill(pid,signal.SIGKILL);killed.append(pid)
                except ProcessLookupError:pass
            time.sleep(.05)
        write_json(str(E/(self.name+'-registers.json')),self.snap)
        with tarfile.open(E/(self.name+'-snapshot.tar.gz'),'w:gz') as t:t.add(self.root,arcname=self.name)
        rem=own_pids(self.root)
        shutil.rmtree(self.root)
        write_json(str(E/(self.name+'-cleanup.json')),{'root':str(self.root),'killed_by_pid':killed,'remaining':rem,'removed':not self.root.exists()})
        if rem:raise RuntimeError('remaining own pids '+str(rem))
def matrix():
    s=Space('matrix',step=True)
    try:
        initial=s.boot();check('initial',initial['state']=='ok',register=initial)
        # Real chmod denial, malformed source and directory fault; isolate same exact patience positions.
        for kind in ('half','permission','directory','missing_key','missing_round','not_number'):
            s.source(10);good=s.cycle();p=s.src/'out/temp.json'
            if kind=='half':p.write_text('{"v":1,"rou')
            elif kind=='permission':p.chmod(0)
            elif kind=='directory':p.unlink();p.mkdir()
            else:
                d=read_json(str(p))
                if kind=='missing_key':d['value']={}
                if kind=='missing_round':d.pop('round')
                if kind=='not_number':d['value']['x']=True
                write_json(str(p),d)
            denied=False
            if kind=='permission':
                try:p.read_bytes()
                except PermissionError:denied=True
            rows=[s.cycle() for _ in range(3)]
            check('fault_'+kind,[(z['state'],z['held']) for z in rows]==[('ok',1),('ok',2),('unknown',0)] and rows[-1]['last']['basis']==good['basis'],rows=rows,real_eacces=denied)
            if p.is_dir():p.rmdir()
            else:p.chmod(0o600)
            s.source(11);z=s.cycle();check('recovery_'+kind,z['state']=='ok',register=z)
        # Explicit absence bypasses patience.
        (s.src/'out/temp.json').unlink();z=s.cycle();check('absent',z['state']=='absent' and z['last'] is not None,register=z)
        s.source(12);s.cycle()
        write_json(str(s.dst/'adapt/temp.json'),dict(s.decl,patience=9));z=s.cycle();check('chain_change_M',z['why']=='chain_changed' and z['state']=='unknown',register=z)
        write_json(str(s.dst/'adapt/temp.json'),s.decl);check('chain_restore',s.cycle()['state']=='ok')
        # New source versions skip exactly 4; task PID only SIGKILL, real keep relaunch.
        s.source(17);before=s.cycle();fr=s.frame();pid=wait(lambda:read_json(str(s.slot()/'pid.json')))
        os.kill(pid['pid'],signal.SIGKILL);wait(lambda:read_json(str(s.slot()/'exit.json')))
        after=s.cycle();newpid=read_json(str(s.slot()/'pid.json'))
        check('adapt_sigkill_restart',newpid['run']>pid['run'] and s.frame()['since']==fr['since'] and after['skipped']==before['skipped'] and after['basis']==before['basis'],before=before,after=after,old_pid=pid,new_pid=newpid)
        # Genuine source rebuild: no source tasks/daemon in this manual root; preserve stale publication.
        for _ in range(15):s.cycle('src')
        s.source(18);old=s.cycle();shutil.rmtree(s.src/'.aos');write_json(str(s.src/'.aos/tasks.json'),{'tasks':[]});s.cycle('src')
        z=s.cycle();check('source_rebuild',z['src_state']=='reset' and z['why']=='void_basis' and z['last']['void'],before=old,after=z)
        s.source(1);z=s.cycle();check('source_new_basis',z['state']=='ok' and z['basis']['src_round']==1,register=z)
        # Gates with exact integer values and binary exact q=.5; independent truth table.
    finally:s.finish()
    for op in ('ge','gt','le','lt'):
        d={'steps':[{'select':'value.x'},{'scale':{'mul':1,'q':.5,'as':'c'}},{'threshold':{op:80,'as':'hot'}}]}
        s=Space('boundary-'+op,decl=d)
        try:
            s.boot();rows=[]
            for i,x in enumerate((79,79.5,80,80.5,81)):
                s.source(i+2,x);z=s.cycle();lo=x-.5;hi=x+.5
                cmp={'ge':lambda a:a>=80,'gt':lambda a:a>80,'le':lambda a:a<=80,'lt':lambda a:a<80}[op]
                expected=cmp(lo) if cmp(lo)==cmp(hi) else None
                actual=z['trace'][-1]['v'];rows.append({'x':x,'interval':[lo,hi],'expected':expected,'actual':actual,'state':z['state']})
            check('threshold_'+op,all(r['expected'] is r['actual'] and r['state']==('unknown' if r['expected'] is None else 'ok') for r in rows),rows=rows)
        finally:s.finish()
    s=Space('blueprint-step',step=True)
    try:
        s.cycle('src');s.source(1,790);s.cycle();s.cycle()
        rows=[]
        for i,x in enumerate((790,799,800)):
            s.source(i+2,x);z=s.cycle();s.cycle();rows.append(z)
        fr=read_json(str(s.dst/'jobs/gate/frame.json'))
        check('step_num_unknown_wait',fr['phase']=='running' and fr['pc']=='w',frame=fr,registers=rows)
        s.source(9,801)
        for _ in range(5):s.cycle()
        fr=read_json(str(s.dst/'jobs/gate/frame.json'))
        check('step_num_then',fr['phase']=='ended' and fr['end']=='ok',frame=fr)
        check('blueprint_formula',[z['trace'][-1]['v'] for z in rows]==[False,False,None],registers=rows)
    finally:s.finish()
    # Boundary ages and stalls, full unmodified task through core lifecycle.
    for name,decl in [('max_age',{'max_age':2}),('stall',{'stall':3})]:
        s=Space(name,decl=decl)
        try:
            s.boot();rows=[]
            for _ in range(4):
                if name=='max_age':s.cycle('src')
                rows.append(s.cycle())
            expected=['ok','ok','unknown','unknown'] if name=='max_age' else ['ok','ok','ok','unknown']
            check(name+'_boundary',[z['state'] for z in rows]==expected,rows=rows)
        finally:s.finish()
    s=Space('long320')
    try:
        s.boot()
        def files():return {str(p.relative_to(s.root)):sorted(str(q.relative_to(p)) for q in p.rglob('*') if q.is_file()) for p in (s.dst/'in',s.dst/'adapt',s.slot(),s.src/'out')}
        before=files();r0=read_json(str(s.dst/'.aos/round.json'));start=time.monotonic()
        for n in range(320):
            s.cycle('src');s.source(n+2);s.cycle()
        after=files();r1=read_json(str(s.dst/'.aos/round.json'))
        check('long320_closed',not r0['open'] and not r1['open'] and r1['round']-r0['round']==320 and before==after and all(r['state']=='ok' for r in s.snap),first_closed=r0,last_closed=r1,seconds=time.monotonic()-start,before_files=before,after_files=after,samples=len(s.snap))
    finally:s.finish()
def flows():
    for src_ms,dst_ms,n in [(20,200,12),(200,20,45),(50,50,20),(10,2000,6),(2000,10,100)]:
        s=Space('flow-%d-%d'%(src_ms,dst_ms),sensor=True,src_ms=src_ms,dst_ms=dst_ms)
        try:
            p=s.daemon();wait(lambda:s.reg().get('state')=='ok',30);rows=s.collect(n,60)
            seq=[r['basis']['seq'] for r in rows];same=sum(a==b for a,b in zip(seq,seq[1:]));skip=rows[-1]['skipped']-rows[0]['skipped']
            good=all(r['state']=='ok' and r['value']['c']==80.1 and r['err']['c']==.05 for r in rows)
            good=good and (skip>0 if src_ms<dst_ms else (same>0 if src_ms>dst_ms else True))
            check('flow_%d_%d'%(src_ms,dst_ms),good,seq=seq,skipped_delta=skip,repeated_pairs=same,max_age=max(r['age_src_rounds'] for r in rows),my_rounds=[r['my_round'] for r in rows])
            if src_ms==20 and dst_ms==200:
                s.pause('src');rs=s.collect(7);stable=rs[2:]
                check('source_pause',all(r['state']=='ok' and r['src_state']=='stalled' for r in stable) and len({r['age_src_rounds'] for r in stable})==1,rows=rs)
                s.resume('src');rs=s.collect(4);check('source_resume',any(r['src_state']=='advancing' and r['state']=='ok' for r in rs),rows=rs)
                s.pause('dst');b=s.reg();fr=s.frame();mt=(s.dst/'in/temp.json').stat().st_mtime_ns;time.sleep(.7)
                check('dst_pause',b==s.reg() and fr==s.frame() and mt==(s.dst/'in/temp.json').stat().st_mtime_ns,before=b,after=s.reg())
                s.resume('dst');s.collect(3)
                # Kill only daemon PID. Child task identity remains; restart keeps clocks.
                before=s.reg();os.kill(p.pid,signal.SIGKILL);p.wait();time.sleep(.3);s.daemon(register=False)
                rs=s.collect(8,30);check('daemon_restart',all(r['src_state']!='reset' for r in rs) and rs[-1]['basis']['src_round']>before['basis']['src_round'],before=before,rows=rs)
        finally:s.finish()
if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else 'matrix';start=time.monotonic()
    try:globals()[mode]()
    except Exception as e:
        check('HARNESS_EXCEPTION',False,error=repr(e),traceback=traceback.format_exc());raise
    finally:
        write_json(str(E/(mode+'-results.json')),{'seconds':time.monotonic()-start,'results':RESULT})
        (E/(mode+'-ps.txt')).write_text(subprocess.run(['ps','-eo','pid,ppid,stat,args'],capture_output=True,text=True).stdout)
