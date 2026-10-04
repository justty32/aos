#!/usr/bin/env python3
"""Read-only QA. Real daemon signals; synthetic missing-since fixture is explicitly M.
Clock rollback uses per-test Python datetime injection, never changes host wall clock.
"""
import importlib.util,json,os,signal,subprocess,sys,tarfile,time,traceback
from pathlib import Path
OUT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('probe',OUT/'probe_subd.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ROWS=[]
def ident(pid):
 try:
  s=Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split()
  return {'pid':pid,'state':s[0],'starttime':int(s[19])}
 except OSError:return {'pid':pid,'state':'gone'}
def same(before,after):return before.get('starttime')==after.get('starttime') and after['state'] not in ('gone','Z')
def receipt_list(sub):return [m.read(p) for p in sorted((sub/'.aosd/ctl-done').glob('*.json'))]
def term(c,allow,stale=False):
 sub=c.space();p=c.start(allow=allow);d=c.daemon(sub);old=c.ready(sub)
 stale_receipt=None
 if stale:
  stale_receipt=c.ctl(sub,'stop');assert p.wait(15)==0
  (sub/'.aosd/stopped.json').unlink();time.sleep(.01)
  p=c.start(allow=allow);d=c.daemon(sub,exclude=(d,));assert m.live(old)
 since=m.read(sub/'.aosd/subd-life.json')['since'];before=ident(old)
 os.kill(d,signal.SIGTERM);rc=p.wait(15)
 status=m.read(sub/'.aosd/status.json');life=m.read(sub/'.aosd/subd-life.json');receipts=receipt_list(sub)
 stopped=(sub/'.aosd/stopped.json').exists();dead=not m.live(old)
 q=c.start(allow=allow);nd=c.daemon(sub,exclude=(d,));new=c.ready(sub,exclude=(old,))
 return {'classification':'normal：SIGTERM 是核心 stop+kill，非 subd 被允許外部 stop；不留 stopped.json，keep 可重開', 'allow_stop':allow,'stale_receipt':stale_receipt,'since':since,'before_task':before,'after_term_task':ident(old),'wrapper_rc':rc,'status':status,'life':life,'receipts':receipts,'stopped_json':stopped,'new_daemon':nd,'new_task':new,'pass':rc==0 and status.get('stopped') is True and life['state']=='running' and not stopped and dead and new!=old and (not stale or stale_receipt['result']['at']<since)}
def missing_since(c):
 sub=c.space();p=c.start(allow=True,point='subd-stop-seen');d=c.daemon(sub);old=c.ready(sub)
 receipt=c.ctl(sub,'stop');assert p.wait(15)==-9
 original=m.read(sub/'.aosd/subd-life.json');fixture=dict(original);fixture.pop('since');m.write(sub/'.aosd/subd-life.json',fixture)
 q=c.start(allow=True);nd=c.daemon(sub,exclude=(d,));new=c.ready(sub,exclude=(old,))
 return {'classification':'M synthetic compatibility fixture；life 只准 subd 寫，此案手移除 since 不列 bug；歷史初版無 life、A5 首引入已有 since', 'original_life':original,'synthetic_life':fixture,'receipt':receipt,'old_task':old,'new_task':new,'new_daemon':nd,'old_alive_after_restart':m.live(old),'stopped_json':(sub/'.aosd/stopped.json').exists(),'pass':not m.live(old) and new!=old and not (sub/'.aosd/stopped.json').exists()}
def clockback(c):
 sub=c.space();hooks=c.root/'clock';hooks.mkdir();marker=c.root/'rollback-seconds'
 (hooks/'sitecustomize.py').write_text('''import datetime,os,pathlib
Real=datetime.datetime
class QAClock(Real):
 @classmethod
 def now(cls,tz=None):
  t=Real.now(tz)
  try: delta=float(pathlib.Path(os.environ['QA_CLOCK_OFFSET']).read_text())
  except (KeyError,OSError,ValueError):delta=0
  return t-datetime.timedelta(seconds=delta)
datetime.datetime=QAClock
''')
 old_env=c.env;c.env=lambda:dict(old_env(),PYTHONPATH=str(hooks),QA_CLOCK_OFFSET=str(marker))
 p=c.start(allow=True);d=c.daemon(sub);old=c.ready(sub);since=m.read(sub/'.aosd/subd-life.json')['since']
 marker.write_text('3600');receipt=c.ctl(sub,'stop');rc=p.wait(15)
 before={'life':m.read(sub/'.aosd/subd-life.json'),'status':m.read(sub/'.aosd/status.json'),'stopped':(sub/'.aosd/stopped.json').exists(),'task':ident(old)}
 q=c.start(allow=True);nd=c.daemon(sub,exclude=(d,));new=c.ready(sub,exclude=(old,))
 return {'classification':'X 環境牆鐘倒退／已知 KISS 界線；非 B/G（README 判定即 at>=since；loop6 自報不另防）','injection':'僅測試程序 datetime.now() 倒退3600秒，主機時鐘未改','since':since,'receipt':receipt,'wrapper_rc':rc,'before_restart':before,'new_daemon':nd,'new_task':new,'old_alive':m.live(old),'pass':receipt['result']['at']<since and not before['stopped'] and before['life']['state']=='running' and not m.live(old)}
def unknown(c,kind):
 sub=c.space();p=c.start(allow=True,point='subd-stop-seen');d=c.daemon(sub);old=c.ready(sub);before=ident(old)
 receipt=c.ctl(sub,'stop');assert p.wait(15)==-9
 target=str(sub/'.aosd/status.json') if kind=='status' else str(next((sub/'.aosd/ctl-done').glob('*.json')))
 hook=c.root/'eio.py';hook.write_text('import errno,os\ndef test_point(name): pass\ndef inject(op,path):\n if op=="open" and str(path)==os.environ.get("QA_EIO_PATH"): raise OSError(errno.EIO,"QA injected EIO")\n')
 old_env=c.env;c.env=lambda:dict(old_env(),AOS7_TEST_HOOKS=str(hook),QA_EIO_PATH=target)
 q=c.start(allow=True);rc=q.wait(10);during=ident(old);life=m.read(sub/'.aosd/subd-life.json');stopped=(sub/'.aosd/stopped.json').exists()
 c.env=old_env;r=c.start(allow=True);repaired_rc=r.wait(10);after=ident(old)
 return {'classification':'X 已保守處理：讀不到就不收不起，恢復讀取後補完 stop','target':target,'receipt':receipt,'rc_eio':rc,'during':during,'life_during':life,'stopped_during':stopped,'repair_rc':repaired_rc,'life_after':m.read(sub/'.aosd/subd-life.json'),'after':after,'pass':rc==1 and repaired_rc==1 and same(before,during) and same(before,after) and life['state']=='running' and not stopped and m.read(sub/'.aosd/subd-life.json')['state']=='stopped'}
def run(name,fn):
 c=m.Case(name);r={'name':name};start=time.monotonic()
 try:r.update(fn(c))
 except Exception:r.update({'pass':False,'error':traceback.format_exc()})
 finally:
  with tarfile.open(OUT/(name+'-snapshot.tar.gz'),'w:gz') as tf:tf.add(c.root,arcname=name)
  r['cleanup']=c.cleanup();r['elapsed_s']=round(time.monotonic()-start,3);ROWS.append(r)
  (OUT/'new-edges.json').write_text(json.dumps({'cases':ROWS},ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='cleanup'},ensure_ascii=False),flush=True)
for allow in (False,True):run(f'term-allow-{allow}',lambda c,allow=allow:term(c,allow))
run('term-with-old-receipt',lambda c:term(c,True,True))
run('synthetic-life-no-since',missing_since)
run('clock-rollback',clockback)
for kind in ('status','receipt'):run(f'eio-{kind}',lambda c,kind=kind:unknown(c,kind))
remaining=m.belonging(m.TMP)
if not remaining:m.HOOK.unlink();m.TMP.rmdir()
result={'cases':ROWS,'tmp':str(m.TMP),'final_proc_remaining':remaining,'tmp_removed':not m.TMP.exists()}
(OUT/'new-edges.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
