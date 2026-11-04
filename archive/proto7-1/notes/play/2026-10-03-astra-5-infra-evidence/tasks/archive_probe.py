#!/usr/bin/env python3
"""Offline Q3 probes. Hooks only pause readers at real file-operation boundaries.
Actual archival always runs unmodified aos7-tock in another process. No LLM.
"""
import json, os, pathlib, shutil, subprocess, sys, tempfile
from unittest.mock import patch
REPO = pathlib.Path.cwd()
sys.path.insert(0, str(REPO/'proto7-1/lib'))
import aos7_fs as fs, aos7_agent as agent, aos7_kernel as kernel
import aos7_kernel_rules as rules, aos7_task as task
OUT = pathlib.Path(__file__).resolve().parent


def fixture():
    root=pathlib.Path(tempfile.mkdtemp(prefix='astra5-tasks-archive-'))
    node=root/'n'; aos=node/'.aos'; old=aos/'tasks'/'worker-r1'; own=aos/'tasks'/'worker-r3'
    fs.write_json(str(aos/'timeline.json'), {'interval_ms':100,'keep_ended_rounds':0})
    fs.write_json(str(aos/'round.json'), {'round':3,'open':True,'started':[]})
    for d,rnd in [(old,1),(own,3)]:
        fs.write_json(str(d/'birth.json'), {'name':'worker','tid':d.name,'round':rnd})
    fs.write_json(str(old/'exit.json'), {'code':0})
    fs.write_json(str(old/'ended.json'), {'round':1})
    fs.write_json(str(old/'usage.json'), {'tokens':1234})
    fs.write_json(str(old/'state.json'), {'state':'act','round':2,'steps':9,'pc':4})
    fs.write_json(str(old/'kernel-state.json'), dict(rules.empty_state(),sentinel='inherited-state'))
    return root,node,aos,old,own


def archive(root):
    p=subprocess.run([sys.executable,str(REPO/'proto7-1/bin/aos7-tock'),str(root),'n'],capture_output=True,text=True,timeout=5)
    assert p.returncode==0,(p.returncode,p.stderr)
    return json.loads(p.stdout)


def race(kind):
    root,node,aos,old,own=fixture(); fired=[]
    env={'root':str(root),'node':str(node),'node_id':'n','task':str(own),'tid':own.name}
    result={'case':kind,'root':str(root),'method':'pause read just before opening selected old pathname; run actual aos7-tock process; resume read'}
    try:
        read=fs.read_json
        suffix={'agent':'state.json','kernel':'kernel-state.json','usage':'usage.json'}[kind]
        def hooked(path,*args,**kw):
            if str(path)==str(old/suffix) and not fired:
                fired.append(True); result['tock']=archive(root)
            return read(path,*args,**kw)
        if kind=='agent':
            result['before']=agent.load_state(env)
            with patch.object(agent,'read_json',hooked): result['during']=agent.load_state(env)
            result['after']=agent.load_state(env)
        elif kind=='kernel':
            result['before']=kernel.load_state(env)
            with patch.object(fs,'read_json',hooked): result['during']=kernel.load_state(env)
            result['after']=kernel.load_state(env)
        else:
            result['before']=rules.snapshot_node(str(aos))
            with patch.object(fs,'read_json',hooked): result['during']=rules.snapshot_node(str(aos))
            result['after']=rules.snapshot_node(str(aos))
        result['barrier_hit']=bool(fired)
        assert fired
    finally: shutil.rmtree(root)
    return result


def collisions():
    root,node,aos,old,own=fixture()
    try:
        first=archive(root)
        normal=task.new_tid(str(node),'worker',1)
        # Restore/import a historical directory with same tid into active storage;
        # this can arise in manual restore, not normal serialized tick allocation.
        shutil.copytree(aos/'tasks-old'/old.name,old)
        fs.write_json(str(old/'usage.json'), {'tokens':5678})
        fs.write_json(str(aos/'round.json'), {'round':4,'open':True,'started':[]})
        conflict=archive(root)
        return {'case':'archive-collision','normal_new_tid':normal,'first_tock':first,'conflict_tock':conflict,
            'active_usage':fs.read_json(str(old/'usage.json')),'archive_usage':fs.read_json(str(aos/'tasks-old'/old.name/'usage.json')),
            'active_still_present':old.exists(),'next_new_tid':task.new_tid(str(node),'worker',1)}
    finally: shutil.rmtree(root)


def open_fd():
    root,node,aos,old,own=fixture()
    try:
        with open(old/'state.json') as f:
            summary=archive(root)
            data=json.load(f)
        return {'case':'already-open-fd','tock':summary,'state_from_fd':data,'old_path_exists':(old/'state.json').exists()}
    finally: shutil.rmtree(root)

if __name__=='__main__':
    for result in [race('agent'),race('kernel'),race('usage'),collisions(),open_fd()]:
        (OUT/(result['case']+'-archive.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(result['case'],json.dumps(result.get('during',result),ensure_ascii=False))
