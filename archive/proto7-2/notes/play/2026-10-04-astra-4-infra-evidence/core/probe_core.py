#!/usr/bin/env python3
"""astra-4: adapt astra-3 core/module scenarios, assert repaired contracts.
Run from repository root; only writes evidence beside this script and own /tmp roots.
No production source changes. Faults model X, never rewrite core-owned lifecycle files.
"""
import errno, json, os, pathlib, signal, subprocess, sys, tempfile, time, traceback
from unittest import mock
OUT=pathlib.Path(__file__).resolve().parent
TOP=OUT.parents[3]
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
sys.path.insert(0,str(TOP/'tests'))
from _matrix import MatrixCase, fault, rec_argv, alive, env
from base import DaemonCase, read_json, write_json
import aos7_mount, aos7_control, aos7_tock
from aos7_fs import locked
sys.path.insert(0,str(TOP/'modules/once_retry'))
import retry_lost
sys.path.insert(0,str(TOP/'modules/audit'))
import aos7_audit
RUNROOT=tempfile.mkdtemp(prefix='astra4-core-')
tempfile.tempdir=RUNROOT
ROWS=[]; ROOTS=[]
def run(name, fn, cls=MatrixCase):
    c=cls(); c.setUp(); ROOTS.append(c.root); begin=time.monotonic()
    original_set_tasks=c.set_tasks
    def locked_set_tasks(node,tasks,**top):
        with locked(os.path.join(node,'.aos/tasks.json'),1): original_set_tasks(node,tasks,**top)
    c.set_tasks=locked_set_tasks
    try: row=dict(name=name,observations=fn(c),status='passed')
    except Exception: row=dict(name=name,status='failed',traceback=traceback.format_exc())
    finally: c.doCleanups()
    row.update(seconds=round(time.monotonic()-begin,3),root=c.root,root_removed=not os.path.exists(c.root))
    ROWS.append(row); (OUT/'results.json').write_text(json.dumps(ROWS,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(row,ensure_ascii=False),flush=True)

def mount(c, target, code):
    n=c.mknode('a',[dict(name='job',mode='keep',argv=rec_argv('job',keep=True))]); c.itick(); pid=c.wait_pid(n,'job')['pid']; c.itock()
    slot=pathlib.Path(c.slot(n,'job')); req=slot/'mount-req/data.json'; receipt=slot/'mount-done/data.json'
    write_json(str(req),dict(name='data',path='data',why='valid request'))
    before=(slot/'birth.json').read_bytes(); hits=[]
    if target=='birth':
        original=aos7_mount.fact
        def timed(path,*a,**kw):
            if str(path).endswith('/birth.json'):
                with fault('open:*/birth.json:'+code) as f:
                    val=original(path,*a,**kw); hits.extend(f.records()); return val
            return original(path,*a,**kw)
        with mock.patch.object(aos7_mount,'fact',side_effect=timed): tick=c.itick()
    else:
        with fault('open:*/mount-req/data.json:'+code) as f:
            tick=c.itick(); hits=f.records()
    blocked=dict(request_retained=req.exists(),receipt_exists=receipt.exists(),birth_unchanged=before==(slot/'birth.json').read_bytes(),mount_exists=(slot/'mnt/data').is_symlink(),task_alive=alive(pid))
    assert hits and blocked==dict(request_retained=True,receipt_exists=False,birth_unchanged=True,mount_exists=False,task_alive=True),blocked
    tick_state=c.round_json(n)
    assert any(m.get('unknown') for m in tick_state['mounts']),tick_state
    c.itock(); recovered=c.itick(); receipt_value=read_json(str(receipt)); c.itock()
    assert receipt_value['result']['ok'] and not req.exists() and (slot/'mnt/data').is_symlink()
    return dict(target=target,errno=code,fault_hits=hits,blocked=blocked,tick=tick,round_state=tick_state,recovery_tick=recovered,receipt=receipt_value,verdict='A4-01 修好；X 走 U 留現狀')

for target in ('request','birth'):
    for code in ('EIO','EACCES','ESTALE'): run('A4-01_'+target+'_'+code,lambda c,t=target,e=code:mount(c,t,e))

def ctl_concurrent(c):
    n=c.mknode('a',[dict(name='w',mode='keep',argv=rec_argv('w'))]); c.itick(); c.wait_ended(n,'w',1); c.itock()
    c.set_tasks(n,[dict(name='w',mode='keep',enabled=False,argv=rec_argv('w'))])
    original=aos7_control.edit_json; trace=[]
    def schedule(path,fn,**kw):
        with mock.patch.object(aos7_control,'edit_json',original):
            b=aos7_control.restart(n,'w',req_id='concurrent'); c.itick(); c.wait_ended(n,'w',2); c.itock()
        trace.append(dict(B=b,birth_before_A_lock=c.birth(n,'w')))
        return original(path,fn,**kw)
    with mock.patch.object(aos7_control,'edit_json',schedule): a=aos7_control.restart(n,'w',req_id='concurrent')
    queued=c.tasks(n); tick=c.itick(); c.itock()
    assert len(trace)==1 and a['once']=='done' and not [i for i in queued if i.get('mode')=='once']
    assert c.ran(n,'w')==['1','2'] and not tick['started']
    return dict(trace=trace,A=a,queued=queued,next_tick=tick,runs=c.ran(n,'w'),verdict='A4-02 修好；只一個 restart run')
run('A4-02_control_concurrent',ctl_concurrent)

def ctl_lifetime(c):
    n=c.mknode('a',[dict(name='w',mode='keep',argv=rec_argv('w'))]); c.itick(); c.wait_ended(n,'w',1); c.itock()
    first=aos7_control.restart(n,'w',req_id='same'); c.itick(); c.wait_ended(n,'w',2); c.itock()
    done=aos7_control.restart(n,'w',req_id='same'); c.itick(); c.wait_ended(n,'w',3); c.itock()
    birth=c.birth(n,'w'); resend=aos7_control.restart(n,'w',req_id='same')
    assert first['once']=='added' and done['once']=='done' and resend['once']=='added'
    return dict(first=first,at_run2=done,birth_run3=birth,at_run3=resend,verdict='A4-06 修好（文件）；行為未變且符合明定去重期限，不列 bug')
run('A4-06_control_lifetime',ctl_lifetime)

def audit_refresh(c):
    audit=str(TOP/'modules/audit/aos7-audit')
    code="import pathlib,time; p=pathlib.Path; p('ready').write_text('1');\nwhile not p('release').exists(): time.sleep(.02)\np('nested/result.txt').write_text('data')\np('own.txt').write_text('ok')"
    n=c.mknode('a',[dict(name='w',mode='once',argv=[sys.executable,audit,'--',sys.executable,'-c',code])],interval_ms=500)
    nested=c.mknode('a/nested',[]); d=c.start_daemon(register=['a']); c.wait_for(lambda:pathlib.Path(n,'ready').exists())
    receipt=c.wait_receipt(c.ctl('register','a/nested')); assert receipt['result']['ok']
    pathlib.Path(n,'release').write_text('go'); c.wait_for(lambda:pathlib.Path(n,'own.txt').exists())
    log=pathlib.Path(c.slot(n,'w'),'writes.jsonl'); records=[json.loads(x) for x in log.read_text().splitlines()]
    hit=[r for r in records if r['path'].endswith('/nested/result.txt')]; own=[r for r in records if r['path'].endswith('/own.txt')]
    scan=aos7_audit.scan(c.root); assert len(hit)==1 and not hit[0]['ok'] and own[0]['ok']
    assert any(r['path'].endswith('/nested/result.txt') for _,r in scan['bad']),scan
    c.stop_daemon(d)
    return dict(receipt=receipt,nested_write=hit,own_write=own,scan=scan,verdict='A4-05 修好；受測任務越界是 M，但 audit 正確標出')
run('A4-05_audit_refresh',audit_refresh,DaemonCase)

def once_crash(c,point):
    n=c.mknode('a',[dict(name='o',mode='once',argv=rec_argv('o'))]); rc=c.crash('aos7-tick',point)
    pending=c.tasks(n); birth=c.birth(n,'o'); assert pending[0]['launch']['run']==birth['run']==1
    if point=='before-once-delete': c.wait_ended(n,'o',1)
    first=c.itock(); nexttick=c.itick(); pending_after=c.tasks(n); second=c.itock()
    more=[]
    for _ in range(3): more.append(c.itick()); c.itock()
    runs=c.ran(n,'o'); assert pending_after==[] and nexttick['started']==[] and all(not x['started'] for x in more)
    assert runs==(['1'] if point=='before-once-delete' else [])
    return dict(crash_point=point,returncode=rc,pending_before=pending,birth_before=birth,first_tock=first,recovery_tick=nexttick,pending_after=pending_after,second_tock=second,external_runs=runs,verdict='§4.4(a) 通過；birth 已存在、恢復移項且不多起。after-birth 允許最多一次為零次')
for point in ('after-birth','before-once-delete'):run('once_birth_before_remove_'+point,lambda c,p=point:once_crash(c,p))

def deletion(c,replay):
    n=c.mknode('a',[dict(name='o',mode='once',argv=rec_argv('o'))]); c.itick(); c.wait_ended(n,'o',1)
    if replay:
        rc=c.crash('aos7-tock','tock-after-finish'); crashed=dict(rc=rc,round=c.round_json(n),summary=c.last_round(n),exists=os.path.isdir(c.slot(n,'o')))
    else: crashed=None
    report=c.itock(); before_next=dict(exists=os.path.isdir(c.slot(n,'o')),exit=c.exit_of(n,'o')); assert before_next['exists']
    c.itick(); after_tick=os.path.isdir(c.slot(n,'o')); assert after_tick
    nexttock=c.itock(); after=os.path.isdir(c.slot(n,'o')); assert not after
    return dict(replay=replay,crashed=crashed,report=report,after_reporting_tock=before_next,after_next_tick=after_tick,next_tock=nexttock,exists_after_next_tock=after,verdict='§4.4(b)/§5.1 通過；報結束 tock 1 保留、tock 2 才刪，含同回合重播')
for replay in (False,True):run('ended_slot_deletion_'+str(replay),lambda c,r=replay:deletion(c,r))

def notify_fault(slots):
    original=aos7_tock.write_json; hits=[]
    def write(path,value,*args,**kw):
        if any(str(path).endswith('/'+s+'/tock.json') for s in slots):
            hits.append(dict(path=str(path),round=value.get('round'),errno='EIO')); raise OSError(errno.EIO,'probe notification write EIO',str(path))
        return original(path,value,*args,**kw)
    return mock.patch.object(aos7_tock,'write_json',write),hits

def history(c):
    n=c.mknode('a',[dict(name='history',mode='keep',argv=[sys.executable,str(TOP/'modules/history.py')])]); c.itick(); c.wait_pid(n,'history'); c.itock()
    output=pathlib.Path(n,'history/a.jsonl')
    def records():return [json.loads(x) for x in output.read_text().splitlines()] if output.exists() else []
    c.wait_for(lambda:any(r.get('round')==1 for r in records()))
    c.itick(); patch,hits=notify_fault(['history'])
    with patch: missed=c.itock()
    state=c.round_json(n); old=read_json(os.path.join(c.slot(n,'history'),'tock.json')); retry=c.itock()
    assert hits and state['notify_errors'] and old['round']==1
    assert read_json(os.path.join(c.slot(n,'history'),'tock.json'))['round']==1
    c.itick(); at_tick=read_json(os.path.join(c.slot(n,'history'),'tock.json')); assert at_tick['round']==1
    c.itock(); c.wait_for(lambda:any(r.get('round')==3 for r in records())); seen=records()
    assert [r.get('round') for r in seen if 'round' in r]==[1,3] and any(r.get('gap')==[2,2] for r in seen)
    return dict(hits=hits,failed_round=state,closed_tock_retry=retry,notification_before_next_tock=at_tick,history=seen,verdict='F47 合約內 X：history 正確記 gap [2,2]；不補送、不造歷史')
run('F47_history_lost_sample',history)

def replay_notify(c):
    n=c.mknode('a',[dict(name='w',mode='keep',argv=rec_argv('w',keep=True))]); c.itick(); c.wait_pid(n,'w')
    rc=c.crash('aos7-tock','tock-summary'); before=pathlib.Path(n,'.aos/last-round.json').read_bytes()
    out=c.itock(); note=read_json(os.path.join(c.slot(n,'w'),'tock.json'))
    assert rc==-9 and out['replayed'] and note['round']==1 and before==pathlib.Path(n,'.aos/last-round.json').read_bytes()
    return dict(crash_rc=rc,replay=out,notification=note,summary_unchanged=True,verdict='F47 同回合重播補寫仍正常')
run('F47_same_round_replay',replay_notify)

def retry_sample(c,miss):
    n=c.mknode('a',[dict(name='retry',mode='keep',argv=[sys.executable,str(TOP/'modules/once_retry/retry_lost.py')])]); c.itick(); c.wait_pid(n,'retry'); c.itock(); time.sleep(.15)
    c.set_tasks(n,c.tasks(n)+[dict(name='o',mode='once',argv=rec_argv('o'),x=dict(retry_lost=True))]); rc=c.crash('aos7-tick','after-birth'); c.itock()
    report=None; fault_hits=[]; failed_state=None
    for _ in range(5):
        c.itick(); patch,hits=notify_fault(['retry'])
        with patch: s=c.itock()
        fault_hits+=hits
        if any(e.get('never_started') and e.get('run')=='o#2' for e in s['ended']): report=s; failed_state=c.round_json(n); break
    assert report and fault_hits,dict(report=report,fault_hits=fault_hits)
    # A clean variant calls the module's public scan on the exact committed sample;
    # failure variant leaves the true keep task unnotified and observes next round.
    pending={}; table_hits=[]
    if not miss:
        with fault('open:*/tasks.json:EIO') as f: pending=retry_lost.scan(n); table_hits=f.records()
        assert pending
    c.itick(); later=c.itock()
    if not miss:
        left=retry_lost.scan(n,pending); assert left=={}
        c.itick(); c.wait_ended(n,'o'); c.itock(); c.wait_for(lambda:c.ran(n,'o'))
        assert len(c.ran(n,'o'))==1
    else:
        time.sleep(.2); assert not [i for i in c.tasks(n) if (i.get('x') or {}).get('retry_of')]
        assert c.ran(n,'o')==[] and not os.path.exists(c.slot(n,'o'))
    return dict(crash_rc=rc,notification_fault_hits=fault_hits,lost_report=report,failed_round_state=failed_state,next_summary=later,pending_ids=list(pending),table_fault_hits=table_hits,runs=c.ran(n,'o'),slot_exists=os.path.exists(c.slot(n,'o')),verdict=('F47 合約內 X：漏報 lost 的取樣依 README 明確退回最多一次' if miss else 'F47 合約內：已取樣但表 EIO 的 pending 保留、下次可加回'))
for miss in (True,False):run('F47_once_retry_'+('missed' if miss else 'pending'),lambda c,m=miss:retry_sample(c,m))

ps=subprocess.run(['ps','-eo','pid,ppid,stat,args'],capture_output=True,text=True,check=True).stdout
matching=[line for line in ps.splitlines() if RUNROOT in line]
live=[]
for p in pathlib.Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try: envb=(p/'environ').read_bytes()
    except OSError:continue
    if any(('AOS7_ROOT='+r).encode() in envb for r in ROOTS):live.append(int(p.name))
cleanup=dict(root=RUNROOT,case_roots_removed=all(not os.path.exists(r) for r in ROOTS),remaining=os.listdir(RUNROOT),ps_matching=matching,live_pids=live)
if not cleanup['remaining']:os.rmdir(RUNROOT)
cleanup['root_removed']=not os.path.exists(RUNROOT)
(OUT/'cleanup.json').write_text(json.dumps(cleanup,ensure_ascii=False,indent=2)+'\n')
assert not matching and not live and cleanup['root_removed'],cleanup
sys.exit(any(r['status']!='passed' for r in ROWS))
