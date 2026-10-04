#!/usr/bin/env python3
"""QA-only probes. Creates own /tmp roots; does not edit repo implementation/tests.
Run from repo root: python3 proto7-2/notes/play/2026-10-04-astra-4-infra-evidence/step/probe_step.py
"""
import copy, json, os, pathlib, subprocess, sys, time, traceback
HERE=pathlib.Path(__file__).resolve().parent
TOP=HERE.parents[3]
sys.path[:0]=[str(TOP/'packs/step/tests'),str(TOP/'packs/step'),str(TOP/'tests')]
from test_step import StepCase, probe_table, child
import aos7_step as step
import aos7_ctl
from aos7_fs import read_json, write_json
records=[]
roots=[]
def emit(name,data):
    records.append({'probe':name,**data})
    (HERE/'step-probes.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    print(name, flush=True)
def scenario(name,fn):
    case=StepCase('runTest'); case.setUp(); roots.append(case.root)
    try: emit(name,fn(case))
    except Exception as e: emit(name,{'probe_error':repr(e),'traceback':traceback.format_exc()})
    finally: case.doCleanups()
def basic_wait(job='waitstart'):
    return {'job':job,'start':'w','steps':{'w':{'wait':{'exists':'${job}/ack'},'patience':2,'then':'done'},'done':{'end':'ok'}}}
def initial_wait(c):
    node=c.mknode('a'); t=basic_wait(); c.set_tasks(node,[c.install(node,t['job'],t)])
    frames=[]
    for _ in range(8):
        c.cycle(node,t['job']); fr=c.frame(node,t['job']); frames.append({k:fr.get(k) for k in ('pc','phase','since','seen','halt')})
    assert frames[-1]['phase']=='halted' and frames[-1]['halt']['kind']=='timeout'
    assert frames[0]['since']==1 and frames[3]['halt']['round']==4
    return {'classification':'pass','checker_errors':step.errors_of(step.check(t)),'frames':frames,'observed':'since=1，r4差值3>2後 timeout，A4-03修好'}
def entered_wait(c):
    node=c.mknode('a'); t=basic_wait('waitentered');t['start']='a';t['steps']['a']={'run':child('enter'),'finite':True,'ok':'w'}
    c.set_tasks(node,[c.install(node,t['job'],t)]); frames=[]
    for _ in range(8):
        c.cycle(node,t['job']);fr=c.frame(node,t['job']);frames.append({k:fr.get(k) for k in ('pc','phase','since','seen','halt')})
        if fr.get('phase')=='halted':break
    return {'classification':'pass','frames':frames,'observed':'run→wait 有 since，差值>2 時 timeout'}
def delayed_intent(c):
    node=c.mknode('a'); t=probe_table('late');c.set_tasks(node,[c.install(node,'late',t)]);c.crash_at(node,'late','after-intent')
    c.cycle(node,'late');before=c.frame(node,'late'); c.set_enabled(node,'step-late',False)
    for _ in range(3):c.cycle(node,'late')
    c.set_enabled(node,'step-late',True);c.cycle(node,'late');after=c.frame(node,'late')
    return {'classification':'X','before':before,'after':after,'runs_a':len(c.ran(node,'late-a')),'observed':'意圖寫後 SIGKILL，跨超過1回合才接回：unknown，不重派'}
def resend_twice(c):
    node=c.mknode('a');t=probe_table('twice',a={'on_unknown':'resend'},gate=True);c.set_tasks(node,[c.install(node,'twice',t)]);path=c.jd(node,'twice','gate-a');pathlib.Path(path).touch()
    c.run_until(node,'twice',lambda:os.path.exists(path+'.entered'))
    frames=[]
    for n in (1,2):
        c.wait_pid(node,'step-twice-a'); c.wait_for(lambda:c.birth(node,'step-twice-a').get('x',{}).get('step',{}).get('attempt','').endswith('-a'+str(n)),10)
        frames.append(c.frame(node,'twice'))
        aos7_ctl.task_ctl(c.slot(node,'step-twice-a'),why='QA kill same step attempt',run=c.birth(node,'step-twice-a')['run'])
        if n==1:
            c.run_until(node,'twice',lambda:(c.frame(node,'twice').get('pending') or {}).get('attempt','').endswith('-a2'))
            c.cycle(node,'twice');c.wait_for(lambda:len(c.ran(node,'twice-a'))==2)
        else:c.run_until(node,'twice',lambda:c.frame(node,'twice').get('phase')=='halted')
    for _ in range(3):c.cycle(node,'twice')
    return {'classification':'X','snapshots':frames,'after':c.frame(node,'twice'),'runs_a':len(c.ran(node,'twice-a')),'observed':'僅自動重派一次，同request不同attempt，第二次未知停住'}
def timeout_kill(c):
    node=c.mknode('a');t=probe_table('tk',a={'patience':1,'on_timeout':'kill'},gate=True);c.set_tasks(node,[c.install(node,'tk',t)]);pathlib.Path(c.jd(node,'tk','gate-a')).touch()
    c.run_until(node,'tk',lambda:c.frame(node,'tk').get('phase')=='halted')
    ctl=read_json(os.path.join(c.slot(node,'step-tk-a'),'ctl.json'));fr=c.frame(node,'tk')
    assert fr['halt']['kind']=='timeout' and ctl['run']==c.birth(node,'step-tk-a')['run']
    for _ in range(3):c.cycle(node,'tk')
    return {'classification':'pass','frame':fr,'kill_request':ctl,'exit':c.exit_of(node,'step-tk-a'),'results':c.results(node,'tk','a'),'observed':'timeout kill 帶run，停住且不假報結果'}
def close_active(c):
    node=c.mknode('a');t=probe_table('cl',gate=True);c.set_tasks(node,[c.install(node,'cl',t)]);pathlib.Path(c.jd(node,'cl','gate-a')).touch();c.cycle(node,'cl')
    r=c.step_cli(node,'close','jobs/cl');return {'classification':'pass','returncode':r.returncode,'stderr':r.stderr,'phase':c.frame(node,'cl')['phase']}
def checker(c):
    node=c.mknode('a');cases=[];good=probe_table('check')
    mutations=[('scalar_step',lambda t:t['steps'].__setitem__('a',3)),('list_target',lambda t:t['steps']['a'].__setitem__('ok',[])),('list_start',lambda t:t.__setitem__('start',[])),('list_result_condition',lambda t:t['steps'].__setitem__('w',{'wait':{'result.ok':[]},'then':'done'})),('global_kill_wait',lambda t:(t.__setitem__('start','w'),t.__setitem__('options',{'on_timeout':'kill'}),t['steps'].__setitem__('w',{'wait':{'exists':'never'},'patience':1,'then':'done'}))),('step_wake_override',lambda t:t['steps']['a'].__setitem__('wake',True))]
    for name,mut in mutations:
        t=copy.deepcopy(good);mut(t);p=os.path.join(node,name+'.json');write_json(p,t);r=c.step_cli(node,'check',p)
        cases.append({'case':name,'input':t,'returncode':r.returncode,'stdout':r.stdout,'stderr_tail':r.stderr[-1200:]})
    for item in cases:
        diagnostics=json.loads(item['stdout'])
        assert not item['stderr_tail'], item
        assert item['returncode']==(0 if item['case']=='step_wake_override' else 1), item
        assert isinstance(diagnostics,list), item
    return {'classification':'pass','cases':cases,'observed':'A4-04、A4-07檢查器反例消失，壞型別均JSON診斷'}
def malformed_frame(c):
    node=c.mknode('a');t=probe_table('badfr');c.set_tasks(node,[c.install(node,'badfr',t)]);c.cycle(node,'badfr');p=c.jd(node,'badfr','frame.json');fr=c.frame(node,'badfr');del fr['pc'];write_json(p,fr)
    # Deliberate internal-file tamper, explicitly M (never claim this as B).
    r=subprocess.run([sys.executable,'-c',"import sys;sys.path.insert(0,sys.argv[1]);import aos7_step;aos7_step.run_pass('jobs/badfr')",str(TOP/'packs/step')],cwd=node,capture_output=True,text=True,timeout=10)
    return {'classification':'M','returncode':r.returncode,'stderr_tail':r.stderr[-700:],'observed':'手改frame刪pc後KeyError，誤用、不處理；此案不列要修'}
for name,fn in [('initial_wait_patience',initial_wait),('entered_wait_patience',entered_wait),('delayed_intent_unknown',delayed_intent),('resend_at_most_once',resend_twice),('timeout_kill',timeout_kill),('close_active_refused',close_active),('checker_edges',checker),('malformed_frame_misuse',malformed_frame)]:scenario(name,fn)
ps=subprocess.run(['ps','-eo','pid,ppid,stat,args'],capture_output=True,text=True,check=True).stdout
left=[ln for ln in ps.splitlines() if any(root in ln for root in roots)]
emit('cleanup',{'roots':roots,'roots_remaining':[r for r in roots if os.path.exists(r)],'ps_root_matches':left})
