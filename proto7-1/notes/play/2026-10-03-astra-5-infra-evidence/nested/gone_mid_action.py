#!/usr/bin/env python3
"""Freeze direct CLI after node check+action lock, before round/summary write."""
import json,os,pathlib,shutil,signal,subprocess,sys,tempfile,time
P=pathlib.Path;HERE=P(__file__).resolve().parent;REPO=next(p for p in HERE.parents if (p/'proto7-1/lib').is_dir())
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x))
def files(p):return {str(x.relative_to(p)):x.read_text() for x in p.rglob('*') if x.is_file()} if p.exists() else {}
out=[]
for action,change in [('tick','delete'),('tick','rename'),('tock','delete'),('tock','rename')]:
 root=P(tempfile.mkdtemp(prefix='astra5-nested-midaction-'));node=root/'n';p=None;r={'action':action,'change':change,'root':str(root)}
 try:
  write(node/'.aos/timeline.json',{'interval_ms':100});write(node/'.aos/tasks.json',{'tasks':[]});write(node/'.aos/round.json',{'round':1,'open':True,'started':[],'ctl':[],'mounts':[]})
  hook=root/'hook';hook.mkdir();(hook/'sitecustomize.py').write_text('''import sys,os,signal,json
sys.path.insert(0,os.environ['PROBE_LIB'])
import aos7_fs
name='write_json' if os.environ['PROBE_ACTION']=='tick' else 'append_jsonl'
old=getattr(aos7_fs,name)
held=False
def hold(path,obj):
 global held
 if not held and path==os.environ['PROBE_TARGET']:
  held=True
  with open(os.environ['PROBE_MARK'],'w') as f:json.dump({'pid':os.getpid(),'target':path,'operation':name},f)
  os.kill(os.getpid(),signal.SIGSTOP)
  setattr(aos7_fs,name,old)
 return old(path,obj)
setattr(aos7_fs,name,hold)
''')
  env=dict(os.environ,PYTHONPATH=str(hook),PROBE_LIB=str(REPO/'proto7-1/lib'),PROBE_ACTION=action,PROBE_MARK=str(root/'marker.json'),PROBE_TARGET=str(node/'.aos'/('round.json' if action=='tick' else 'rounds.jsonl')))
  p=subprocess.Popen([sys.executable,str(REPO/'proto7-1/bin'/('aos7-'+action)),str(root),'n'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  end=time.monotonic()+3
  while not (root/'marker.json').exists():
   if time.monotonic()>end:raise TimeoutError()
   time.sleep(.005)
  r['marker']=json.loads((root/'marker.json').read_text())
  if change=='delete':shutil.rmtree(node)
  else:node.rename(root/'moved')
  r['old_path_exists_before_resume']=node.exists();os.kill(p.pid,signal.SIGCONT)
  p.wait(timeout=3)
  stdout,stderr=p.communicate();r.update(rc=p.returncode,stdout=stdout,stderr=stderr,old_path_exists_after=node.exists(),old_files=files(node),moved_files=files(root/'moved'))
 finally:
  if p and p.poll() is None:p.kill();p.wait()
  shutil.rmtree(root);r['cleanup']={'root_removed':not root.exists(),'child_returncode':p.returncode if p else None}
 out.append(r)
(HERE/'gone_mid_action.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps([{'action':x['action'],'change':x['change'],'rc':x['rc'],'rebuilt':x['old_path_exists_after'],'files':list(x['old_files'])} for x in out]))
