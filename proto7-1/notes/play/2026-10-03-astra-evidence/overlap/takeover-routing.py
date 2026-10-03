import json,os,pathlib,subprocess,tempfile,time
OUT=pathlib.Path(__file__).resolve().parent; BIN=OUT.parents[3]/'bin';ROOT=pathlib.Path(tempfile.mkdtemp(prefix='astra-route-'));NODE=ROOT/'child/work'
def w(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(x) if not isinstance(x,str) else x);tmp.replace(p)
def r(p):
 try:return json.loads(p.read_text())
 except:return {}
def wait(fn):
 for _ in range(300):
  if fn():return
  time.sleep(.03)
 raise TimeoutError()
def launch(root,label):
 return subprocess.Popen(['python3',str(BIN/'aos7-daemon'),str(root)],stdout=open(OUT/(label+'.log'),'w'),stderr=subprocess.STDOUT,start_new_session=True)
def stop(p,root):
 if p.poll() is None:w(root/'.aosd/ctl/stop.json',{'op':'stop','kill':True});p.wait(timeout=10)
w(NODE/'.aos/timeline.json',{'interval_ms':120})
w(NODE/'.aos/tasks.json',{'tasks':[{'name':'self-control','mode':'keep','argv':['python3','worker.py']}]})
w(NODE/'worker.py','''import json,os,pathlib,time\nroot=pathlib.Path(os.environ['AOS7_ROOT']);node=pathlib.Path(os.environ['AOS7_NODE']);task=pathlib.Path(os.environ['AOS7_TASK'])\n(task/'environment.json').write_text(json.dumps({k:v for k,v in os.environ.items() if k.startswith('AOS7_')}))\nwhile not (node/'trigger').exists():time.sleep(.02)\np=root/'.aosd/ctl/self-pause.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps({'op':'pause','node':os.environ['AOS7_NODE_ID'],'by':os.environ['AOS7_TID']}));tmp.replace(p)\nwhile True:time.sleep(.1)\n''')
parent=launch(ROOT,'routing-parent');child=None
try:
 wait(lambda:r(NODE/'.aos/round.json').get('round',0)>=3)
 child=launch(ROOT/'child','routing-child')
 wait(lambda:r(NODE/'.aos/round.json').get('round',0)>=8)
 w(NODE/'trigger','go')
 wait(lambda:(ROOT/'.aosd/ctl-done/self-pause.json').exists())
 round_pause=r(NODE/'.aos/round.json')
 wait(lambda:r(NODE/'.aos/round.json').get('round',0)>=round_pause['round']+5)
 result={'root':str(ROOT),'round_when_pause_ack':round_pause,'round_after':r(NODE/'.aos/round.json'),'parent_status':r(ROOT/'.aosd/status.json'),'child_status':r(ROOT/'child/.aosd/status.json'),'control_done':r(ROOT/'.aosd/ctl-done/self-pause.json'),'environment':r(NODE/'.aos/tasks/self-control-r1/environment.json'),'birth':r(NODE/'.aos/tasks/self-control-r1/birth.json')}
 (OUT/'takeover-routing-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
finally:
 if child:stop(child,ROOT/'child')
 stop(parent,ROOT)
