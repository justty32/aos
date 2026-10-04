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

# Previous once-probes.py worker/helpers/boundary cases preserved above. The following
# assertions now observe fixed behavior instead of waiting for the old duplicate bug.
def corrupt_once_test():
    item={'name':'o','mode':'once','argv':['sh','-c','echo "$AOS7_RUN" >> "$AOS7_NODE/ran"']}
    with fixture('once-birth-corrupt',[item]) as (root,n):
        p=subprocess.run([sys.executable,str(Path(__file__).resolve()),'worker',str(root),'before-delete'],capture_output=True,text=True,timeout=8)
        wait(lambda:load(slot(n)/'exit.json'))
        wait(lambda:not proc.env_procs(str(n),'o',1,runners=True))
        before={'launch':load(n/'.aos/tasks.json'),'exit':load(slot(n)/'exit.json'),'executions':(n/'ran').read_text().splitlines()}
        (slot(n)/'birth.json').write_text('{')
        s=tock.tock(str(root),'n');t=tick.tick(str(root),'n');time.sleep(.1);after=tock.tock(str(root),'n')
        return {'tick_crash_rc':p.returncode,'before':before,'corrupt_tock':s,'recovery_tick':t,'executions':(n/'ran').read_text().splitlines(),'final_tasks':load(n/'.aos/tasks.json'),'final_summary':after}

def three_state_tests():
    out={};item={'name':'o','mode':'keep','argv':['sleep','60']}
    for case in ['proc_starttime_none','proc_stat_eio','proc_all_eio','birth_bad_proc_environ_eio']:
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
            with contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch('builtins.open',failopen));stack.enter_context(mock.patch.object(os,'listdir',faillist))
                if case=='proc_starttime_none':stack.enter_context(mock.patch.object(proc,'proc_starttime',lambda p:None))
                v=task.judge(str(slot(n)),str(n),'o',3);result=tick.tick(str(root),'n');summary=tock.tock(str(root),'n')
            out[case]={'view':v,'tick':result,'summary':summary,'old_pid':pd['pid'],'old_alive':alive(pd['pid']),'pid_unchanged':load(slot(n)/'pid.json')==pd}
    return out

def round_tests():
    out={}
    for case in ['round_eio','round_bad','round_open_missing','direct_tick_open']:
        with fixture(case,[]) as (root,n):
            tick.tick(str(root),'n');tock.tock(str(root),'n');tick.tick(str(root),'n')
            rp=n/'.aos/round.json'
            if case=='round_bad':rp.write_text('{')
            if case=='round_open_missing':
                s=load(rp);s.pop('open');dump(rp,s)
            before=rp.read_bytes();origopen=os.open
            def fail(path,*a,**kw):
                if case=='round_eio' and str(path).endswith('/round.json') and a and not a[0]&os.O_WRONLY and not a[0]&os.O_CREAT:
                    raise OSError(errno.EIO,'injected round EIO')
                return origopen(path,*a,**kw)
            vals={}
            with mock.patch.object(os,'open',fail):
                for label,fn in [('tick',tick.tick),('tock',tock.tock)]:
                    try:vals[label]=fn(str(root),'n')
                    except Exception as e:vals[label]={'exception':type(e).__name__,'message':str(e)}
            vals['round_bytes_unchanged']=rp.read_bytes()==before;vals['last_round']=load(n/'.aos/last-round.json');out[case]=vals
    return out

def restart_tests():
    out={};item={'name':'o','mode':'once','argv':['sh','-c','echo "$AOS7_RUN" >> "$AOS7_NODE/ran"']}
    with fixture('restart-after-append',[item]) as (root,n):
        tick.tick(str(root),'n');wait(lambda:load(slot(n)/'exit.json'));fs.write_json(str(slot(n)/'ctl.json'),{'op':'restart','by':'probe'})
        code='''import sys,os,signal
sys.path.insert(0,sys.argv[1]);import aos7_task,aos7_tock
orig=aos7_task.edit_json
def cut(*a,**kw):
 r=orig(*a,**kw);os.kill(os.getpid(),signal.SIGKILL)
aos7_task.edit_json=cut
aos7_tock.tock(sys.argv[2],'n')
'''
        p=subprocess.run([sys.executable,'-B','-c',code,str(TOP/'lib'),str(root)],capture_output=True,timeout=10)
        queued=load(n/'.aos/tasks.json');tock.tock(str(root),'n');recovered=load(n/'.aos/tasks.json')
        starts=[]
        for i in range(3):
            starts.append(tick.tick(str(root),'n')['started']);time.sleep(.1);tock.tock(str(root),'n')
        out['original_append_sigkill']={'rc':p.returncode,'queued_after_cut':queued,'queued_after_recovery':recovered,'started':starts,'executions':(n/'ran').read_text().splitlines()}
    for case in ['new_mtime','same_mtime','long_ids']:
        with fixture('restart-'+case,[item]) as (root,n):
            tick.tick(str(root),'n');wait(lambda:load(slot(n)/'exit.json'));tock.tock(str(root),'n')
            ctl=slot(n)/'ctl.json';record={'op':'restart','by':'probe'}; ids=[];inodes=[];receipts=[]
            for i in range(2):
                if case=='long_ids':record['id']='x'*64+str(i)
                fs.write_json(str(ctl),record)
                if case=='same_mtime':os.utime(ctl,ns=(1000000000,1000000000))
                ids.append(task.ctl_id_of(str(ctl),record));inodes.append(ctl.stat().st_ino)
                t=tick.tick(str(root),'n');time.sleep(.1);receipts.append(load(slot(n)/'ctl-done.json'));tock.tock(str(root),'n')
            out[case]={'ctl_ids':ids,'inodes':inodes,'executions':(n/'ran').read_text().splitlines(),'receipts':receipts}
    # Real unlink failure at low-level syscall; a keep task exits independently after restart.
    with fixture('restart-replay-after-birth-reuse',[dict(item,mode='keep',argv=['sh','-c','echo "$AOS7_RUN" >> "$AOS7_NODE/ran"; if [ "$AOS7_RUN" -ge 3 ]; then sleep 60; fi'])]) as (root,n):
        tick.tick(str(root),'n');wait(lambda:load(slot(n)/'exit.json'));tock.tock(str(root),'n')
        fs.write_json(str(slot(n)/'ctl.json'),{'op':'restart','id':'one-request'})
        origremove=os.remove;origwrite=task.write_json;unlink_errors=[]
        def permissions_after_done(path,obj):
            origwrite(path,obj)
            if str(path).endswith('/ctl-done.json'):os.chmod(Path(path).parent,0o555)
        def failremove(path,*a,**kw):
            try:
                return origremove(path,*a,**kw)
            except OSError as e:
                if str(path).endswith('/ctl.json'):unlink_errors.append({'errno':e.errno,'mode':oct(Path(path).parent.stat().st_mode & 0o777)})
                raise
            finally:
                if str(path).endswith('/ctl.json'):os.chmod(Path(path).parent,0o755)
        rows=[]
        with mock.patch.object(os,'remove',failremove),mock.patch.object(task,'write_json',permissions_after_done):
            for i in range(4):
                t=tick.tick(str(root),'n');time.sleep(.12);s=tock.tock(str(root),'n')
                rows.append({'tick':t,'birth':load(slot(n)/'birth.json'),'receipt':load(slot(n)/'ctl-done.json'),'tasks':load(n/'.aos/tasks.json'),'summary_ctl':s.get('ctl')})
        out['ctl_unlink_denied_birth_reused']={'real_unlink_errors':unlink_errors,'rows':rows,'executions':(n/'ran').read_text().splitlines(),'ctl_still_present':(slot(n)/'ctl.json').exists()}
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

def cross_slot_ids():
    out={}
    for case in ['explicit_same_id','same_raw_mtime']:
        items=[{'name':name,'mode':'once','argv':['sh','-c','echo "$AOS7_RUN" >> "$AOS7_NODE/ran-$AOS7_TID"']} for name in ['o','p']]
        with fixture('cross-slot-'+case,items) as (root,n):
            tick.tick(str(root),'n')
            for name in ['o','p']:wait(lambda:load(slot(n,name)/'exit.json'))
            tock.tock(str(root),'n');record={'op':'restart','by':'probe'}
            if case=='explicit_same_id':record['id']='both-slots'
            for name in ['o','p']:
                path=slot(n,name)/'ctl.json';fs.write_json(str(path),record)
                if case=='same_raw_mtime':os.utime(path,ns=(1000000000,1000000000))
            t=tick.tick(str(root),'n');time.sleep(.1)
            out[case]={'tick':t,'receipts':{name:load(slot(n,name)/'ctl-done.json') for name in ['o','p']},'executions':{name:(n/('ran-'+name)).read_text().splitlines() for name in ['o','p']}}
            tock.tock(str(root),'n')
    return out

try:
    results={'once_boundaries':boundary_tests(),'once_corrupt_birth':corrupt_once_test(),'three_state':three_state_tests(),'rounds':round_tests(),'restart':restart_tests(),'identity':identity_tests(),'cross_slot_ids':cross_slot_ids()}
    dump(HERE/'once-regression.json',results)
finally:
    for child in list(ROOT.iterdir()):
        if child.is_dir():cleanup(child)
    ROOT.rmdir()
    dump(HERE/'once-cleanup.json',{'cases':CLEAN,'remaining_test_pids':pids_for(ROOT),'temp_root_exists':ROOT.exists()})
print(json.dumps({'result':'once-regression.json','cases_cleaned':len(CLEAN),'remaining':pids_for(ROOT)},ensure_ascii=False))
