from common import *
from unittest import mock
import errno
import aos7_daemon as daemon, aos7_tick as tick, aos7_tock as tock, aos7_mount as mount

def root_case(s,kind):
    base=s.root;root=base/'real';root.mkdir();n=root/'n'
    write(n/'.aos/tasks.json',{'tasks':[{'name':'s','mode':'keep','argv':SLEEP}]});write(n/'.aos/timeline.json',{'interval_ms':150})
    alias=base/'alias';alias.symlink_to(root,target_is_directory=True)
    arg=alias if kind=='initial-symlink' else root
    p=s.start(args=[sys.executable,str(BIN/'aos7-daemon'),str(arg)])
    pid=wait(lambda:read(n/'.aos/tasks/s-r1/pid.json'))['pid'];before=read(n/'.aos/round.json')['round'];ob={}
    if kind=='chmod':
        root.chmod(0)
        try:time.sleep(.4);ob={'alive_during':p.poll() is None,'task_alive_during':task.pid_alive(pid)}
        finally:root.chmod(0o700)
    elif kind=='rename-return':
        os.kill(p.pid,signal.SIGSTOP);root.rename(base/'moved');(base/'moved').rename(root);os.kill(p.pid,signal.SIGCONT)
    elif kind in ('symlink-same','symlink-other'):
        os.kill(p.pid,signal.SIGSTOP);root.rename(base/'moved');n=base/'moved/n'
        target=base/'moved'
        if kind=='symlink-other':target=base/'other';target.mkdir();write(target/'sentinel.json',{'keep':True})
        root.symlink_to(target,target_is_directory=True);os.kill(p.pid,signal.SIGCONT)
    time.sleep(.6)
    state=read(n.parent/'.aosd/status.json',{});r=read(n/'.aos/round.json',{})
    return {'kind':kind,**ob,'before_round':before,'after_round':r.get('round'),'daemon_alive':p.poll() is None,'task_alive':task.pid_alive(pid),'status':state,'events':[x for x in rows(n.parent/'.aosd/log.jsonl') if x.get('ev') in ('root-gone','scan-error','scan-ok','io-error')][-5:],'other_files':[str(q.relative_to(base/'other')) for q in (base/'other').rglob('*')] if (base/'other').exists() else []}

def bind(s):
    # Mount only in a private user+mount namespace. No host mount mutation.
    src=s.root/'src';dst=s.root/'dst';src.mkdir();dst.mkdir()
    code="""import os,sys,subprocess,json
sys.path.insert(0,sys.argv[1]);import aos7_daemon
src,dst=sys.argv[2:4]
p=subprocess.run(['mount','--bind',src,dst],capture_output=True,text=True)
r={'mount_rc':p.returncode,'mount_error':p.stderr}
if p.returncode==0:
 try:
  d=aos7_daemon.Daemon(dst);d.check_root();r['same_inode_root_ok']=not d.root_gone;os.close(d.rfd)
 finally:r['umount_rc']=subprocess.run(['umount',dst]).returncode
print(json.dumps(r))
"""
    p=subprocess.run(['unshare','--user','--map-root-user','--mount',sys.executable,'-c',code,str(LIB),str(src),str(dst)],capture_output=True,text=True,timeout=8)
    return {'rc':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'actual_bind_test':p.returncode==0}

def runner(s):
    results=[]
    for kind in ('legacy','valid','invalid','nonnumeric','file','elsewhere'):
        a=s.root/kind/'a';b=s.root/kind/'b';a.mkdir(parents=True);b.mkdir()
        for d in (a,b):write(d/'birth.json',{'tid':d.name,'argv':[sys.executable,'-c',f'print({d.name!r})']})
        fd=None;args=[sys.executable,str(BIN/'aos7-run'),str(a)]
        if kind in ('valid','elsewhere','file'):
            fd=os.open(str(b if kind=='elsewhere' else a/'birth.json' if kind=='file' else a),os.O_RDONLY);args.append(str(fd))
        if kind=='invalid':args.append('999999')
        if kind=='nonnumeric':args.append('bad')
        p=subprocess.run(args,cwd=s.root,pass_fds=() if fd is None else (fd,),capture_output=True,text=True,timeout=5)
        if fd is not None:os.close(fd)
        results.append({'kind':kind,'rc':p.returncode,'stderr':p.stderr,'a_state':task.task_state(str(a)),'a_exit':read(a/'exit.json'),'b_exit':read(b/'exit.json'),'b_output':(b/'out.log').read_text() if (b/'out.log').exists() else None})
    return {'cases':results}

def ctl(s):
    d=daemon.Daemon(str(s.root));done=s.root/'.aosd/ctl-done/x.json';done.mkdir(parents=True)
    try:
        for i in range(100):write(s.root/'.aosd/ctl/x.json',{'op':'wake','node':'n','sequence':i});d.handle_ctl()
        failed=s.root/'.aosd/ctl-failed';initial=list(failed.iterdir());seq=[read(q).get('sequence') for q in initial]
        write(failed/'x.json.42',{'sentinel':'earlier failure'})
        with mock.patch.object(daemon.time,'time_ns',return_value=42):
            write(s.root/'.aosd/ctl/x.json',{'op':'wake','node':'n','sequence':100});d.handle_ctl()
        write(s.root/'.aosd/ctl/stop.json',{'op':'stop','kill':True});d.handle_ctl()
        return {'normal_failures':len(initial),'unique_sequences':len(set(seq)),'suffix_collision_after':read(failed/'x.json.42'),'stop':read(s.root/'.aosd/ctl-done/stop.json'),'failed_count_after':len(list(failed.iterdir())),'last_error':d.last_ctl_error,'injection':'fixed time_ns=42 with preexisting x.json.42'}
    finally:os.close(d.rfd)

RACE_HOOK='''import os,sys,signal
if os.path.basename(sys.argv[0])=='aos7-tick' and sys.argv[-1]=='n/inner':
 sys.path.insert(0,os.environ['EDGE_LIB'])
 import aos7_task
 real=aos7_task.subroot_running
 def checked(sp):
  r=real(sp)
  open(os.environ['EDGE_MARK'],'w').write(str(r))
  os.kill(os.getpid(),signal.SIGSTOP)
  return r
 aos7_task.subroot_running=checked
'''
def claim_race(s):
    sub='n/inner/sub';n=s.node(items=[{'name':'first','argv':['aos7-daemon','$AOS7_SUBROOT'],'subroot':sub,'allow_stop':False}]);inner=s.node('n/inner',items=[{'name':'second','argv':['aos7-daemon','$AOS7_SUBROOT'],'subroot':sub,'allow_stop':True}])
    hook=s.root/'hook';hook.mkdir();(hook/'sitecustomize.py').write_text(RACE_HOOK);mark=s.root/'mark'
    second=s.start('aos7-tick','n/inner',env={'PYTHONPATH':str(hook),'EDGE_LIB':str(LIB),'EDGE_MARK':str(mark)});wait(mark.exists)
    first=s.run('aos7-tick');st=wait(lambda:read(s.root/sub/'.aosd/status.json'));owner=read(s.root/sub/'.aosd/owner.json')
    os.kill(second.pid,signal.SIGCONT);second.wait(8);ex=wait(lambda:read(inner/'.aos/tasks/second-r1/exit.json'))
    after=read(s.root/sub/'.aosd/owner.json');current=read(s.root/sub/'.aosd/status.json')
    write(s.root/sub/'.aosd/ctl/stop.json',{'op':'stop','kill':True});receipt=wait(lambda:read(s.root/sub/'.aosd/ctl-done/stop.json'))
    return {'barrier_saw_locked':mark.read_text(),'first_tick':first,'before_owner':owner,'after_owner':after,'same_daemon_pid':st['pid']==current['pid'],'loser_exit':ex,'stop_receipt':receipt}

READ_HOOK='''import os,sys,json
if os.path.basename(sys.argv[0])=='aos7-tock':
 sys.path.insert(0,os.environ['EDGE_LIB'])
 import aos7_tock as t
 original=t.logged_summary
 def checked(node,rnd,k=5):
  value=original(node,rnd,k)
  mark=os.environ['EDGE_MARK']
  if value is not None and not os.path.exists(mark):
   open(mark,'w').write(json.dumps({'round':rnd,'summary':value}))
   return None
  return value
 t.logged_summary=checked
'''
def readback(s,daemon_mode):
    n=s.node(items=[{'name':'one','mode':'each','from_round':1,'argv':['true'],'max_live':1}]);write(n/'.aos/tasks.json',{'tasks':[]});write(n/'.aos/spawn/one.json',{'name':'one','argv':['true']})
    hook=s.root/'hook';hook.mkdir();(hook/'sitecustomize.py').write_text(READ_HOOK);mark=s.root/'mark';env={'PYTHONPATH':str(hook),'EDGE_LIB':str(LIB),'EDGE_MARK':str(mark)}
    if daemon_mode:
        d=s.start(env=env);wait(mark.exists);wait(lambda:read(n/'.aos/round.json',{}).get('round',0)>=4);d.terminate();d.wait(10)
        return {'injected':read(mark),'summaries':rows(n/'.aos/rounds.jsonl'),'ended':read(n/'.aos/tasks/one-r1/ended.json'),'tock_errors':[r for r in rows(s.root/'.aosd/log.jsonl') if r.get('ev')=='tock' and r.get('rc')]}
    s.run('aos7-tick');wait(lambda:read(n/'.aos/tasks/one-r1/exit.json'));bad=s.run('aos7-tock',env=env);state=read(n/'.aos/round.json');ended=read(n/'.aos/tasks/one-r1/ended.json');again=s.run('aos7-tock')
    return {'failed_attempt':bad,'open_after_failure':state['open'],'ended_after_failure':ended,'retry':again,'summaries':rows(n/'.aos/rounds.jsonl')}
if __name__=='__main__':
    for kind in ('initial-symlink','chmod','rename-return','symlink-same','symlink-other'):case('root-'+kind,lambda s,k=kind:root_case(s,k))
    for name,fn in [('root-bind',bind),('runner-fd',runner),('ctl-failed',ctl),('claim-race',claim_race),('readback-direct',lambda s:readback(s,False)),('readback-daemon',lambda s:readback(s,True))]:case(name,fn)
