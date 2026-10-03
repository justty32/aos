from common import *
from boundaries import hook,ctl,status,disk_cost
from unittest import mock
import aos7_tick as tick, aos7_tock as tock, aos7_kernel_rules as rules

def cap(s):
    n=s.node();write(n/'.aos/timeline.json',{'keep_old_rounds':0});write(n/'.aos/round.json',{'round':3,'open':True});td=n/'.aos/tasks-old/a-r1'
    for file,v in [('birth',{'tid':'a-r1','name':'a','round':1}),('ended',{'round':1}),('exit',{'code':0}),('usage',{'tokens':1000,'calls':2})]:write(td/(file+'.json'),v)
    cfg={'cap_tokens':500};before=rules.snapshot_node(str(n/'.aos'));snap={'round':1,'node_id':'controller','members':{'n':before},'self_tasks':[]};dec1,state=rules.run_rules(cfg,{},snap)
    summary=tock.tock(str(s.root),'n');after=rules.snapshot_node(str(n/'.aos'));snap['round']=2;snap['members']['n']=after;dec2,state2=rules.run_rules(cfg,state,snap)
    return {'cfg_unchanged':cfg,'before':before,'decision_before':dec1,'purge':summary.get('purged'),'after':after,'decision_after':dec2,'note':'real snapshot+tock+rules, no LLM, synthetic usage.json; pending/current tock or manual tock allows purge despite cap pause'}

def crash_tick(s):
    n=s.node(items=[{'name':'x','mode':'keep','argv':SLEEP}]);code='''import os,sys,signal
sys.path.insert(0,os.environ['HOOK_LIB'])
if os.path.basename(sys.argv[0])=='aos7-tick':
 import aos7_task as t
 real=t.subprocess.Popen
 def spawn(args,*a,**kw):
  p=real(args,*a,**kw)
  if len(args)>1 and str(args[1]).endswith('/aos7-run'):
   open(os.environ['MARK'],'w').write(str(p.pid));os.kill(os.getpid(),signal.SIGSTOP)
  return p
 t.subprocess.Popen=spawn
if os.path.basename(sys.argv[0])=='aos7-run':os.kill(os.getpid(),signal.SIGSTOP)
'''
    p=s.start('aos7-tick','n',env=hook(s,code));wait((s.root/'mark').exists);rp=int((s.root/'mark').read_text());os.kill(rp,signal.SIGKILL);p.kill();p.wait();wait(lambda:not task.pid_alive(rp));td=n/'.aos/tasks/x-r1'
    tr=s.run('aos7-tock');r2=s.run('aos7-tick');return {'killed_tick':p.pid,'killed_runner':rp,'runner_json':read(td/'runner.json'),'pid_json':read(td/'pid.json'),'state':task.task_state(str(td)),'tock':tr,'next_tick':r2}

def duplicate(s):
    body="import os,time;open('pid-'+os.environ['AOS7_TID'],'w').write(str(os.getpid()));time.sleep(60)"
    n=s.node(items=[{'name':'x','mode':'keep','argv':[sys.executable,'-c',body]}]);code='''import os,sys,signal
if os.path.basename(sys.argv[0])=='aos7-run':
 sys.path.insert(0,os.environ['HOOK_LIB']);import aos7_run as r
 real=r.write_at
 def write(fd,name,obj):
  if name=='pid.json':open(os.environ['MARK'],'w').write(str(os.getpid()));os.kill(os.getpid(),signal.SIGSTOP)
  return real(fd,name,obj)
 r.write_at=write
'''
    s.run('aos7-tick',env=hook(s,code));wait((n/'pid-x-r1').exists);wait((s.root/'mark').exists);rp=int((s.root/'mark').read_text());original=int((n/'pid-x-r1').read_text());os.kill(rp,signal.SIGKILL);wait(lambda:not task.pid_alive(rp));tr=s.run('aos7-tock');r2=s.run('aos7-tick');wait((n/'pid-x-r2').exists);new=int((n/'pid-x-r2').read_text())
    both={'old_pid':original,'new_pid':new,'old_alive':task.pid_alive(original),'new_alive':task.pid_alive(new)}
    # Real daemon stop sweep must still reclaim both cooperative tasks.
    write(s.root/'.aosd/paused.json',{'paused':['n']});d=s.start();wait(lambda:status(s).get('pid'));stop=ctl(s.root,'stop',kill=True);d.wait(10)
    return {'tock':tr,'next_tick':r2,'simultaneous':both,'stop':stop,'after_stop':{'old_alive':task.pid_alive(original),'new_alive':task.pid_alive(new)}}

def late_runner_move(s):
    n=s.node(items=[{'name':'x','mode':'keep','argv':[sys.executable,'-c',"import os;from pathlib import Path;p=Path(os.environ['AOS7_TASK']);p.mkdir(parents=True,exist_ok=True);(p/'marker').write_text(os.getcwd())"]}]);code='''import os,sys,signal
if os.path.basename(sys.argv[0])=='aos7-run':
 sys.path.insert(0,os.environ['HOOK_LIB']);import aos7_run as r
 real=r.subprocess.Popen
 def spawn(*a,**kw):
  open(os.environ['MARK'],'w').write(str(os.getpid()));os.kill(os.getpid(),signal.SIGSTOP)
  return real(*a,**kw)
 r.subprocess.Popen=spawn
'''
    s.run('aos7-tick',env=hook(s,code));wait((s.root/'mark').exists);rp=int((s.root/'mark').read_text());m=s.root/'moved';n.rename(m);os.kill(rp,signal.SIGCONT);ex=wait(lambda:read(m/'.aos/tasks/x-r1/exit.json'))
    return {'barrier':'runner Popen immediately after env_mismatch and out.log open','exit':ex,'old_node_recreated':n.exists(),'ghost_marker':(n/'.aos/tasks/x-r1/marker').read_text() if (n/'.aos/tasks/x-r1/marker').exists() else None,'moved_pid':read(m/'.aos/tasks/x-r1/pid.json')}

DISKHOOK='''import os,sys,time
if os.path.basename(sys.argv[0])=='aos7-daemon':
 sys.path.insert(0,os.environ['HOOK_LIB']);import aos7_daemon as d
 real=d.Daemon.disk_usage
 def slow(self):
  if os.path.exists(os.environ['MARK']):return real(self)
  original=d.os.lstat
  def delay(path,*a,**kw):
   if '/ctl-done/' in str(path):time.sleep(.01)
   return original(path,*a,**kw)
  open(os.environ['MARK'],'w').write('disk scan started')
  d.os.lstat=delay
  try:return real(self)
  finally:d.os.lstat=original
 d.Daemon.disk_usage=slow
'''
def disk_control(s):
    for i in range(200):write(s.root/'.aosd/ctl-done'/(str(i)+'.json'),{'i':i})
    d=s.start(env=hook(s,DISKHOOK));wait((s.root/'mark').exists);t=time.monotonic();r=ctl(s.root,'stop',kill=True);d.wait(10)
    return {'fault':'lstat on own ctl-done files delayed 10ms x 200; no external filesystem modified','stop':r,'total_stop_s':time.monotonic()-t,'rc':d.returncode,'final':status(s)}

if __name__=='__main__':
    for name,fn in [('disk-cost',disk_cost),('retention-cap',cap),('runner-tick-crash',crash_tick),('runner-duplicate',duplicate),('H05-runner-late-move',late_runner_move),('disk-control-delay',disk_control)]:case(name,fn)
