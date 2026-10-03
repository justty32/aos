#!/usr/bin/env python3
"""Bounded infrastructure time probes. Real programs, controlled clock/stall injection; no LLM."""
import json, os, pathlib, shutil, signal, subprocess, sys, tempfile, time
HERE=pathlib.Path(__file__).resolve().parent
REPO=next(p for p in HERE.parents if (p/'proto7-1/lib').is_dir())
LIB=REPO/'proto7-1/lib'
roots=[]; ps=[]
def w(p,x):
 p.parent.mkdir(parents=True,exist_ok=True); q=p.with_suffix('.tmp');q.write_text(json.dumps(x));q.replace(p)
def read(p,default=None):
 try:return json.loads(p.read_text())
 except (OSError,ValueError):return default
def rows(p):
 try:return [json.loads(s) for s in p.read_text().splitlines()]
 except OSError:return []
def wait(pred,seconds=3):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  v=pred()
  if v:return v
  time.sleep(.003)
 raise TimeoutError('probe condition')
def root(tag):
 r=pathlib.Path(tempfile.mkdtemp(prefix='astra4-time-'+tag+'-'));roots.append(r);return r
def node(r,n,ms,tasks=[]):
 w(r/n/'.aos/timeline.json',{'interval_ms':ms});w(r/n/'.aos/tasks.json',{'tasks':tasks})
def start(r,stall=False,clock=False):
 # Driver logs monotonic process start/end; only stall case replaces run_prog.
 wrapper=r/'driver.py';wrapper.write_text('''import sys,os,json,time,subprocess,signal
sys.path.insert(0,sys.argv[2])
import aos7_daemon_timeline as tl
import aos7_daemon as dm
from aos7_fs import BIN,env_with_bin
root=sys.argv[1]
old=tl.run_prog
stalled=False
def run(name,root,nid):
 global stalled
 a=time.monotonic()
 if os.environ.get('STALL') and name=='aos7-tick' and not stalled:
  stalled=True
  p=subprocess.Popen([sys.executable,os.path.join(BIN,name),root,nid],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env_with_bin())
  os.kill(p.pid,signal.SIGSTOP)
  with open(root+'/stall.json','w') as f:json.dump({'pid':p.pid,'at':time.monotonic()},f)
  out,err=p.communicate();obj=json.loads(out.strip().splitlines()[-1]) if out.strip() else None
  result=(p.returncode,obj,err)
 else:result=old(name,root,nid)
 b=time.monotonic()
 with open(root+'/times.jsonl','a') as f:f.write(json.dumps({'prog':name,'node':nid,'start':a,'end':b,'round':(result[1] or {}).get('round'),'rc':result[0]})+'\\n')
 return result
tl.run_prog=run
sys.exit(dm.main([root]))
''')
 env=dict(os.environ,STALL='1' if stall else '')
 if clock:
  hook=r/'hook';hook.mkdir();(hook/'sitecustomize.py').write_text('''import datetime,os
_base=datetime.datetime
class Clock(_base):
 @classmethod
 def now(cls,tz=None):
  try:delta=float(open(os.environ['CLOCK_FILE']).read())
  except (OSError,ValueError):delta=0
  return _base.now(tz)+datetime.timedelta(seconds=delta)
datetime.datetime=Clock
''');env.update(PYTHONPATH=str(hook),CLOCK_FILE=str(r/'offset'))
 err=open(r/'stderr','w');p=subprocess.Popen([sys.executable,str(wrapper),str(r),str(LIB)],env=env,stdout=subprocess.DEVNULL,stderr=err);err.close();ps.append(p);return p
def stop(p):
 if p.poll() is None:p.terminate();p.wait(timeout=5)
def save(tag,r,extra={}):
 payload=dict(extra,events=rows(r/'times.jsonl'),daemon_log=rows(r/'.aosd/log.jsonl'),status=read(r/'.aosd/status.json'),stderr=(r/'stderr').read_text())
 (HERE/(tag+'.json')).write_text(json.dumps(payload,ensure_ascii=False,indent=1))
 return payload
results={}
try:
 r=root('interval');
 for n,ms in [('one',1),('zero',0),('negative',-10),('hundred',100),('day',86400000)]:node(r,n,ms)
 p=start(r);time.sleep(1.05);a=time.monotonic();stop(p);results['interval']=save('interval',r,{'stop_ms':(time.monotonic()-a)*1000})
 r=root('invalid');
 for n,ms in [('null',None),('text','bad'),('nan',float('nan')),('inf',float('inf')),('overflow',10**309),('good',100)]:node(r,n,ms)
 p=start(r);time.sleep(.25);before=read(r/'.aosd/status.json')
 for n in ['null','text','nan','inf','overflow']:w(r/n/'.aos/timeline.json',{'interval_ms':100})
 w(r/'.aosd/ctl/rescan.json',{'op':'rescan'});time.sleep(.3);after=read(r/'.aosd/status.json');stop(p);results['invalid']=save('invalid',r,{'before_repair':before,'after_repair_rescan':after})
 r=root('change');node(r,'n',1000);p=start(r)
 wait(lambda:len(rows(r/'times.jsonl'))>=2);changed=time.monotonic();w(r/'n/.aos/timeline.json',{'interval_ms':100})
 wait(lambda:len([e for e in rows(r/'times.jsonl') if e['prog']=='aos7-tick'])>=4,3);stop(p);results['change']=save('change',r,{'changed_mono':changed,'old_ms':1000,'new_ms':100})
 r=root('longchange');node(r,'n',86400000);p=start(r);wait(lambda:len(rows(r/'times.jsonl'))>=2)
 changed=time.monotonic();w(r/'n/.aos/timeline.json',{'interval_ms':10});w(r/'.aosd/ctl/rescan.json',{'op':'rescan'});time.sleep(.3)
 unchanged=read(r/'n/.aos/round.json');a=time.monotonic();stop(p);results['longchange']=save('longchange',r,{'changed_mono':changed,'observed_ms':300,'round_after_change':unchanged,'stop_ms':(time.monotonic()-a)*1000})
 r=root('stall');node(r,'n',100);p=start(r,stall=True);s=wait(lambda:read(r/'stall.json'));time.sleep(.35);resumed=time.monotonic();os.kill(s['pid'],signal.SIGCONT)
 wait(lambda:len(rows(r/'times.jsonl'))>=6);stop(p);results['stall']=save('stall',r,{'stop_injection':s,'resume_mono':resumed})
 r=root('clock');node(r,'n',100);(r/'offset').write_text('0');p=start(r,clock=True);wait(lambda:len(rows(r/'times.jsonl'))>=4)
 changes=[]
 for offset in [3600,-3600,0]:
  (r/'offset').write_text(str(offset));changes.append({'offset_s':offset,'mono':time.monotonic()});time.sleep(.31)
 stop(p);results['clock']=save('clock',r,{'injected_wall_offsets':changes,'rounds':rows(r/'n/.aos/rounds.jsonl')})
 r=root('early');node(r,'empty',500);node(r,'short',500,[{'name':'short','mode':'each','argv':[sys.executable,'-c','import time;time.sleep(.01)']}]);node(r,'keep',500,[{'name':'keep','mode':'keep','argv':[sys.executable,'-c','import time;time.sleep(30)']}]);p=start(r);time.sleep(1.2);stop(p);results['early']=save('early',r)
finally:
 for p in ps:
  try:stop(p)
  except Exception:
   p.kill();p.wait()
 for r in roots:shutil.rmtree(r,ignore_errors=True)
print(json.dumps({'cases':list(results),'cleaned_roots':list(map(str,roots))}))
