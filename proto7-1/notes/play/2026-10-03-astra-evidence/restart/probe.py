import json, os, pathlib, signal, subprocess, sys, tempfile, time
REPO=pathlib.Path.cwd()
EVID=REPO/'proto7-1/notes/play/2026-10-03-astra-evidence/restart'
ROOT=pathlib.Path(tempfile.mkdtemp(prefix='astra-restart-'))
BIN=REPO/'proto7-1/bin'
(EVID/'root.txt').write_text(str(ROOT)+'\n')
def write(path,x):
 path.parent.mkdir(parents=True,exist_ok=True); t=path.with_suffix('.tmp'); t.write_text(json.dumps(x)); t.replace(path)
def read(path):
 try: return json.loads(path.read_text())
 except (FileNotFoundError,json.JSONDecodeError): return None
def wait(pred,timeout=10):
 start=time.monotonic()
 while time.monotonic()-start<timeout:
  v=pred()
  if v:return v
  time.sleep(.02)
 raise RuntimeError('timeout')
def snap(name):
 files={str(p.relative_to(ROOT)):p.read_text() for p in ROOT.rglob('*') if p.is_file() and p.name!='daemon.lock'}
 write(EVID/(name+'.json'),files)
for n in ['live','paused']:
 node=ROOT/n
 write(node/'.aos/timeline.json',{'interval_ms':500})
 write(node/'.aos/tasks.json',{'tasks':[{'name':'worker','mode':'keep','argv':['python3','worker.py']}]})
 (node/'worker.py').write_text('''import os,pathlib,time,json\np=pathlib.Path(os.environ['AOS7_TASK'])\nseen=None\nwhile True:\n try:\n  d=json.loads((p/'tock.json').read_text())\n  if d!=seen:\n   with (p/'observed.jsonl').open('a') as f:f.write(json.dumps(d)+'\\n')\n   seen=d\n except (FileNotFoundError,json.JSONDecodeError):pass\n time.sleep(.01)\n''')
log=(EVID/'daemon.log').open('w')
p=subprocess.Popen([str(BIN/'aos7-daemon'),str(ROOT)],stdout=log,stderr=log)
restarted=None
try:
 wait(lambda:read(ROOT/'live/.aos/tasks/worker-r1/pid.json'))
 write(ROOT/'.aosd/ctl/pause.json',{'op':'pause','node':'paused','by':'probe'})
 wait(lambda:(read(ROOT/'.aosd/status.json') or {}).get('nodes',{}).get('paused',{}).get('phase')=='paused')
 wait(lambda:(read(ROOT/'live/.aos/round.json') or {}).get('round',0)>=4)
 before=read(ROOT/'live/.aos/round.json')
 snap('01-before-kill')
 p.kill();p.wait()
 time.sleep(.8)
 snap('02-after-kill')
 restarted=subprocess.Popen([str(BIN/'aos7-daemon'),str(ROOT)],stdout=log,stderr=log)
 wait(lambda:(read(ROOT/'live/.aos/round.json') or {}).get('round',0)>=before['round']+4)
 snap('03-restarted')
 write(ROOT/'.aosd/ctl/stop.json',{'op':'stop','kill':True,'by':'probe'})
 restarted.wait(timeout=10)
 snap('04-stopped')
 outcome={'root':str(ROOT),'old_daemon_pid':p.pid,'new_daemon_pid':restarted.pid,'interrupted_round':before,'live_round_summaries':sorted(x.name for x in (ROOT/'live/.aos/rounds').glob('*.json')),'paused':read(ROOT/'.aosd/paused.json'),'live_births':[str(x.relative_to(ROOT)) for x in ROOT.glob('live/.aos/tasks/*/birth.json')]}
 write(EVID/'outcome.json',outcome);print(json.dumps(outcome,indent=2))
finally:
 for proc in [p,restarted]:
  if proc is not None and proc.poll() is None: proc.terminate();proc.wait(timeout=10)
 for path in ROOT.glob('*/.aos/tasks/*/pid.json'):
  info=read(path)
  for key in ['pgid']:
   try:os.killpg(info[key],signal.SIGKILL)
   except ProcessLookupError:pass
 log.close()
