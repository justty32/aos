"""Focused astra-3 probes. Does not modify product files; all nodes live in own /tmp root."""
import json, os, pathlib, signal, subprocess, sys, tempfile, time, traceback
from unittest import mock
OUT=pathlib.Path(__file__).resolve().parent
REPO=OUT.parents[4]
TOP=REPO/'proto7-2'
sys.path.insert(0,str(TOP/'tests'))
from _matrix import MatrixCase, fault, rec_argv, alive
from aos7_fs import read_json, write_json
import aos7_mount
RUNROOT=tempfile.mkdtemp(prefix='astra3-core-probes-')
tempfile.tempdir=RUNROOT
rows=[]
def run(name,fn):
    c=MatrixCase(); c.setUp(); begin=time.monotonic()
    try:
        row=dict(name=name,observations=fn(c),probe_assertions='passed')
    except Exception:
        row=dict(name=name,probe_assertions='failed',traceback=traceback.format_exc())
    finally:
        c.doCleanups()
    row.update(elapsed_s=round(time.monotonic()-begin,3),case_root=c.root,case_root_removed=not os.path.exists(c.root))
    rows.append(row); (OUT/'core-probes.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    print(json.dumps(row,ensure_ascii=False),flush=True)
def mount_case(c,birth_fault=False):
    node=c.mknode('a',[dict(name='job',mode='keep',argv=rec_argv('job',keep=True))])
    c.itick(); pid=c.wait_pid(node,'job')['pid']; c.itock()
    slot=c.slot(node,'job'); req=os.path.join(slot,'mount-req','data.json')
    write_json(req,dict(name='data',path='data',why='valid request'))
    before=c.birth(node,'job'); hits=[]
    if birth_fault:
        original=aos7_mount.read_json
        def timed_read(path,*a,**kw):
            if str(path).endswith('/birth.json'):
                with fault('open:*/birth.json:EIO') as f:
                    val=original(path,*a,**kw); hits.extend(f.records()); return val
            return original(path,*a,**kw)
        with mock.patch.object(aos7_mount,'read_json',side_effect=timed_read): out=c.itick()
    else:
        with fault('open:*/mount-req/data.json:EIO') as f:
            out=c.itick(); hits=f.records()
    after=c.birth(node,'job'); receipt=read_json(os.path.join(slot,'mount-done','data.json'))
    obs=dict(fault_hits=hits,birth_before=before,birth_after=after,request_retained=os.path.exists(req),receipt=receipt,tick=out,task_alive=alive(pid),mount_exists=os.path.islink(os.path.join(slot,'mnt','data')))
    c.assertGreater(len(hits),0)
    if birth_fault:
        c.assertNotIn('run',after); c.assertTrue(receipt['result']['ok']); c.assertTrue(obs['task_alive'])
        obs['post_fault_view']=dict(c.view(node,'job',2))
        obs['post_fault_tock']=c.itock()
        c.assertEqual(obs['post_fault_view']['state'],'unknown')
        c.assertTrue(obs['post_fault_tock'].get('errors'))
        obs['classification']='B'; obs['contract']='卡 2.3；spec 0 U 保留現狀及 4.5 加掛'
    else:
        c.assertFalse(obs['request_retained']); c.assertEqual(receipt['result']['msg'],'not a JSON object'); c.assertFalse(obs['mount_exists'])
        obs['classification']='B'; obs['contract']='卡 2.3；spec 0 U 請求留著下一圈再看'
    return obs
run('mount_request_EIO_consumed',lambda c:mount_case(c,False))
run('mount_birth_EIO_clobbered',lambda c:mount_case(c,True))
def until_crash(c,point):
    node=c.mknode('a',[dict(name='o',mode='once',argv=rec_argv('o'),until_round=1)])
    p=subprocess.run([sys.executable,str(TOP/'bin/aos7-tick'),c.root,'a'],env=dict(os.environ,AOS7_TEST_CRASH=point),capture_output=True,text=True,timeout=20)
    c.assertEqual(p.returncode,-signal.SIGKILL)
    pending_before=c.tasks(node); born=c.birth(node,'o'); c.itock()
    starts=[]; ended=[]
    for i in range(4):
        starts.extend(c.itick()['started']); ended.extend(c.itock()['ended'])
    c.assertEqual(starts,[]); c.assertEqual(c.ran(node,'o'),[])
    if point=='after-launch': c.assertEqual(len(c.tasks(node)),1)
    else: c.assertEqual(c.tasks(node),[]); c.assertTrue(any(e.get('never_started') for e in ended))
    return dict(crash_point=point,returncode=p.returncode,until_round=1,pending_before=pending_before,birth_before=born,recovery_started=starts,external_runs=c.ran(node,'o'),final_tasks=c.tasks(node),ended=ended,classification='X handled to contract')
for point in ['after-launch','after-birth']:run('until_round_'+point,lambda c,p=point:until_crash(c,p))
def until_busy(c):
    node=c.mknode('a',[dict(name='job',mode='keep',argv=rec_argv('job',keep=True),until_round=1)])
    c.itick(); pj=c.wait_pid(node,'job'); c.itock()
    c.set_tasks(node,[dict(name='job',mode='once',slot='job',argv=rec_argv('new'),until_round=2)])
    out=c.itick(); c.assertEqual(out['started'],[]); c.itock()
    write_json(os.path.join(c.slot(node,'job'),'ctl.json'),dict(op='kill',run=1,by='probe'))
    starts=[]
    for _ in range(3): starts.extend(c.itick()['started']); c.itock()
    c.assertEqual(starts,[]); c.assertEqual(c.ran(node,'new'),[]); c.assertEqual(len(c.tasks(node)),1)
    return dict(expired_once_pending=c.tasks(node),starts=starts,new_external_runs=c.ran(node,'new'),old_runs=c.ran(node,'job'),round=c.round_json(node)['round'])
run('until_round_busy_then_expired',until_busy)
def until_keep(c):
    node=c.mknode('a',[dict(name='k',mode='keep',argv=rec_argv('k',keep=True),until_round=1)])
    c.itick(); pj=c.wait_pid(node,'k'); c.itock(); starts=[]
    for _ in range(4): starts.extend(c.itick()['started']); c.itock(); c.assertTrue(alive(pj['pid']))
    c.assertEqual(starts,[])
    write_json(os.path.join(c.slot(node,'k'),'ctl.json'),dict(op='kill',run=1,by='probe'))
    for _ in range(3): starts.extend(c.itick()['started']); c.itock()
    c.assertEqual(starts,[]); c.assertEqual(c.ran(node,'k'),['1'])
    return dict(alive_through_round=5,post_expiry_started=starts,runs=c.ran(node,'k'),last_round=c.round_json(node)['round'])
run('until_round_keep_alive_then_ended',until_keep)
# Verify no live matching processes, then remove only this invocation's private temporary root.
ps=subprocess.run(['ps','-eo','pid,ppid,stat,args'],capture_output=True,text=True).stdout
matching=[x for x in ps.splitlines() if RUNROOT in x]
cleanup=dict(root=RUNROOT,remaining=os.listdir(RUNROOT),ps_matching=matching,case_roots_removed=all(x['case_root_removed'] for x in rows))
if not os.listdir(RUNROOT): os.rmdir(RUNROOT)
cleanup['root_removed']=not os.path.exists(RUNROOT)
(OUT/'core-cleanup.json').write_text(json.dumps(cleanup,ensure_ascii=False,indent=2))
assert not matching and cleanup['root_removed'], cleanup
assert all(x['probe_assertions']=='passed' for x in rows)
