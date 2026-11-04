#!/usr/bin/env python3
"""Replay with PYTHONDONTWRITEBYTECODE=1 python3 <this file>; no LLM, local shell tasks only."""
import os, sys, json, tempfile, pathlib, time, unittest, io, traceback, importlib.util
HERE=pathlib.Path(__file__).resolve().parent
TOP=HERE.parents[2]
os.environ['PYTHONDONTWRITEBYTECODE']='1'
tempfile.tempdir=str(HERE)
sys.path.insert(0,str(TOP/'tests'))
from base import DaemonCase, CoreCase, MODULES
from aos7_fs import read_json, write_json, read_jsonl
import aos7_task

def size(path):
    out={'files':0,'bytes':0,'directories':0}
    for p,ds,fs in os.walk(path):
        out['directories']+=len(ds)
        for f in fs:
            try:
                st=os.stat(os.path.join(p,f),follow_symlinks=False)
                out['files']+=1;out['bytes']+=st.st_size
            except FileNotFoundError: pass
    return out

def save(name,value):
    (HERE/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def long_run(history):
    c=DaemonCase();c.setUp();root=c.root;t0=time.monotonic()
    result={'history':history,'target_rounds':500,'samples':[]}
    try:
        tasks=[{'name':'keep','mode':'keep','argv':['sleep','3600'],'max_live':2},
               {'name':'each_busy','mode':'each','argv':['sleep','3600'],'max_live':3},
               {'name':'each_fast','mode':'each','argv':['true'],'max_live':2},
               {'name':'keep_fast','mode':'keep','argv':['true'],'max_live':2}]
        if history: tasks.append({'name':'history','mode':'keep','argv':[sys.executable,str(TOP/'modules'/'history.py'),'--status','--max-lines','50']})
        node=c.mknode('a',tasks,interval_ms=0)
        c.ctl('pause','a',by='measure')
        p=c.start_daemon(register=['a'])
        c.wait_for(lambda:c.nstat().get('phase')=='paused',20)
        previous_goal=0
        for goal in [10,50,100,250,400,500]:
            c.wait_receipt(c.ctl('resume','a','--rounds',str(goal-previous_goal),by='measure'))
            c.wait_for(lambda:c.node_round()>=goal and c.nstat().get('phase')=='paused',180,'round stalled')
            time.sleep(.15)  # runners finished, no tick clearing/recreating files during measurement
            previous_goal=goal
            result['samples'].append({'observed_round':c.node_round(),'aos':size(pathlib.Path(node)/'.aos'),'aosd':size(pathlib.Path(root)/'.aosd')})
            print('progress',history,c.node_round(),flush=True)
        c.wait_for(lambda:c.nstat().get('phase')=='paused',30)
        time.sleep(.15)
        result['final_round']=c.round_json(node)
        result['stable_final']={'aos':size(pathlib.Path(node)/'.aos'),'aosd':size(pathlib.Path(root)/'.aosd')}
        result['slots']=sorted(os.listdir(pathlib.Path(node)/'.aos'/'tasks'))
        result['history_exists']=(pathlib.Path(node)/'history').exists()
        if history:
            rows=read_jsonl(pathlib.Path(node)/'history'/'a.jsonl')
            result['history']={'node_rows':len(rows),'rounds':[x.get('round') for x in rows if 'round' in x], 'gaps':[x['gap'] for x in rows if 'gap' in x], 'event_rows':len(read_jsonl(pathlib.Path(node)/'history'/'daemon-events.jsonl')), 'size':size(pathlib.Path(node)/'history')}
        result['seconds']=round(time.monotonic()-t0,3)
        c.stop_daemon(p)
    finally:
        c.doCleanups()
        result['cleanup_root_removed']=not os.path.exists(root)
    return result

def targeted():
    suite=unittest.defaultTestLoader.loadTestsFromNames(['test_ctl.TestCtl','test_ctl.TestMounts','test_tick_tock.TestSlotRemoval','test_tick_tock.TestSlotsAndRuns.test_infra_files_cleared_task_files_kept'])
    stream=io.StringIO();out=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    return {'tests':out.testsRun,'failures':len(out.failures),'errors':len(out.errors),'output':stream.getvalue()}

def design_probes():
    c=CoreCase();c.setUp();root=c.root;out={}
    try:
        n=c.mknode('a',[{'name':'job','argv':['true']}]);c.itick();c.wait_ended(n,'job',1)
        sd=pathlib.Path(c.slot(n,'job'))
        write_json(sd/'state.json',{'previous':True});write_json(sd/'usage.json',{'tokens':100})
        c.itock();before={'run':c.birth(n,'job')['run'],'usage':read_json(sd/'usage.json'),'state':read_json(sd/'state.json')}
        c.set_tasks(n,[]);c.itick();c.itock();deleted=not sd.exists()
        c.set_tasks(n,[{'name':'job','argv':['true']}]);c.itick();c.wait_ended(n,'job',3)
        write_json(sd/'usage.json',{'tokens':150});c.itock()
        after={'run':c.birth(n,'job')['run'],'usage':read_json(sd/'usage.json'),'state':read_json(sd/'state.json')}
        out['slot_recreated']={'before':before,'deleted':deleted,'after':after,'kernel_rule_simulation':{'observations':[100,150],'spec8_retired':0,'spec8_total':150,'true_usage':250,'conclusion':'No observed decrease: slot-name+max counter cannot distinguish new lifetime. kernel is absent; this is design simulation, not an implemented kernel bug.'}}
        # Call the shipped history implementation: bounded node stream but --status path not trimmed.
        spec=importlib.util.spec_from_file_location('aos_history',TOP/'modules'/'history.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
        import argparse
        args=argparse.Namespace(src=['a'],out=str(pathlib.Path(n)/'history'),max_lines=3,status=True)
        me={'root':root,'node_id':'a'};st={}
        for rnd in range(1,11):
            write_json(pathlib.Path(n)/'.aos'/'last-round.json',{'round':rnd})
            write_json(pathlib.Path(root)/'.aosd'/'status.json',{'last_event':{'event':'test','serial':rnd}})
            h.once(me,args,lambda _:None,st)
        out['history_max_lines']={'max_lines':3,'node_rows':len(read_jsonl(pathlib.Path(args.out)/'a.jsonl')),'event_rows':len(read_jsonl(pathlib.Path(args.out)/'daemon-events.jsonl'))}
        # First sample cannot report missed prefix; after seen cursor it reports explicit gap.
        st={};args.out=str(pathlib.Path(n)/'history_gap');args.max_lines=0;args.status=False
        write_json(pathlib.Path(n)/'.aos'/'last-round.json',{'round':100});h.once(me,args,lambda _:None,st)
        write_json(pathlib.Path(n)/'.aos'/'last-round.json',{'round':110});h.once(me,args,lambda _:None,st)
        out['history_gap']={'rows':read_jsonl(pathlib.Path(args.out)/'a.jsonl'),'initial_rounds_1_to_99_explicit_gap':False}
    finally:
        c.doCleanups();out['cleanup_root_removed']=not os.path.exists(root)
    return out

if __name__=='__main__':
    save('slots-design-rerun', design_probes())
