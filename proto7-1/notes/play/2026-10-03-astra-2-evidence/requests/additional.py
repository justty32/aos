#!/usr/bin/env python3
"""Daemon bad-field isolation plus actual agent auto-mount name collision."""
import json,os,pathlib,shutil,signal,subprocess,sys,tempfile,time
HERE=pathlib.Path(__file__).resolve().parent
REPO=next(p for p in HERE.parents if (p/'proto7-1/bin/aos7-tick').exists())
BIN=REPO/'proto7-1/bin'
RESULT=[]

def read(p):
 try:return json.loads(p.read_text())
 except (OSError,ValueError):return None

def write(p,d):
 p.parent.mkdir(parents=True,exist_ok=True); q=p.with_suffix('.tmp');q.write_text(json.dumps(d));q.replace(p)

def wait(pred,timeout=5):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  if pred():return
  time.sleep(.015)
 raise TimeoutError('condition timeout')

def alive(pid):
 try:return pathlib.Path(f'/proc/{pid}/stat').read_text().split(') ')[1].split()[0]!='Z'
 except (OSError,IndexError):return False

def run(prog,root,node):
 p=subprocess.run([sys.executable,str(BIN/prog),str(root),node],capture_output=True,text=True,timeout=8)
 return {'rc':p.returncode,'stdout':p.stdout,'stderr':p.stderr}

def stop_tasks(root):
 pids=[]
 for p in root.glob('**/.aos/tasks.json'):write(p,{'tasks':[]})
 for p in root.glob('**/pid.json'):
  d=read(p) or {};pids.extend(d.get(k) for k in ['pid','runner_pid'] if d.get(k));write(p.parent/'ctl.json',{'op':'kill'})
 for p in root.glob('**/.aos/timeline.json'):run('aos7-tock',root,str(p.parent.parent.relative_to(root)))
 time.sleep(.15)
 return {'pids':pids,'alive':[p for p in pids if alive(p)]}

root=pathlib.Path(tempfile.mkdtemp(prefix='astra2-requests-daemon-')); proc=None
try:
 for node in ['n','healthy']:
  write(root/node/'.aos/timeline.json',{'interval_ms':150})
  write(root/node/'.aos/tasks.json',{'tasks':[{'name':'worker','mode':'keep','argv':['python3','-c','import time;time.sleep(120)']},{'name':'pulse','mode':'each','argv':['python3','-c','pass']} ]})
 with (root/'daemon.log').open('w') as log:proc=subprocess.Popen([sys.executable,str(BIN/'aos7-daemon'),str(root)],stdout=log,stderr=log)
 td=root/'n/.aos/tasks/worker-r1';wait(lambda:(td/'pid.json').exists())
 # Pause through documented daemon ctl for deterministic injection before the next tick.
 write(root/'.aosd/ctl/pause.json',{'op':'pause','node':'n'});wait(lambda:(read(root/'.aosd/status.json') or {}).get('nodes',{}).get('n',{}).get('phase')=='paused')
 before=read(root/'n/.aos/round.json')['round']
 write(td/'mount-req/01-good.json',{'name':'ok','path':'recipient/inbox'})
 write(td/'mount-req/02-bad.json',{'name':['bad'],'path':'recipient/inbox'})
 write(td/'mount-req/03-later.json',{'name':'later','path':'recipient/other'})
 write(root/'.aosd/ctl/resume.json',{'op':'resume','node':'n'})
 wait(lambda:(read(root/'n/.aos/round.json') or {}).get('round',0)>=before+3)
 status=read(root/'.aosd/status.json')
 RESULT.append({'case':'daemon-bad-name','before_round':before,'status':status,'birth':read(td/'birth.json'),'receipts':{p.name:read(p) for p in (td/'mount-done').glob('*.json')},'bad_request_exists':(td/'mount-req/02-bad.json').exists(),'bad_receipt_exists':(td/'mount-done/02-bad.json').exists(),'rounds':{p.name:read(p) for p in (root/'n/.aos/rounds').glob('*.json')},'task_ids':sorted(p.name for p in (root/'n/.aos/tasks').iterdir()),'log':(root/'.aosd/log.jsonl').read_text()})
finally:
 if proc and proc.poll() is None:
  write(root/'.aosd/ctl/stop.json',{'op':'stop','kill':True});proc.wait(timeout=8)
 cleanup=stop_tasks(root);shutil.rmtree(root);RESULT.append({'case':'daemon-cleanup',**cleanup,'root_removed':not root.exists(),'daemon_exit':proc.returncode if proc else None})

root=pathlib.Path(tempfile.mkdtemp(prefix='astra2-requests-collision-'))
try:
 for node in ['sender','a/b','a_b']:
  write(root/node/'.aos/timeline.json',{'interval_ms':100})
  write(root/node/'.aos/tasks.json',{'tasks':[]})
 write(root/'sender/.aos/tasks.json',{'tasks':[{'name':'agent','mode':'keep','argv':['aos7-agent']}],'mount_allow':['a'] + ['a_b']})
 write(root/'sender/agent.json',{'name':'sender','llm':'fake'})
 write(root/'sender/goal.json',{'say_first':{'to':'a/b','body':'hello first'}})
 for _ in range(8):run('aos7-tick',root,'sender');time.sleep(.035);run('aos7-tock',root,'sender');time.sleep(.06)
 td=root/'sender/.aos/tasks/agent-r1'
 RESULT.append({'case':'first-auto-name','birth':read(td/'birth.json'),'state':read(td/'state.json'),'first_inbox':{p.name:read(p) for p in (root/'a/b/inbox').glob('*.json')}})
 write(root/'sender/goal.json',{'say_first':{'to':'a_b','body':'hello second'}})
 for _ in range(8):run('aos7-tick',root,'sender');time.sleep(.035);run('aos7-tock',root,'sender');time.sleep(.06)
 RESULT.append({'case':'second-auto-name','birth':read(td/'birth.json'),'state':read(td/'state.json'),'receipts':{p.name:read(p) for p in (td/'mount-done').glob('*.json')},'outbox':{str(p.relative_to(root/'sender')):read(p) for p in (root/'sender/outbox').rglob('*.json')},'first_inbox':{p.name:read(p) for p in (root/'a/b/inbox').glob('*.json')},'second_inbox':{p.name:read(p) for p in (root/'a_b/inbox').glob('*.json')}})
finally:
 cleanup=stop_tasks(root);shutil.rmtree(root);RESULT.append({'case':'collision-cleanup',**cleanup,'root_removed':not root.exists()})
write(HERE/'additional-results.json',RESULT)
print(json.dumps(RESULT,ensure_ascii=False,indent=2))
