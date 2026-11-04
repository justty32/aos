#!/usr/bin/env python3
"""Offline, root-scoped probes; no kernel/agent. All /tmp roots removed and descendants reaped."""
import ctypes,json,os,pathlib,shutil,signal,subprocess,sys,tempfile,time
P=pathlib.Path
HERE=P(__file__).resolve().parent
REPO=HERE.parents[4]
BIN=REPO/'proto7-1/bin'
ctypes.CDLL(None).prctl(36,1,0,0,0)  # make probe driver subreaper for clean experiments

def write(p,v):
 p.parent.mkdir(parents=True,exist_ok=True); q=p.with_name(p.name+'.tmp');q.write_text(json.dumps(v));q.replace(p)
def read(p):
 try:return json.loads(p.read_text())
 except (ValueError,OSError):return None
def wait(fn,timeout=10):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  val=fn()
  if val:return val
  time.sleep(.025)
 raise RuntimeError('timeout')
def procs(root):
 out=[]
 for pd in P('/proc').iterdir():
  if not pd.name.isdigit():continue
  try:
   cmd=(pd/'cmdline').read_bytes();env=(pd/'environ').read_bytes();stat=(pd/'stat').read_text().rsplit(')',1)[1].split()
   if stat[0]!='Z' and str(root).encode() in cmd+env:
    out.append({'pid':int(pd.name),'ppid':int(stat[1]),'pgid':int(stat[2]),'state':stat[0],'cmd':cmd.replace(b'\0',b' ').decode(errors='replace')[:400]})
  except (OSError,IndexError):pass
 return out

def clean(root,ps):
 for p in procs(root):
  try:os.kill(p['pid'],signal.SIGKILL)
  except ProcessLookupError:pass
 for p in ps:
  try:p.wait(timeout=2)
  except subprocess.TimeoutExpired:pass
 end=time.monotonic()+3
 while time.monotonic()<end:
  try:
   pid,_=os.waitpid(-1,os.WNOHANG)
   if pid:continue
  except ChildProcessError:break
  time.sleep(.03)
 leftovers=procs(root)
 if leftovers:raise RuntimeError(('leftovers',leftovers))
 shutil.rmtree(root)
 return {'active_processes':0,'root_removed':not root.exists()}
def node(root,n,tasks):
 n=root/n;write(n/'.aos/timeline.json',{'interval_ms':150});write(n/'.aos/tasks.json',{'tasks':tasks});return n
def task(name,argv,mounts=None):return dict(name=name,argv=argv,mode='keep',mounts=mounts or {})
def launch(root,ps):
 p=subprocess.Popen([sys.executable,str(BIN/'aos7-daemon'),str(root)],stdout=subprocess.DEVNULL,stderr=open(root/'daemon.stderr','w'),start_new_session=True);ps.append(p);return p

def nested(kind):
 root=P(tempfile.mkdtemp(prefix='astra4-nested-'+kind+'-'));ps=[];res={'case':kind,'root':str(root)}
 try:
  r1=root/'n/child';r2=r1/'n/grand';r1.mkdir(parents=True);r2.mkdir(parents=True)
  (r1/'.aosd').mkdir();(r2/'.aosd').mkdir()
  node(root,'n',[task('child',[str(BIN/'aos7-daemon'),'$AOS7_TASK/mnt/sub'],{'sub':'n/child'})])
  node(r1,'n',[task('grand',[str(BIN/'aos7-daemon'),'$AOS7_TASK/mnt/sub'],{'sub':'n/grand'})])
  stubborn=kind=='term-stubborn'
  leafcode='import signal,time; '+('signal.signal(signal.SIGTERM,signal.SIG_IGN); ' if stubborn else '')+'time.sleep(90)'
  node(r2,'n',[task('leaf'+str(i),[sys.executable,'-c',leafcode]) for i in range(4 if stubborn else 1)])
  d=launch(root,ps)
  wait(lambda: len(list((r2/'n/.aos/tasks').glob('*/pid.json')))==(4 if stubborn else 1))
  time.sleep(.35)
  roots=[root,r1,r2]; res['before']={'status':[read(r/'.aosd/status.json') for r in roots],'processes':procs(root)}
  start=time.monotonic();d.send_signal(signal.SIGKILL if kind=='kill' else signal.SIGTERM);d.wait(timeout=10)
  res['parent_exit_seconds']=time.monotonic()-start
  time.sleep(1.4)
  res['after']={'status':[read(r/'.aosd/status.json') for r in roots],'processes':procs(root),'tasks':{str(p.parent.relative_to(root)):{'pid':read(p),'exit':read(p.parent/'exit.json'),'ended':read(p.parent/'ended.json')} for p in root.rglob('pid.json')}}
 finally:res['cleanup']=clean(root,ps)
 return res

PEER_CODE='''import os,pathlib,json,time
p=pathlib.Path(os.environ['AOS7_TASK']); n=pathlib.Path(os.environ['AOS7_NODE'])
while not (n/'go').exists():time.sleep(.02)
peer=p/'mnt/peer'
try:
 q=peer/'ctl'/('from-'+os.environ['AOS7_NODE_ID'].replace('/','_')+'.json');q.parent.mkdir(exist_ok=True)
 q.write_text(json.dumps(dict(op='pause',node='n',by=os.environ['AOS7_TID'])))
 (p/'sent.json').write_text(json.dumps({'path':str(q),'ok':True}))
except OSError as e:(p/'sent.json').write_text(json.dumps({'ok':False,'error':str(e)}))
time.sleep(90)
'''
def cycle(reexport):
 root=P(tempfile.mkdtemp(prefix='astra4-nested-cycle-'));ps=[];res={'case':'cycle-reexport' if reexport else 'cycle-native','root':str(root)}
 try:
  child=root/'child';child.mkdir();(child/'.aosd').mkdir()
  if reexport:
   (child/'.parent-aosd').mkdir();(root/'.aosd').symlink_to('child/.parent-aosd',target_is_directory=True)
  else:(child/'parent-link').symlink_to(root/'.aosd',target_is_directory=True)
  node(root,'n',[task('writer',[sys.executable,'-c',PEER_CODE],{'peer':'child/.aosd'})])
  node(child,'n',[task('writer',[sys.executable,'-c',PEER_CODE],{'peer':'.parent-aosd' if reexport else 'parent-link','direct-parent':'../.aosd'} if not reexport else {'peer':'.parent-aosd'})])
  launch(root,ps);launch(child,ps)
  wait(lambda:len(list(root.rglob('pid.json')))>=2)
  for r in (root,child):(r/'n/go').write_text('go')
  wait(lambda:len(list(root.rglob('sent.json')))>=2)
  time.sleep(.5)
  res['status']=[read(r/'.aosd/status.json') for r in (root,child)]
  res['births']={str(p.relative_to(root)):read(p) for p in root.rglob('birth.json')}
  res['sent']={str(p.relative_to(root)):read(p) for p in root.rglob('sent.json')}
  res['receipts']={str(p.relative_to(root)):read(p) for p in root.rglob('ctl-done/*.json')}
  res['paused_files']=[read(r/'.aosd/paused.json') for r in (root,child)]
  res['rounds_before']=[read(r/'n/.aos/round.json') for r in (root,child)];time.sleep(.4)
  res['rounds_after']=[read(r/'n/.aos/round.json') for r in (root,child)]
  # daemon control itself still runs while all timelines paused; externally resume both
  for r in (root,child):write(r/'.aosd/ctl/external-resume.json',dict(op='resume',node='n',by='probe-driver'))
  wait(lambda:all(read(r/'.aosd/ctl-done/external-resume.json') for r in (root,child)))
  time.sleep(.3);res['after_resume']=[read(r/'.aosd/status.json') for r in (root,child)]
 finally:res['cleanup']=clean(root,ps)
 return res

if __name__=='__main__':
 out=[]
 for c in ['term','term-stubborn','kill']:
  v=nested(c);out.append(v);print(c,v['parent_exit_seconds'],len(v['after']['processes']),flush=True)
 for b in [False,True]:
  v=cycle(b);out.append(v);print(v['case'],v['paused_files'],flush=True)
 (HERE/'results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
