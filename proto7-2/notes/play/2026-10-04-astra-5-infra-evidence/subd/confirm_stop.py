#!/usr/bin/env python3
"""Repeat A6-01 with /proc starttime and actual task run identity."""
import importlib.util,json,os,shutil,signal,subprocess,sys,time,traceback
from pathlib import Path
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('probe',P/'probe_subd.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def identity(pid):
 try:
  p=Path(f'/proc/{pid}');s=(p/'stat').read_text().split(') ',1)[1].split()
  return {'pid':pid,'state':s[0],'ppid':int(s[1]),'pgid':int(s[2]),'starttime':int(s[19]),'aos_env':[e.decode() for e in (p/'environ').read_bytes().split(b'\0') if e.startswith(b'AOS7_')]}
 except OSError:return {'pid':pid,'state':'gone'}
rows=[]
for kind,point,n in [('normal',None,1),('stopped-tmp','tmp:stopped.json',1),('life-tmp','tmp:subd-life.json',3)]:
 for i in range(1,4):
  c=m.Case(f'confirm-{kind}-{i}');r={'kind':kind,'repeat':i}
  try:
   sub=c.space();p=c.start(allow=True,point=point,n=n);d=c.daemon(sub);old=c.ready(sub)
   r['before_stop']=identity(old);r['stop_receipt']=c.ctl(sub,'stop');r['wrapper_rc']=p.wait(15);r['at_stopped']=identity(old)
   r['life']=m.read(sub/'.aosd/subd-life.json');r['status']=m.read(sub/'.aosd/status.json');r['hit']=m.read(c.root/'hit.json');r['stopped_exists']=(sub/'.aosd/stopped.json').exists()
   r['stopped_record']=m.read(sub/'.aosd/stopped.json')
   r['temp_life']=[{'path':x.name,'record':m.read(x)} for x in (sub/'.aosd').glob('.subd-life.json.tmp.*')]
   if r['stopped_exists']:(sub/'.aosd/stopped.json').unlink()
   c.start(allow=True);r['new_daemon']=c.daemon(sub,exclude=(d,));time.sleep(.4);r['after_restart']=identity(old)
   r['new_ready']=m.read(sub/'n1/.aos/tasks/w/ready.json');r['new_life']=m.read(sub/'.aosd/subd-life.json');r['bug_reproduced']=kind!='normal' and not m.live(old)
   r['control_pass']=kind=='normal' and m.live(old) and r['before_stop']['starttime']==r['after_restart']['starttime']
  except Exception:r['error']=traceback.format_exc()
  finally:r['cleanup']=c.cleanup();rows.append(r);print(json.dumps({k:v for k,v in r.items() if k not in ('cleanup','before_stop','at_stopped')},ensure_ascii=False),flush=True)
result={'cases':rows,'final_proc_remaining':m.belonging(m.TMP),'tmp':str(m.TMP)}
if not result['final_proc_remaining']:m.HOOK.unlink();m.TMP.rmdir()
result['tmp_removed']=not m.TMP.exists();(P/'confirm-stop.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
