#!/usr/bin/env python3
"""Runtime-only fault injection; writes fixtures solely under evidence and removes them.
Run: PYTHONDONTWRITEBYTECODE=1 python3 <this-file>
"""
import builtins, contextlib, ctypes, errno, json, os, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path
from unittest import mock
HERE=Path(__file__).resolve().parent
TOP=HERE.parents[2]
sys.path.insert(0,str(TOP/'lib'))
import aos7_fs as fs, aos7_tick as tick, aos7_tock as tock, aos7_task as task, aos7_proc as proc
import aos7_daemon_timeline as timeline
os.environ['PYTHONDONTWRITEBYTECODE']='1'

def dump(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def killself(): os.kill(os.getpid(),signal.SIGKILL)

def worker(root,point):
    tw=tick.write_json; bw=task.write_json; ed=tick.edit_json
    def tickwrite(path,obj):
        launch=str(path).endswith('/tasks.json') and any(isinstance(t,dict) and t.get('launch') for t in obj.get('tasks',[]))
        if launch and point=='before-launch': killself()
        tw(path,obj)
        if launch and point=='after-launch': killself()
    def birthwrite(path,obj):
        if str(path).endswith('/birth.json'):
            p='runner' if obj.get('runner') else 'birth'
            if point=='before-'+p: killself()
            bw(path,obj)
            if point=='after-'+p: killself()
        else: bw(path,obj)
    def edit(path,fn,*a,**kw):
        if point=='before-delete': killself()
        result=ed(path,fn,*a,**kw)
        if point=='after-delete': killself()
        return result
    tick.write_json=tickwrite; task.write_json=birthwrite; tick.edit_json=edit
    if point=='runner-before-pid':
        popen=subprocess.Popen
        def launch(args,*a,**kw):
            if len(args)>1 and str(args[1]).endswith('aos7-run'):
                args=[sys.executable,str(Path(__file__).resolve()),'runner-worker',*args[2:]]
            return popen(args,*a,**kw)
        task.subprocess.Popen=launch
    print(json.dumps(tick.tick(root,'n')))

if len(sys.argv)>1 and sys.argv[1]=='worker':
    worker(sys.argv[2],sys.argv[3]); sys.exit()
if len(sys.argv)>1 and sys.argv[1]=='runner-worker':
    import aos7_run
    real=aos7_run.write_at
    def write_at(fd,name,obj):
        if name=='pid.json': killself()
        return real(fd,name,obj)
    aos7_run.write_at=write_at
    sys.exit(aos7_run.main(sys.argv[2:]))

# Adopt orphaned test runners so cleanup can reap by PID, without touching unrelated processes.
ctypes.CDLL(None).prctl(36,1,0,0,0)
ROOT=Path(tempfile.mkdtemp(prefix='once-work-',dir=HERE)).resolve()
CLEAN=[]
def pids_for(root):
    result=[]; want=('AOS7_ROOT='+str(root)).encode()
    for p in Path('/proc').iterdir():
        if p.name.isdigit() and int(p.name)!=os.getpid():
            try:
                env=(p/'environ').read_bytes().split(b'\0')
                if any(e==want or e.startswith(want+b'/') for e in env):result.append(int(p.name))
            except OSError: pass
    return result

def alive(pid):
    try:
        return Path('/proc/%d/stat'%pid).read_text().rsplit(')',1)[1].split()[0]!='Z'
    except OSError:return False

def cleanup(root):
    found=pids_for(root)
    for pid in found:
        try: os.kill(pid,signal.SIGKILL)
        except ProcessLookupError:pass
    end=time.monotonic()+3
    while time.monotonic()<end:
        try:
            while os.waitpid(-1,os.WNOHANG)[0]:pass
        except ChildProcessError:pass
        if not any(alive(p) for p in found):break
        time.sleep(.02)
    CLEAN.append({'root':str(root.relative_to(HERE)),'killed_pids':found,'surviving_pids':[p for p in found if alive(p)]})
    shutil.rmtree(root)

@contextlib.contextmanager
def fixture(name,items):
    root=ROOT/name; node=root/'n'; (node/'.aos').mkdir(parents=True)
    fs.write_json(str(node/'.aos/tasks.json'),{'tasks':items})
    try:yield root,node
    finally:cleanup(root)

def wait(pred):
    end=time.monotonic()+5
    while time.monotonic()<end:
        v=pred()
        if v:return v
        time.sleep(.01)
    raise TimeoutError('predicate timed out')
def load(p):return fs.read_json(str(p))
def slot(n,s='o'):return n/'.aos/tasks'/s

def boundary_tests():
    out=[]
    for point in ['before-launch','after-launch','before-birth','after-birth','before-runner','after-runner','before-delete','after-delete']:
        item={'name':'o','mode':'once','argv':['sh','-c','echo "$AOS7_RUN" >> "$AOS7_NODE/ran"']}
        with fixture(point,[item]) as (root,n):
            p=subprocess.run([sys.executable,str(Path(__file__).resolve()),'worker',str(root),point],capture_output=True,text=True,timeout=8)
            assert p.returncode==-9,(point,p.returncode,p.stderr)
            time.sleep(.08)
            at_crash={'tasks':load(n/'.aos/tasks.json'),'birth':load(slot(n)/'birth.json'),'round':load(n/'.aos/round.json')}
            summaries=[]
            with mock.patch.dict(os.environ,{'AOS7_INCOMPLETE':'tick'}): summaries.append(tock.tock(str(root),'n'))
            for _ in range(4):
                tick.tick(str(root),'n');time.sleep(.08);summaries.append(tock.tock(str(root),'n'))
            ran=(n/'ran').read_text().splitlines() if (n/'ran').exists() else []
            out.append({'point':point,'tick_rc':p.returncode,'crash_birth':at_crash['birth'],'crash_tasks':at_crash['tasks'],'executions':ran,'ended':[e for s in summaries for e in s['ended']],'final_tasks':load(n/'.aos/tasks.json'),'rounds':[s['round'] for s in summaries]})
    return out

def corrupt_once_test():
    item={'name':'o','mode':'once','argv':['sh','-c','echo "$AOS7_RUN" >> "$AOS7_NODE/ran"']}
    with fixture('once-birth-corrupt',[item]) as (root,n):
        p=subprocess.run([sys.executable,str(Path(__file__).resolve()),'worker',str(root),'before-delete'],capture_output=True,text=True,timeout=8)
        wait(lambda:load(slot(n)/'exit.json'))
        wait(lambda:not proc.env_procs(str(n),'o',1,runners=True))
        before={'launch':load(n/'.aos/tasks.json'),'birth':load(slot(n)/'birth.json'),'exit':load(slot(n)/'exit.json'),'executions':(n/'ran').read_text().splitlines()}
        (slot(n)/'birth.json').write_text('{')
        s=tock.tock(str(root),'n');t=tick.tick(str(root),'n')
        wait(lambda:len((n/'ran').read_text().splitlines())==2)
        wait(lambda:(load(slot(n)/'exit.json') or {}).get('run')==2)
        after=tock.tock(str(root),'n')
        return {'tick_crash_rc':p.returncode,'before':before,'corrupt_tock':s,'recovery_tick':t,'executions':(n/'ran').read_text().splitlines(),'final_summary':after}

def three_state_tests():
    out={};item={'name':'o','mode':'keep','argv':['sleep','60']}
    with fixture('three-state',[item]) as (root,n):
        tick.tick(str(root),'n');pd=wait(lambda:load(slot(n)/'pid.json'));tock.tock(str(root),'n')
        with mock.patch.object(proc,'proc_starttime',lambda p:None):
            v=task.judge(str(slot(n)),str(n),'o',2)
            t=tick.tick(str(root),'n');s=tock.tock(str(root),'n')
        out['starttime_none']={'view':v,'tick':t,'summary':s,'old_alive':alive(pd['pid']),'recovered_view':task.judge(str(slot(n)),str(n),'o',2)}
        orig=fs.os.open
        for target in ['birth.json','round.json','last-round.json']:
            def fail(path,*a,**kw):
                if str(path).endswith('/'+target) and a and a[0]&os.O_WRONLY==0 and not a[0]&os.O_CREAT:
                    raise OSError(errno.EIO,'injected read EIO',str(path))
                return orig(path,*a,**kw)
            before={f:load(n/'.aos'/f) for f in ['round.json','last-round.json']}
            with mock.patch.object(fs.os,'open',fail):
                vals={}
                for name,fn in [('tick',tick.tick),('tock',tock.tock)]:
                    try: vals[name]=fn(str(root),'n')
                    except Exception as e: vals[name]={'exception':type(e).__name__,'message':str(e)}
            vals.update(old_alive=alive(pd['pid']),birth_run=load(slot(n)/'birth.json')['run'])
            out[target+'_eio']=vals
            tock.tock(str(root),'n')
        bp=slot(n)/'birth.json';saved=bp.read_text()
        for content in ['{','[]']:
            bp.write_text(content)
            v=task.judge(str(slot(n)),str(n),'o',10);t=tick.tick(str(root),'n');s=tock.tock(str(root),'n')
            out['birth_bad_'+content]={'view':v,'tick':t,'summary':s,'old_alive':alive(pd['pid'])}
        bp.write_text(saved)
        out['birth_restored']=task.judge(str(slot(n)),str(n),'o',10)
        (n/'.aos/last-round.json').write_text('{')
        t=tick.tick(str(root),'n');s=tock.tock(str(root),'n');out['last_round_bad_only']={'tick':t,'summary':s}
        (n/'.aos/round.json').write_text('{');(n/'.aos/last-round.json').write_text('{')
        try:tick.tick(str(root),'n')
        except Exception as e:out['both_rounds_bad']={'exception':type(e).__name__,'message':str(e)}
    # Accurate low-level proc fault, leaving real task and runner alive.
    for case in ['proc_stat_eio','proc_all_eio','birth_bad_proc_environ_eio']:
        with fixture(case,[item]) as (root,n):
            tick.tick(str(root),'n');pd=wait(lambda:load(slot(n)/'pid.json'));tock.tock(str(root),'n')
            if case.startswith('birth_bad'): (slot(n)/'birth.json').write_text('{')
            origopen=builtins.open;origlist=os.listdir
            def failopen(path,*a,**kw):
                p=str(path)
                if p.startswith('/proc/') and not p.startswith('/proc/self/') and ((case in ('proc_stat_eio','proc_all_eio') and p.endswith('/stat')) or (case.startswith('birth_bad') and p.endswith('/environ'))):
                    raise OSError(errno.EIO,'injected /proc EIO',p)
                return origopen(path,*a,**kw)
            def faillist(path):
                if str(path)=='/proc' and case=='proc_all_eio':raise OSError(errno.EIO,'injected /proc directory EIO')
                return origlist(path)
            with mock.patch('builtins.open',failopen),mock.patch.object(os,'listdir',faillist):
                v=task.judge(str(slot(n)),str(n),'o',3)
                result=tick.tick(str(root),'n')
            new=wait(lambda: (x if (x:=load(slot(n)/'pid.json')) and x['run']!=pd['run'] else None))
            out[case]={'initial_view':v,'tick':result,'old_pid':pd['pid'],'new_pid':new['pid'],'both_alive':alive(pd['pid']) and alive(new['pid']),'reaped':load(n/'.aos/round.json').get('reaped'),'recovered_tick':None}
            tock.tock(str(root),'n');out[case]['recovered_tick']=tick.tick(str(root),'n');out[case]['old_still_alive_after_recovery']=alive(pd['pid']);tock.tock(str(root),'n')
    return out

def identity_tests():
    out={};item={'name':'o','mode':'keep','argv':['sleep','60']}
    with fixture('runner-dead-before-pid',[item]) as (root,n):
        p=subprocess.run([sys.executable,str(Path(__file__).resolve()),'worker',str(root),'runner-before-pid'],capture_output=True,text=True,timeout=8)
        runner=load(slot(n)/'birth.json')['runner']['pid']
        old=wait(lambda:[pid for pid in proc.env_procs(str(n),'o',1) if pid!=runner])
        wait(lambda:not alive(runner))
        out['runner_before_pid']={'tick_rc':p.returncode,'old_pids':old,'birth':load(slot(n)/'birth.json'),'pid_json':load(slot(n)/'pid.json'),'old_alive_before_tock':[p for p in old if alive(p)]}
        s=tock.tock(str(root),'n');t=tick.tick(str(root),'n');new=wait(lambda:load(slot(n)/'pid.json'))
        out['runner_before_pid'].update(summary=s,next_tick=t,old_alive=[p for p in old if alive(p)],new_pid=new['pid'])
    with fixture('old-run-residue',[item]) as (root,n):
        tick.tick(str(root),'n');pd=wait(lambda:load(slot(n)/'pid.json'));tock.tock(str(root),'n')
        b=load(slot(n)/'birth.json'); b['run']=100;b['runner']=None;b['round']=1;fs.write_json(str(slot(n)/'birth.json'),b)
        fs.write_json(str(slot(n)/'exit.json'),{'run':1,'code':0})
        out['old_run_residue']={'view':task.judge(str(slot(n)),str(n),'o',4),'old_identity_matches_new':proc.env_procs(str(n),'o',100),'old_identity_matches_old':proc.env_procs(str(n),'o',1)}
    return out

def timeline_tests():
    out={}
    # Real Timeline loop with injected tock failure / read EIO, actual tick/tock funcs and real filesystem.
    class D:
        gen=1;stopping=False;stopping_since=None;kill_on_stop=False
        def __init__(self,root):self.root=str(root);self.paused=False;self.completed=0;self.events=[]
        def is_paused(self,n):
            if self.paused:self.stopping=True
            return self.paused
        def round_done(self,n):self.completed+=1;self.paused=True
        def log(self,**kw):self.events.append(kw)
        def kill_live(self,*a):pass
    for case in ['round_eio','round_bad','round_open_missing','recovery_pause_count']:
        with fixture(case,[]) as (root,n):
            fs.write_json(str(n/'.aos/timeline.json'),{'interval_ms':0})
            tick.tick(str(root),'n');tock.tock(str(root),'n');tick.tick(str(root),'n')
            d=D(root);tl=timeline.Timeline(d,'n',None);calls=[];roundpath=n/'.aos/round.json';saved=roundpath.read_text()
            if case=='round_bad':roundpath.write_text('{')
            if case=='round_open_missing':
                state=json.loads(saved);state.pop('open');dump(roundpath,state)
            original=timeline.read_json3
            def read(path):
                if case=='round_eio' and str(path).endswith('/round.json') and not calls:
                    return fs.IO,'injected EIO'
                return original(path)
            def prog(name,extra=None,timeout=None):
                calls.append(name)
                if case=='recovery_pause_count' and len(calls)==1:return 1,None,'injected ENOSPC'
                with mock.patch.dict(os.environ,extra or {}):
                    result=(tick.tick if name=='aos7-tick' else tock.tock)(str(root),'n')
                if name=='aos7-tock' and case!='recovery_pause_count':d.stopping=True
                return 0,result,''
            tl.prog=prog
            def backoff():
                calls.append('backoff');tl.phase='error'
                if case=='round_eio':d.stopping=True
            tl.backoff=backoff
            if case=='recovery_pause_count':tl.owe_done=True
            with mock.patch.object(timeline,'read_json3',read):tl._loop()
            out[case]={'calls':calls,'round':load(roundpath),'last_round':load(n/'.aos/last-round.json'),'round_open':tl.round_open,'last_error':tl.last_error,'completed':d.completed,'paused':d.paused,'events':d.events}
            if case=='round_eio':
                d.stopping=False;tl._loop()
                out[case]['recovery']={'calls':calls,'round':load(roundpath),'last_round':load(n/'.aos/last-round.json')}
    # Direct API tick lacks open guard; explicitly separate from daemon promise.
    with fixture('direct-tick-open',[]) as (root,n):
        a=tick.tick(str(root),'n');b=tick.tick(str(root),'n');out['direct_tick_open']={'first':a,'second':b,'last_round_exists':(n/'.aos/last-round.json').exists()}
    return out

try:
    results={'once_boundaries':boundary_tests(),'once_corrupt_birth':corrupt_once_test(),'three_state':three_state_tests(),'identity':identity_tests(),'timeline':timeline_tests()}
    dump(HERE/'once-results.json',results)
finally:
    for child in list(ROOT.iterdir()):
        if child.is_dir():cleanup(child)
    ROOT.rmdir()
    dump(HERE/'once-cleanup.json',{'cases':CLEAN,'remaining_test_pids':pids_for(ROOT),'temp_root_exists':ROOT.exists()})
print(json.dumps({'result':'once-results.json','cases_cleaned':len(CLEAN),'remaining':pids_for(ROOT)},ensure_ascii=False))
