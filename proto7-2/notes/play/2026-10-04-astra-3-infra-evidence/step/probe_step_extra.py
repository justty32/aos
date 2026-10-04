#!/usr/bin/env python3
"""Additional live tick/tock QA: EACCES recovery, late result/resume/close. Own /tmp only."""
import json,os,pathlib,subprocess,sys,traceback
HERE=pathlib.Path(__file__).resolve().parent;TOP=HERE.parents[3]
sys.path[:0]=[str(TOP/'packs/step/tests'),str(TOP/'packs/step'),str(TOP/'tests')]
from test_step import StepCase,probe_table
from aos7_fs import read_json
rows=[];roots=[]
def execute(name,fn):
 c=StepCase('runTest');c.setUp();roots.append(c.root)
 try:rows.append({'probe':name,**fn(c)})
 except Exception as e:rows.append({'probe':name,'probe_error':repr(e),'traceback':traceback.format_exc()})
 finally:c.doCleanups()
 print(name,flush=True)
def unreadable(c):
 node=c.mknode('a');t=probe_table('io',gate=True);c.set_tasks(node,[c.install(node,'io',t)]);gate=pathlib.Path(c.jd(node,'io','gate-a'));gate.touch()
 c.run_until(node,'io',lambda:os.path.exists(str(gate)+'.entered'));frame=pathlib.Path(c.jd(node,'io','frame.json'));before=frame.read_bytes();frame.chmod(0)
 try:
  for _ in range(2):c.cycle(node,'io')
  error=c.err(node,'io');attempt_count=len(c.ran(node,'io-a'))
 finally:frame.chmod(0o644)
 unchanged=before==frame.read_bytes();gate.unlink();c.run_until(node,'io',lambda:c.frame(node,'io').get('phase')=='ended')
 return {'classification':'X','fault':'chmod frame.json 000: real EACCES','error':error,'fault_hit':"PermissionError" in error.get('why','') or 'EACCES' in error.get('why',''),'frame_unchanged_during_failure':unchanged,'child_runs_during_failure':attempt_count,'final_frame':c.frame(node,'io')}
def late(c):
 node=c.mknode('a');t=probe_table('lateok',a={'patience':1},gate=True);c.set_tasks(node,[c.install(node,'lateok',t)]);gate=pathlib.Path(c.jd(node,'lateok','gate-a'));gate.touch()
 c.run_until(node,'lateok',lambda:c.frame(node,'lateok').get('phase')=='halted');halted=c.frame(node,'lateok');gate.unlink();c.wait_for(lambda:c.results(node,'lateok','a'))
 c.cycle(node,'lateok');before=c.frame(node,'lateok');r=c.step_cli(node,'resume','jobs/lateok');c.run_until(node,'lateok',lambda:c.frame(node,'lateok').get('phase')=='ended');ended=c.frame(node,'lateok');out=pathlib.Path(c.jd(node,'lateok','out','a.txt'));original=out.read_bytes();cl=c.step_cli(node,'close','jobs/lateok')
 return {'classification':'pass','halted':halted,'result_arrived_but_phase':before['phase'],'resume_returncode':r.returncode,'ended':ended,'a_runs':len(c.ran(node,'lateok-a')),'close_returncode':cl.returncode,'results_directory_exists':os.path.exists(c.jd(node,'lateok','results')),'output_preserved':out.read_bytes()==original,'closed':c.frame(node,'lateok').get('closed')}
execute('frame_EACCES_freeze_recover',unreadable);execute('late_result_resume_close',late)
ps=subprocess.run(['ps','-eo','pid,ppid,stat,args'],capture_output=True,text=True,check=True).stdout
rows.append({'probe':'cleanup','roots':roots,'roots_remaining':[r for r in roots if os.path.exists(r)],'ps_root_matches':[ln for ln in ps.splitlines() if any(r in ln for r in roots)]})
(HERE/'step-extra.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
