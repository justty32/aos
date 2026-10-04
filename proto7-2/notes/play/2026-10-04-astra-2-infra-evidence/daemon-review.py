#!/usr/bin/env python3
"""A2-04/06/11/13 原探針現版適配；真 EACCES 與人工恢復組合。
只在同 evidence/daemon-work 建資料，所有新增程序以 PID 清除。
PYTHONDONTWRITEBYTECODE=1 python3 -B <this script>
"""
import ctypes, errno, json, os, pathlib, shutil, signal, subprocess, sys, tempfile, time, traceback
E=pathlib.Path(__file__).resolve().parent; TOP=E.parents[2]
sys.dont_write_bytecode=True;os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.path[:0]=[str(TOP/'tests'),str(TOP/'lib')]
from base import DaemonCase,SLEEP
from aos7_fs import read_json,write_json
import aos7_proc
W=E/'daemon-work';W.mkdir(exist_ok=True);tempfile.tempdir=str(W)
rows={}; recorded_pids=set()
def test(name,fn):
 c=DaemonCase();c.setUp()
 try:rows[name]=fn(c)
 except Exception:rows[name]={'error':traceback.format_exc()}
 finally:c.doCleanups()
def symlink(c,outside=False):
 node=c.mknode(tasks=[{'name':'s','mode':'keep','argv':SLEEP}],interval_ms=200)
 c.start_daemon(register=['a']);pid=c.wait_pid(node,'s')['pid'];c.wait_round(2);before=c.node_round()
 os.rename(node,c.root+'/moved')
 target=c.root+'/target' if outside else 'moved'
 if outside:target=str(W/'outside-target');os.mkdir(target)
 os.symlink(target,node)
 c.wait_for(lambda:c.nstat().get('phase')=='missing');time.sleep(.8)
 result={'phase':c.nstat().get('phase'),'before_round':before,'after_round':c.node_round(),'task_alive':aos7_proc.pid_alive(pid),'outside_aos':os.path.exists(target+'/.aos') if outside else None}
 if outside:shutil.rmtree(target)
 return result
def owners(c):
 c.mknode(interval_ms=120)
 a=c.ctl('pause','a','--owner','A');b=c.ctl('pause','a','--owner','B')
 c.start_daemon(register=['a']);c.wait_receipt(a);c.wait_receipt(b);c.wait_for(lambda:c.nstat().get('phase')=='paused')
 initial=c.nstat();c.wait_receipt(c.ctl('resume','a','--owner','A','--rounds','1'));c.wait_receipt(c.ctl('resume','a','--owner','B','--rounds','3'))
 c.wait_for(lambda:c.nstat().get('phase')=='paused' and 'A' in c.nstat().get('paused_by',[]));first=c.nstat()
 c.wait_receipt(c.ctl('resume','a','--owner','A'));c.wait_for(lambda:c.nstat().get('phase')=='paused' and c.nstat().get('paused_by')==['B'])
 return {'different_request_paths':a!=b,'initial':initial,'after_one':first,'after_three':c.nstat()}
def wake(c):
 c.mknode(tasks=[{'name':'s','argv':['sleep','0.7']}],interval_ms=2500,early=True);c.start_daemon(register=['a'])
 c.wait_for(lambda:c.nstat().get('phase')=='running');t=time.monotonic();receipt=c.wait_receipt(c.ctl('wake','a'));c.wait_round(2,timeout=5)
 return {'interval_ms':2500,'wake_to_next_tick_s':round(time.monotonic()-t,3),'receipt':receipt['result']}
def manual_round(c):
 n=c.mknode(interval_ms=100);c.tick();raw=pathlib.Path(n+'/.aos/round.json').read_bytes();again=c.prog('aos7-tick',c.root,'a',rc=3)
 untouched=raw==pathlib.Path(n+'/.aos/round.json').read_bytes();p=c.start_daemon(register=['a']);c.wait_round(2)
 c.wait_receipt(c.ctl('pause','a'));c.wait_for(lambda:c.nstat().get('phase')=='paused');saved=c.round_json(n)
 pathlib.Path(n+'/.aos/round.json').write_text('{');c.wait_for(lambda:(c.nstat().get('last_error') or {}).get('kind')=='round-unknown');st=c.nstat()
 write_json(n+'/.aos/round.json',saved);c.wait_receipt(c.ctl('resume','a'));c.wait_round(saved['round']+1,timeout=12)
 return {'second_tick_rc':3,'original_open_unchanged':untouched,'daemon_recovered_open':True,'corrupt_status':st,'repaired_round':c.node_round(),'repaired_status':c.nstat()}
def manual_birth(c):
 n=c.mknode(tasks=[{'name':'k','mode':'keep','argv':['true']}],interval_ms=150)
 sp=c.slot(n,'k');os.makedirs(sp);pathlib.Path(sp+'/birth.json').write_text('{');c.start_daemon(register=['a']);c.wait_round(2)
 c.wait_for(lambda:bool(c.nstat().get('uncertain')));st=c.nstat();pathlib.Path(sp+'/birth.json').unlink();c.wait_for(lambda:bool(c.birth(n,'k').get('run')))
 return {'unknown_status':st,'after_delete_birth':c.birth(n,'k')}
def nondumpable(c):
 code="import ctypes,os,time;assert ctypes.CDLL(None).prctl(4,0,0,0,0)==0;open(os.environ['AOS7_NODE']+'/ready','w').write(str(os.getpid()));time.sleep(60)"
 n=c.mknode(tasks=[{'name':'k','mode':'keep','argv':[sys.executable,'-c',code]}]);c.tick();pid=c.wait_pid(n,'k')['pid'];recorded_pids.add(pid)
 def kill_child():
  try:os.kill(pid,signal.SIGKILL)
  except ProcessLookupError:pass
 c.addCleanup(kill_child)
 c.wait_for(lambda:os.path.exists(n+'/ready'));runner=c.birth(n,'k')['runner']['pid']
 try:pathlib.Path('/proc/%d/environ'%pid).read_bytes();err=None
 except OSError as ex:err=ex.errno
 os.kill(runner,signal.SIGKILL);c.wait_for(lambda:not aos7_proc.pid_alive(runner))
 found=aos7_proc.env_procs(n,'k',1);write_json(c.slot(n,'k')+'/ctl.json',{'op':'kill','by':'real-eacces'})
 lr=c.tock();receipt=read_json(c.slot(n,'k')+'/ctl-done.json');alive=aos7_proc.pid_alive(pid)
 c.start_daemon(register=['a']);c.wait_for(lambda:'k#1' in c.nstat().get('live',[]));st=c.nstat()
 return {'uid':os.geteuid(),'environ_errno':err,'expected_eacces':errno.EACCES,'target_pid':pid,'runner_pid':runner,'env_scan':found,'ctl_receipt':receipt,'target_alive_after_kill':alive,'tock_alive':lr['alive'],'status':st}
def nondumpable_before_pid(c):
 code="import ctypes,os,time;assert ctypes.CDLL(None).prctl(4,0,0,0,0)==0;open(os.environ['AOS7_NODE']+'/pid-'+os.environ['AOS7_RUN'],'w').write(str(os.getpid()));time.sleep(60)"
 n=c.mknode(tasks=[{'name':'k','mode':'keep','argv':[sys.executable,'-c',code]}])
 def cleanup_hidden():
  for f in pathlib.Path(n).glob('pid-*'):
   pid=int(f.read_text());recorded_pids.add(pid)
   try:os.kill(pid,signal.SIGKILL)
   except ProcessLookupError:pass
 c.addCleanup(cleanup_hidden)
 c.tick(env={'AOS7_TEST_RUNNER_CRASH':'runner-before-pid'});c.wait_for(lambda:os.path.exists(n+'/pid-1'));pid1=int(pathlib.Path(n+'/pid-1').read_text());recorded_pids.add(pid1)
 runner=c.birth(n,'k')['runner']['pid'];c.wait_for(lambda:not aos7_proc.pid_alive(runner))
 try:pathlib.Path('/proc/%d/environ'%pid1).read_bytes();err=None
 except OSError as ex:err=ex.errno
 missing_pid=not os.path.exists(c.slot(n,'k')+'/pid.json');lr=c.tock();nxt=c.tick();c.wait_for(lambda:os.path.exists(n+'/pid-2'));pid2=int(pathlib.Path(n+'/pid-2').read_text());recorded_pids.add(pid2)
 return {'environ_errno':err,'runner_dead':True,'pid_json_absent':missing_pid,'tock_ended':lr['ended'],'next_started':nxt['started'],'two_live_pids':[p for p in [pid1,pid2] if aos7_proc.pid_alive(p)]}
for name,fn in [('A2-04-same-inode',symlink),('A2-04-outside',lambda c:symlink(c,True)),('A2-06-and-A2-13',owners),('A2-11',wake),('manual-round',manual_round),('manual-birth',manual_birth),('real-environ-eacces',nondumpable),('real-environ-eacces-before-pid',nondumpable_before_pid)]:test(name,fn)
remaining=[p for p in recorded_pids if aos7_proc.pid_alive(p)]
rows['_cleanup']={'remaining_recorded_pids':remaining,'work_entries':[str(p.relative_to(W)) for p in W.rglob('*')]}
shutil.rmtree(W);rows['_cleanup']['work_removed']=not W.exists()
(E/'daemon-review.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(rows,ensure_ascii=False,indent=2))
