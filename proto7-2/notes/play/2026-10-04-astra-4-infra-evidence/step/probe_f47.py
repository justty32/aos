#!/usr/bin/env python3
"""F47: real tick/tock and keep interpreter; inject EIO only at interpreter tock.json write."""
import json, os, pathlib, subprocess, sys, time, traceback
sys.dont_write_bytecode=True
HERE=pathlib.Path(__file__).resolve().parent
TOP=HERE.parents[3]
sys.path[:0]=[str(TOP/'packs/step/tests'),str(TOP/'packs/step'),str(TOP/'tests')]
from test_step import StepCase, probe_table
from unittest.mock import patch
import errno, aos7_tock
from aos7_fs import read_json
from run_comparison import clean
records=[]
def snap(c,node,job):
    return {'frame':c.frame(node,job),'round':c.round_json(node),
            'tock':read_json(os.path.join(c.slot(node,'step-'+job),'tock.json'))}
def blocked(c,node,job):
    hits=[]; original=aos7_tock.write_json
    def fail_write(path,value):
        if path.endswith('/step-'+job+'/tock.json'):
            hits.append({'operation':'write_json','errno':'EIO','path':path,'round':value['round']})
            raise OSError(errno.EIO,'astra4 injected notification write failure',path)
        return original(path,value)
    with patch.object(aos7_tock,'write_json',side_effect=fail_write):
        summary=c.itock()
    assert len(hits)==1, hits
    assert c.round_json(node)['notify_errors'][0]['slot']=='step-'+job
    return {'hits':hits,'summary':summary,**snap(c,node,job)}
def result_after_slot_deleted(c):
    node=c.mknode('a');job='f47result';table=probe_table(job)
    c.set_tasks(node,[c.install(node,job,table)])
    c.cycle(node,job)
    before=snap(c,node,job)
    first_pending=before['frame']['pending']
    missing=[]
    for _ in range(4):
        c.tick()
        if len(missing)==0:
            c.wait_for(lambda:len(c.results(node,job,'a'))==1)
            c.wait_ended(node,'step-'+job+'-a',c.birth(node,'step-'+job+'-a')['run'])
        missing.append(blocked(c,node,job))
        assert c.frame(node,job)['tock']==1
    slot_removed=not os.path.exists(c.slot(node,'step-'+job+'-a'))
    assert slot_removed
    assert len(c.results(node,job,'a'))==1
    same_closed=c.tock()
    assert same_closed.get('skipped')=='round already closed'
    assert c.frame(node,job)['tock']==1
    tick=c.tick()
    assert read_json(os.path.join(c.slot(node,'step-'+job),'tock.json'))['round']==1
    c.tock();c.wait_pass(node,job,tick['round'])
    resumed=snap(c,node,job)
    c.run_until(node,job,lambda:c.frame(node,job).get('phase')=='ended')
    final=c.frame(node,job)
    assert final['accepted']['a']['request']==first_pending['request']
    assert list(final['tries'].values())==[1,1]
    assert len(c.ran(node,job+'-a'))==1 and len(c.ran(node,job+'-b'))==1
    return {'classification':'pass/X','before':before,'failed_notifications':missing,'slot_removed_before_resume':slot_removed,
            'closed_replay':same_closed,'resumed':resumed,'final':final,'runs_a':len(c.ran(node,job+'-a')),'runs_b':len(c.ran(node,job+'-b')),
            'observation':'r2～r5通知各EIO一次不補；once槽已清但槽外結果保留，r6正常通知接回原attempt，不重派'}
def wait_elapsed(c):
    node=c.mknode('a');job='f47wait';table={'job':job,'start':'w','steps':{'w':{'wait':{'exists':'never'},'patience':2,'then':'done'},'done':{'end':'ok'}}}
    c.set_tasks(node,[c.install(node,job,table)]);c.cycle(node,job)
    before=snap(c,node,job);missing=[]
    for _ in range(3):
        c.tick();missing.append(blocked(c,node,job))
    assert c.frame(node,job)['since']==1 and c.frame(node,job)['phase']=='running'
    c.cycle(node,job)
    after=snap(c,node,job)
    assert after['frame']['halt']['kind']=='timeout' and after['frame']['halt']['round']==5
    return {'classification':'pass/X','before':before,'failed_notifications':missing,'after':after,
            'observation':'漏r2～r4通知；r5恢復即依本地回合差timeout，耐性不因漏通知而重設'}
for name,fn in [('durable_result_across_four_missed_tocks',result_after_slot_deleted),('wait_patience_after_three_missed_tocks',wait_elapsed)]:
    c=StepCase();c.setUp();rec={'probe':name}
    try:rec.update(fn(c))
    except Exception as e:rec.update(probe_error=repr(e),traceback=traceback.format_exc())
    finally:rec['cleanup']=clean(c)
    records.append(rec)
    (HERE/'f47-step.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    print(name,rec.get('probe_error','PASS'),flush=True)
assert all('probe_error' not in r for r in records)
