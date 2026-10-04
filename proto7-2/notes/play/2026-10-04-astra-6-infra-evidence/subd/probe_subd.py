#!/usr/bin/env python3
"""Independent process-level subd probes. Write only evidence and own /tmp. No LLM."""
import ctypes, json, os, shutil, signal, subprocess, sys, tempfile, time, traceback
from pathlib import Path
OUT=Path(__file__).resolve().parent
REPO=OUT.parents[4]; TOP=REPO/'proto7-2'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
assert ctypes.CDLL(None).prctl(36,1,0,0,0)==0
TMP=Path(tempfile.mkdtemp(prefix='astra6-subd-edge-'))
RESULT={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'tmp':str(TMP),'cases':[]}
HOOK=TMP/'hooks.py'
HOOK.write_text('''import os,signal,json\nfrom pathlib import Path\ncounts={}\ndef inject(op,path): pass\ndef test_point(name):\n counts[name]=counts.get(name,0)+1\n if name==os.environ.get('QA_CRASH_POINT') and counts[name]==int(os.environ.get('QA_CRASH_N','1')):\n  Path(os.environ['QA_HIT']).write_text(json.dumps({'pid':os.getpid(),'point':name,'count':counts[name]}))\n  os.kill(os.getpid(),signal.SIGKILL)\n''')
def read(p):
 try:return json.loads(Path(p).read_text())
 except (OSError,ValueError):return {}
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name('.'+p.name+'.qa');q.write_text(json.dumps(x));q.replace(p)
def live(pid):
 try:return Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split()[0]!='Z'
 except OSError:return False
def wait(f,seconds=15):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  v=f()
  if v:return v
  time.sleep(.01)
 raise TimeoutError('condition timeout')
def belonging(root):
 out=[];b=str(root).encode()
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid():continue
  try:
   env=(p/'environ').read_bytes().split(b'\0');args=(p/'cmdline').read_bytes()
   if any(e.startswith(b'AOS7_ROOT='+b) for e in env) or b in args:out.append(int(p.name))
  except OSError:pass
 return out
class Case:
 def __init__(self,name):
  self.name=name;self.root=TMP/name;self.root.mkdir();self.known=set();self.procs=[];self.logs=[]
  write(self.root/'.aosd/nodes.json',{'nodes':{'a':{}}})
 def space(self,sub='a/sub'):
  n=self.root/sub/'n1';write(n/'.aos/timeline.json',{'interval_ms':100})
  worker=self.root/'worker.py';worker.write_text("import os,signal,time,json,pathlib\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\np=pathlib.Path(os.environ['AOS7_TASK'])/'ready.json'\np.write_text(json.dumps({'pid':os.getpid(),'run':int(os.environ['AOS7_RUN'])}))\nwhile True:time.sleep(.02)\n")
  write(n/'.aos/tasks.json',{'tasks':[{'name':'w','mode':'keep','argv':[sys.executable,str(worker)]}]});return self.root/sub
 def env(self):return dict(os.environ,AOS7_ROOT=str(self.root),AOS7_NODE=str(self.root/'a'),AOS7_NODE_ID='a',AOS7_TID='sub',AOS7_RUN='1',PATH=str(TOP/'bin')+':'+os.environ['PATH'])
 def start(self,sub='a/sub',allow=False,point=None,n=1,cmd=None):
  e=self.env()
  if point:e.update(AOS7_TEST_HOOKS=str(HOOK),QA_CRASH_POINT=point,QA_CRASH_N=str(n),QA_HIT=str(self.root/'hit.json'))
  boot=['sh','-c','aos7-ctl daemon "$AOS7_SUBROOT" register n1 --by qa >/dev/null && exec aos7-daemon "$AOS7_SUBROOT"']
  log=(self.root/f'wrapper-{len(self.procs)}.log').open('w');self.logs.append(log)
  p=subprocess.Popen([sys.executable,str(TOP/'modules/subd/aos7-subd'),sub]+(['--allow-stop'] if allow else [])+['--']+(cmd or boot),env=e,stdout=log,stderr=log,start_new_session=True)
  self.procs.append(p);self.known.add(p.pid);return p
 def ready(self,sub,exclude=()):
  return wait(lambda:(lambda j:j.get('pid') if j.get('pid') not in exclude and live(j.get('pid',0)) else None)(read(sub/'n1/.aos/tasks/w/ready.json')))
 def daemon(self,sub,exclude=()):return wait(lambda:(lambda p:p if p not in exclude and live(p or 0) else None)(read(sub/'.aosd/status.json').get('pid')))
 def ctl(self,sub,op):
  p=subprocess.run([sys.executable,str(TOP/'bin/aos7-ctl'),'daemon',str(sub),op,'--by','astra6'],capture_output=True,text=True,timeout=10);assert p.returncode==0,p.stderr
  req=Path(json.loads(p.stdout)['wrote']);return wait(lambda:read(sub/'.aosd/ctl-done'/req.name))
 def sleep(self,env=None,cwd=None):
  p=subprocess.Popen([sys.executable,'-c','import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(120)'],env=env or self.env(),cwd=cwd,start_new_session=True);self.procs.append(p);self.known.add(p.pid);return p
 def cleanup(self):
  before=belonging(self.root);self.known.update(before)
  for _ in range(5):
   ids=set(belonging(self.root))|self.known
   for pid in ids:
    if live(pid):
     try:os.kill(pid,signal.SIGKILL)
     except ProcessLookupError:pass
   for p in self.procs:
    try:p.wait(.2)
    except subprocess.TimeoutExpired:pass
   for pid in ids:
    try:os.waitpid(pid,os.WNOHANG)
    except ChildProcessError:pass
   time.sleep(.05)
  after=belonging(self.root);ps=subprocess.run(['ps','-o','pid,ppid,pgid,stat,args','-p',','.join(map(str,sorted(self.known)))],capture_output=True,text=True).stdout
  logs={p.name:p.read_text() for p in self.root.glob('wrapper-*.log')}
  for f in self.logs:f.close()
  result={'before':before,'after':after,'known_live':[p for p in self.known if live(p)],'ps':ps,'logs':logs}
  if not after and not result['known_live']:shutil.rmtree(self.root)
  result['tmp_removed']=not self.root.exists();return result

def run(name,fn):
 c=Case(name);r={'name':name};start=time.monotonic()
 try:r.update(fn(c));r.setdefault('pass',True)
 except Exception:r.update(pass_=False,error=traceback.format_exc())
 finally:r['cleanup']=c.cleanup();r['elapsed_s']=round(time.monotonic()-start,3);RESULT['cases'].append(r);(OUT/'edges.json').write_text(json.dumps(RESULT,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='cleanup'},ensure_ascii=False),flush=True)

def boundaries(c):
 sub=c.space();prefix=c.space('a/sub2');sibling=c.space('a/other');nested=c.space('a/sub/n1/nested')
 env=c.env();ids={}
 for name,node in [('old',sub/'n1'),('prefix',prefix/'n1'),('sibling',sibling/'n1'),('nested',nested/'n1')]:
  ids[name]=c.sleep(dict(env,AOS7_NODE=str(node),AOS7_TID=name)).pid
 plain=dict(os.environ);ids['manual_no_identity']=c.sleep(plain,cwd=sub).pid
 ids['manual_inherited_identity']=c.sleep(dict(env,AOS7_NODE=str(sub/'n1'),AOS7_TID='manual'),cwd=sub).pid
 p=c.start(cmd=[sys.executable,'-c','pass']);assert p.wait(15)==0
 states={name:live(pid) for name,pid in ids.items()};expected={'old':False,'prefix':True,'sibling':True,'nested':False,'manual_no_identity':True,'manual_inherited_identity':False}
 return {'pids':ids,'alive':states,'expected':expected,'pass':states==expected,'classification':'normal；按 AOS7 身分回收，非 aos 執行檔本身不構成 M；純 cwd 位在子根的程序無誤殺'}

def initial_crash(c,point,n=1):
 sub=c.space();old=c.sleep(dict(c.env(),AOS7_NODE=str(sub/'n1'),AOS7_TID='old')).pid
 p=c.start(point=point,n=n);rc=p.wait(15);hit=read(c.root/'hit.json');life=read(sub/'.aosd/subd-life.json');old_after=live(old)
 assert rc==-9 and hit['pid']==p.pid,(rc,hit)
 q=c.start();d=c.daemon(sub);new=c.ready(sub)
 return {'point':point,'nth':n,'crash_rc':rc,'hit':hit,'life_at_crash':life,'old_alive_at_crash':old_after,'old_alive_after_restart':live(old),'new_daemon':d,'new_task':new,'pass':not live(old),'classification':'X；恢復符合保證'}

def active_wrapper_crash(c,point=None):
 sub=c.space();p=c.start(point=point);d=c.daemon(sub);task=c.ready(sub)
 if point:assert p.wait(10)==-9
 else:os.kill(p.pid,signal.SIGKILL);p.wait(5)
 q=c.start();rc=q.wait(5)
 return {'point':point or 'active wrapper SIGKILL','rc_restart':rc,'daemon_alive':live(d),'task_alive':live(task),'life':read(sub/'.aosd/subd-life.json'),'pass':rc==1 and live(d) and live(task),'classification':'X；daemon.lock 持有期間拒絕重開，契約已明列'}

def daemon_crash(c):
 sub=c.space();p=c.start();d=c.daemon(sub);old=c.ready(sub);os.kill(d,signal.SIGKILL);rc=p.wait(10);life=read(sub/'.aosd/subd-life.json');q=c.start();nd=c.daemon(sub,exclude=(d,));new=c.ready(sub,exclude=(old,))
 return {'old_daemon':d,'old_task':old,'wrapper_rc':rc,'life_after_daemon_crash':life,'new_daemon':nd,'new_task':new,'old_alive_after_restart':live(old),'pass':rc==137 and not live(old),'classification':'X；子 daemon 自崩後回收符合保證'}

def stopped(c,point=None,n=1):
 sub=c.space();p=c.start(allow=True,point=point,n=n);d=c.daemon(sub);old=c.ready(sub);receipt=c.ctl(sub,'stop');rc=p.wait(15)
 before={'old_alive':live(old),'life':read(sub/'.aosd/subd-life.json'),'stopped_exists':(sub/'.aosd/stopped.json').exists(),'hit':read(c.root/'hit.json'),'wrapper_rc':rc,'receipt':receipt}
 if (sub/'.aosd/stopped.json').exists():
  blocked=c.start(allow=True);before['blocked_rc']=blocked.wait(5);(sub/'.aosd/stopped.json').unlink()
 q=c.start(allow=True);nd=c.daemon(sub,exclude=(d,));time.sleep(.3)
 return {'point':point,'nth':n,'before':before,'new_daemon':nd,'old_task':old,'old_alive_after_restart':live(old),'pass':live(old),'classification':'B 候選：已允許 stop 的持久化中断後重開收掉應接回任務' if not live(old) else 'normal'}

if __name__=='__main__':
 run('boundaries',boundaries)
 for name,point,n in [('crash-recovering-tmp','tmp:subd-life.json',1),('crash-reaping','subd-reaping',1),('crash-reaped','subd-reaped',1),('crash-running-tmp','tmp:subd-life.json',2),('crash-before-argv','subd-before-argv',1),('crash-guard-tmp','tmp:stop-guard.json',1)]:run(name,lambda c,p=point,n=n:initial_crash(c,p,n))
 run('crash-owner-tmp',lambda c:active_wrapper_crash(c,'tmp:owner.json'))
 run('crash-active-wrapper',active_wrapper_crash)
 run('daemon-self-crash',daemon_crash)
 run('allow-stop-normal',stopped)
 run('allow-stop-crash-stopped-tmp',lambda c:stopped(c,'tmp:stopped.json'))
 run('allow-stop-crash-life-tmp',lambda c:stopped(c,'tmp:subd-life.json',3))
 RESULT['final_proc_remaining']=belonging(TMP)
 if not RESULT['final_proc_remaining']:
  HOOK.unlink();TMP.rmdir()
 RESULT['tmp_removed']=not TMP.exists();(OUT/'edges.json').write_text(json.dumps(RESULT,ensure_ascii=False,indent=2)+'\n')
