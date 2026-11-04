"""README/spec contracts via public CLI; extra restart commit-boundary SIGKILL.
Only test data in this evidence directory. Run with python3 -B.
"""
import os,sys,json,time,pathlib,tempfile,subprocess,signal,hashlib,shutil
E=pathlib.Path(__file__).resolve().parent; TOP=E.parents[2]
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
scratch=E/'docs-work';scratch.mkdir(exist_ok=True);tempfile.tempdir=str(scratch)
sys.path.insert(0,str(TOP/'tests'));sys.path.insert(0,str(TOP/'lib'))
from base import DaemonCase,read_json,write_json
import aos7_ctl,aos7_tick,aos7_tock
rows=[]
def run(name,fn):
 c=DaemonCase();c.setUp()
 try: rows.append({'id':name,'result':fn(c)})
 except Exception as e: rows.append({'id':name,'error':repr(e)});raise
 finally:c.doCleanups()
def D1(c):
 n=c.mknode(timeline=False);p=c.start_daemon();time.sleep(.2)
 before=os.path.exists(n+'/.aos/round.json');c.wait_receipt(c.ctl('register','a'));c.wait_round(1)
 c.wait_for(lambda:not c.round_json(n).get('open',True),3)
 return {'unregistered_started':before,'no_timeline_registered_round':c.last_round(n)['round'],'default_interval_ms':c.nstat()['interval_ms']}
def D2(c):
 n=c.mknode(tasks=[{'name':'o','mode':'once','argv':['true']}]);a=c.tick();c.wait_ended(n,'o');lr=c.tock();b=c.tick();c.tock()
 return {'first':a,'second':b,'tasks':c.tasks(n),'ended':lr['ended'],'slot_removed':not os.path.exists(c.slot(n,'o'))}
def D3(c):
 n=c.mknode(tasks=[{'name':'k','mode':'keep','max_live':2,'argv':['sleep','30']},{'name':'e','mode':'each','max_live':2,'argv':['sleep','30']}]);a=c.tick();c.tock();b=c.tick();c.tock();d=c.tick();c.tock()
 return {'r1':a['started'],'r2':b['started'],'r3':d['started'],'r3_skipped':c.last_round(n)['skipped']}
def D4(c):
 n=c.mknode(tasks=[{'name':'x','argv':['true']}]);c.tick();c.wait_ended(n,'x');c.tock();s=c.slot(n,'x');write_json(s+'/state.json',{'counter':71});pathlib.Path(s+'/out.log').write_text('old-output')
 a=c.tick();c.wait_ended(n,'x');c.tock();return {'new_run':a['started'],'state':read_json(s+'/state.json'),'out':pathlib.Path(s+'/out.log').read_text()}
def D5(c):
 n=c.mknode(tasks=[{'name':'bad','max_live':0,'argv':['true']},{'name':'ok','argv':['true']}]);a=c.tick();c.wait_ended(n,'ok');c.tock();return {'started':a['started'],'errors':c.last_round(n)['tasks_error']}
def D6(c):
 code="import os,json;json.dump({'cwd':os.getcwd(),'env':{k:v for k,v in os.environ.items() if k.startswith('AOS7_')},'path_first':os.environ['PATH'].split(':')[0]},open(os.environ['AOS7_NODE']+'/env.json','w'))"
 n=c.mknode('team/n',tasks=[{'name':'env','argv':[sys.executable,'-c',code]}]);c.tick('team/n');c.wait_ended(n,'env');c.tock('team/n');return read_json(n+'/env.json')
def D7(c):
 n=c.mknode();write_json(n+'/.aos/tasks.json',{'tasks':[],'mount_allow':['peer']});c.prog('aos7-ctl','add',n,json.dumps({'name':'a','argv':['true']}),json.dumps({'name':'b','argv':['true']}));a=c.tick();c.wait_ended(n,'a');c.wait_ended(n,'b');c.tock();return {'started':a['started'],'table':read_json(n+'/.aos/tasks.json')}
def D8(c):
 n=c.mknode();p=c.start_daemon(register=['a']);c.wait_round(1);a=c.ctl('pause','a','--owner','A','--by','A');c.wait_receipt(a);b=c.ctl('pause','a','--owner','B','--by','B');c.wait_receipt(b);c.wait_receipt(c.ctl('resume','a','--owner','A','--by','A'));time.sleep(.15)
 left=read_json(c.root+'/.aosd/paused.json');c.wait_receipt(c.ctl('resume','a','--owner','B','--by','B'));c.wait_round(2);return {'after_resume_A':left,'after_resume_B':read_json(c.root+'/.aosd/paused.json'),'round':c.node_round()}
def D9(c):
 n=c.mknode(tasks=[{'name':'x','argv':['true']}]);c.tick();c.wait_ended(n,'x');lr=c.tock();raw=pathlib.Path(n+'/.aos/last-round.json').read_bytes();st=c.round_json(n);st['open']=True;write_json(n+'/.aos/round.json',st);second=c.tock();return {'replayed':second.get('replayed'),'summary_unchanged':raw==pathlib.Path(n+'/.aos/last-round.json').read_bytes(),'closed':c.round_json(n)['open'] is False}
def D10(c):
 n=c.mknode(interval_ms=100);p=c.start_daemon(register=['a']);c.wait_round(1);first=c.ctl('pause','a');c.wait_receipt(first);second=c.ctl('pause','a');c.wait_receipt(second);return {'same_path':first==second,'pause_receipts':[f for f in os.listdir(c.root+'/.aosd/ctl-done') if '.pause.' in f]}
for i,fn in enumerate([D1,D2,D3,D4,D5,D6,D7,D8,D9,D10],1):run('D%02d'%i,fn)
def restart_crash(c):
 code="import os;f=open(os.environ['AOS7_NODE']+'/executions','a');f.write(os.environ['AOS7_RUN']+'\\n');f.close()"
 n=c.mknode(tasks=[{'name':'x','mode':'once','argv':[sys.executable,'-c',code]}]);c.tick();c.wait_ended(n,'x');s=c.slot(n,'x');write_json(s+'/ctl.json',{'op':'restart','by':'probe'})
 child="""import os,sys,signal
sys.path.insert(0,sys.argv[1]);import aos7_task,aos7_tock
orig=aos7_task.edit_json
def cut(*a,**kw):
 r=orig(*a,**kw);os.kill(os.getpid(),signal.SIGKILL)
aos7_task.edit_json=cut
aos7_tock.tock(sys.argv[2],'a')
"""
 p=subprocess.run([sys.executable,'-B','-c',child,str(TOP/'lib'),c.root],capture_output=True,timeout=10)
 after_cut=c.tasks(n);still_ctl=os.path.exists(s+'/ctl.json');recover=c.tock();after_recover=c.tasks(n)
 a=c.tick();c.wait_ended(n,'x');c.tock();b=c.tick();c.wait_ended(n,'x');c.tock()
 return {'cut_rc':p.returncode,'queued_after_cut':after_cut,'ctl_still_pending':still_ctl,'queued_after_recovery':after_recover,'next_started':[a['started'],b['started']],'executions':pathlib.Path(n+'/executions').read_text().splitlines()}
run('restart_crash_after_append_before_kill',restart_crash)
def owner_collision(c):
 c.mknode();a=c.ctl('pause','a','--owner','A');b=c.ctl('pause','a','--owner','B');p=c.start_daemon(register=['a']);c.wait_receipt(b);return {'same_request_path':a==b,'owners':read_json(c.root+'/.aosd/paused.json')}
run('owner_cli_pending_collision',owner_collision)
metrics={}
for version in ['proto7-1','proto7-2']:
 f=TOP.parent/version/'spec.md';t=f.read_text();metrics[version]={'lines':len(t.splitlines()),'characters':len(t),'bytes':len(t.encode()),'headings':sum(s.startswith('#') for s in t.splitlines())}
output={'document_contracts':rows,'spec_size':metrics,'temporary_leftovers':[str(p.relative_to(scratch)) for p in scratch.rglob('*')]}
(E/'docs-and-crashes.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
if not output['temporary_leftovers']:shutil.rmtree(scratch)
print(json.dumps({'cases':len(rows),'spec_size':metrics,'temporary_leftovers':output['temporary_leftovers']},ensure_ascii=False))
