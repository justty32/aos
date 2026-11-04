#!/usr/bin/env python3
"""I-06 overflow default and I-08 wake follow-up; direct daemon, no wrapper."""
import json,pathlib,subprocess,sys,tempfile,time,shutil
P=pathlib.Path; HERE=P(__file__).resolve().parent; REPO=next(p for p in HERE.parents if (p/'proto7-1/lib').is_dir())
def w(p,x):
 p.parent.mkdir(parents=True,exist_ok=True); q=p.with_suffix('.tmp');q.write_text(json.dumps(x));q.replace(p)
def rd(p):
 try:return json.loads(p.read_text())
 except (OSError,ValueError):return None
def wait(f,sec=5):
 end=time.monotonic()+sec
 while time.monotonic()<end:
  v=f()
  if v:return v
  time.sleep(.01)
 raise TimeoutError()
out={}
for kind in ['overflow','wake']:
 r=P(tempfile.mkdtemp(prefix='astra5-time-extra-'+kind+'-'));p=None
 try:
  w(r/'n/.aos/timeline.json',{'interval_ms':10**309 if kind=='overflow' else 86400000});w(r/'n/.aos/tasks.json',{'tasks':[]})
  p=subprocess.Popen([sys.executable,str(REPO/'proto7-1/bin/aos7-daemon'),str(r)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  wait(lambda:rd(r/'.aosd/status.json'))
  time.sleep(1.25 if kind=='overflow' else .15)
  before=rd(r/'.aosd/status.json');w(r/'n/.aos/timeline.json',{'interval_ms':100})
  started=time.monotonic();w(r/'.aosd/ctl/repair.json',{'op':'rescan' if kind=='overflow' else 'wake','node':'n'})
  after=wait(lambda:(x if (x:=rd(r/'.aosd/status.json')) and x['nodes']['n']['round']>=3 else None))
  out[kind]={'root':str(r),'before':before,'after':after,'repair_to_round3_ms':(time.monotonic()-started)*1000,'log':[json.loads(x) for x in (r/'.aosd/log.jsonl').read_text().splitlines()]}
 finally:
  if p and p.poll() is None:p.terminate();p.wait(timeout=5)
  shutil.rmtree(r)
  out[kind]['cleanup']={'daemon_returncode':p.returncode,'root_removed':not r.exists()}
(HERE/'extra.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({k:{'before':v['before']['nodes'],'repair_to_round3_ms':v['repair_to_round3_ms']} for k,v in out.items()},ensure_ascii=False))
