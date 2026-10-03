import json, os, pathlib, signal, subprocess, tempfile, time
BASE=pathlib.Path(__file__).resolve().parents[4]
BIN=BASE/'bin'
OUT=pathlib.Path(__file__).resolve().parent
ROOT=pathlib.Path(tempfile.mkdtemp(prefix='astra-overlap-'))
procs=[]
def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True); tmp=p.with_name(p.name+'.tmp'); tmp.write_text(json.dumps(x) if not isinstance(x,str) else x);tmp.replace(p)
def read(p):
 try:return json.loads(p.read_text())
 except:return None
def daemon(root,label):
 log=open(OUT/(label+'.log'),'w');p=subprocess.Popen(['python3',str(BIN/'aos7-daemon'),str(root)],stdout=log,stderr=log,start_new_session=True);procs.append((p,root));return p
def wait(fn,timeout=10):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  if fn():return
  time.sleep(.03)
 raise TimeoutError()
def stop(p,r):
 if p.poll() is None:
  write(r/'.aosd/ctl/stop-test.json',{'op':'stop','kill':True,'by':'overlap-test'});p.wait(timeout=12)
def snap(root):
 return {str(p.relative_to(root)):read(p) for p in root.rglob('*.json') if not 'ctl-done' in str(p)}
results={'root':str(ROOT)}
try:
 # Two independent timelines are handed the same shared folder.
 space=ROOT/'shared'; (space/'mail').mkdir(parents=True)
 worker='''import json,os,pathlib,time\np=pathlib.Path('../mail/events.jsonl')\nfor i in range(4):\n with p.open('a') as f:f.write(json.dumps({'node':os.environ['AOS7_NODE_ID'],'tid':os.environ['AOS7_TID'],'i':i})+'\\n')\n time.sleep(.015)\n'''
 for name in ['alpha','beta']:
  node=space/name
  write(node/'.aos/timeline.json',{'interval_ms':100})
  write(node/'.aos/tasks.json',{'tasks':[{'name':'writer','mode':'each','argv':['python3','worker.py'],'dirs':['../mail']}]})
  write(node/'worker.py',worker)
 p=daemon(space,'shared'); wait(lambda:(read(space/'alpha/.aos/round.json') or {}).get('round',0)>=25)
 # same-root duplicate should fail visibly
 dup=subprocess.run(['python3',str(BIN/'aos7-daemon'),str(space)],capture_output=True,text=True,timeout=3)
 results['same_root']={'code':dup.returncode,'stdout':dup.stdout,'stderr':dup.stderr}
 stop(p,space)
 results['shared']={'state':snap(space),'events':(space/'mail/events.jsonl').read_text()}
 # Live takeover: a child daemon begins over a subtree the parent already owns.
 live=ROOT/'takeover';child=live/'child';worker=child/'work'
 write(worker/'.aos/timeline.json',{'interval_ms':180})
 write(worker/'.aos/tasks.json',{'tasks':[{'name':'sleeper','mode':'keep','argv':['python3','worker.py']}]})
 write(worker/'worker.py','import time\nwhile True: time.sleep(.1)\n')
 parent=daemon(live,'takeover-parent');wait(lambda:(read(worker/'.aos/round.json') or {}).get('round',0)>=3)
 results['takeover_before']=snap(live)
 sub=daemon(child,'takeover-child');wait(lambda:(read(worker/'.aos/round.json') or {}).get('round',0)>=12)
 results['takeover_during']=snap(live)
 stop(sub,child);time.sleep(.4)
 results['takeover_after_child_stop']=snap(live)
 stop(parent,live)
 # Nested daemon represented by ordinary task, then parent stop kills it.
 nest=ROOT/'nested';outer=nest/'team';subroot=outer/'sub';unit=subroot/'unit'
 write(outer/'.aos/timeline.json',{'interval_ms':150})
 write(outer/'.aos/tasks.json',{'tasks':[{'name':'subd','mode':'keep','argv':['python3',str(BIN/'aos7-daemon'),'sub']}]})
 (subroot/'.aosd').mkdir(parents=True)
 write(unit/'.aos/timeline.json',{'interval_ms':90})
 write(unit/'.aos/tasks.json',{'tasks':[{'name':'sleeper','mode':'keep','argv':['python3','worker.py']}]})
 write(unit/'worker.py','import time\nwhile True: time.sleep(.1)\n')
 p=daemon(nest,'nested');wait(lambda:(read(unit/'.aos/round.json') or {}).get('round',0)>=10)
 results['nested_before_stop']=snap(nest)
 stop(p,nest);time.sleep(.5)
 results['nested_after_stop']=snap(nest)
 results['processes']=[{'pid':p.pid,'returncode':p.poll(),'root':str(r)} for p,r in procs]
finally:
 for p,r in reversed(procs):
  if p.poll() is None:
   try:stop(p,r)
   except Exception:
    os.killpg(p.pid,signal.SIGKILL);p.wait()
 (OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
 print(json.dumps({'root':str(ROOT),'results':str(OUT/'results.json'),'cases':list(results)},ensure_ascii=False))
