#!/usr/bin/env python3
"""Read-only QA of production sources; own /tmp roots cleaned via CoreCase."""
import os, sys, json, time, unittest, subprocess, pathlib, importlib.util, errno
from unittest import mock
HERE=pathlib.Path(__file__).resolve().parent
TOP=HERE.parents[3]
sys.path.insert(0,str(TOP/'tests'))
from base import DaemonCase, write_json, read_json
from _matrix import MatrixCase, rec_argv, env, fault, alive
import aos7_control, aos7_ctl, aos7_task
sys.path.insert(0,str(TOP/'modules/once_retry'))
import retry_lost
sys.path.insert(0,str(TOP/'modules/audit'))
import aos7_audit
RESULTS={}; ROOTS=[]
class Cases(MatrixCase):
    def setUp(self):
        super().setUp(); ROOTS.append(self.root)
    def save(self,name,value): RESULTS[name]=value
    def test_control_late_same_id(self):
        n=self.mknode('a',[{'name':'w','mode':'keep','argv':rec_argv('w')}])
        self.itick(); self.wait_ended(n,'w',1); self.itock()
        first=aos7_control.restart(n,'w',req_id='same-request')
        self.itick(); self.wait_ended(n,'w',2); self.itock()
        done=aos7_control.restart(n,'w',req_id='same-request')
        self.assertEqual(done['once'],'done')
        self.itick(); self.wait_ended(n,'w',3); self.itock()
        before=self.birth(n,'w'); resend=aos7_control.restart(n,'w',req_id='same-request')
        self.save('control_late_same_id',{'first':first,'at_run2':done,'birth_after_keep':before,'at_run3':resend,'queued':self.tasks(n),'runs':self.ran(n,'w'),'classification':'G: completion-id lifetime unspecified after ordinary keep replacement'})
        self.assertEqual(resend['once'],'added')
    def test_control_same_id_concurrent_snapshot(self):
        n=self.mknode('a',[{'name':'w','mode':'keep','argv':rec_argv('w')}])
        self.itick(); self.wait_ended(n,'w',1); self.itock()
        # Disable ordinary keep before race: runs 2 and 3 must both come from restart.
        self.set_tasks(n,[{'name':'w','mode':'keep','enabled':False,'argv':rec_argv('w')}])
        original=aos7_control.edit_json; trace=[]
        def schedule(path,fn,**kw):
            # A has read run1 birth and is about to take tasks lock. B finishes
            # the identical request while A is descheduled; no core file edits.
            with mock.patch.object(aos7_control,'edit_json',original):
                b=aos7_control.restart(n,'w',req_id='concurrent')
                self.itick(); self.wait_ended(n,'w',2); self.itock()
            trace.append({'B':b,'birth_before_A_lock':self.birth(n,'w')})
            return original(path,fn,**kw)
        with mock.patch.object(aos7_control,'edit_json',schedule):
            a=aos7_control.restart(n,'w',req_id='concurrent')
        queued=self.tasks(n)
        self.assertEqual(len([i for i in queued if i.get('mode')=='once']),1)
        self.itick(); self.wait_ended(n,'w',3); self.itock()
        b3=self.birth(n,'w')
        self.assertEqual(b3.get('x',{}).get('req_id'),'concurrent')
        self.save('control_same_id_concurrent_snapshot',{'scheduling_hook_hits':len(trace),'trace':trace,'A':a,'queued':queued,'third_birth':b3,'runs':self.ran(n,'w'),'classification':'B: concurrent same-id request queues duplicate after other caller completed; no documented single-caller precondition'})
    def test_control_stale_kill_replay(self):
        n=self.mknode('a',[{'name':'w','mode':'keep','argv':rec_argv('w')}])
        self.itick(); self.wait_ended(n,'w',1)
        req=aos7_control.restart(n,'w',req_id='stale-kill')
        original_remove=os.remove; hits=[]
        def deny(p,*args,**kw):
            if str(p).endswith('/ctl.json'):
                hits.append(str(p)); raise PermissionError(errno.EACCES,'injected ctl unlink',str(p))
            return original_remove(p,*args,**kw)
        sums=[]
        with mock.patch('os.remove',deny):
            sums.append(self.itock())
            for run in (2,3,4):
                self.itick(); self.wait_ended(n,'w',run); sums.append(self.itock())
        receipt=read_json(os.path.join(self.slot(n,'w'),'ctl-done.json'))
        self.assertGreaterEqual(len(hits),4); self.assertEqual(self.ran(n,'w'),['1','2','3','4'])
        self.assertEqual(receipt['run'],1); self.assertFalse(receipt['result']['ok'])
        self.save('control_stale_kill_replay',{'unlink_fault_hits':len(hits),'runs':self.ran(n,'w'),'receipt':receipt,'ctl_summaries':[s.get('ctl') for s in sums],'birth':self.birth(n,'w'),'classification':'X handled; old run kill never hits replacements'})
    def test_control_reload_and_g1(self):
        n=self.mknode('a',[{'name':'w','mode':'keep','argv':['sleep','60']}])
        self.itick(); pj=self.wait_pid(n,'w')
        self.set_tasks(n,[{'name':'w','mode':'keep','argv':['sleep','59'],'max_live':'bad'}])
        bad=aos7_control.restart(n,'w',reload=True)
        self.assertFalse(bad['ok']); self.assertFalse(os.path.exists(os.path.join(self.slot(n,'w'),'ctl.json')))
        self.set_tasks(n,[{'name':'w','mode':'keep','argv':['sleep','59'],'x':{'tag':'new'}}])
        with fault('open:*/tasks.json:EIO') as f:
            refusal=aos7_control.restart(n,'w'); hit=f.hits()
        self.assertFalse(refusal['ok']); self.assertTrue(alive(pj['pid']))
        good=aos7_control.restart(n,'w',reload=True,req_id='reload')
        self.itock(); self.itick(); self.wait_pid(n,'w')
        self.assertEqual(self.birth(n,'w')['argv'],['sleep','59'])
        self.save('control_reload_and_g1',{'invalid_reload':bad,'EIO_refusal':refusal,'EIO_hits':hit,'valid_reload':good,'birth':self.birth(n,'w')})
    def test_once_retry_pending(self):
        n=self.mknode('a',[{'name':'w','mode':'once','argv':rec_argv('w'),'x':{'retry_lost':True}}])
        self.crash('aos7-tick','after-birth')
        with env(AOS7_INCOMPLETE='tick'): self.itock()
        sums=[]
        for _ in range(4):
            self.itick(); sums.append(self.itock())
            if retry_lost.candidates(n): break
        cs=retry_lost.candidates(n); self.assertEqual(len(cs),1)
        with fault('open:*/tasks.json:EIO') as f:
            pending=retry_lost.scan(n); hits=f.hits()
        self.assertEqual(len(pending),1)
        left=retry_lost.scan(n,pending); self.assertEqual(left,{})
        retry_lost.scan(n,pending)
        queued=self.tasks(n); self.assertEqual(len(queued),1)
        self.itick(); self.wait_ended(n,'w'); self.itock()
        self.assertEqual(len(self.ran(n,'w')),1)
        self.save('once_retry_pending',{'lost':[e for s in sums for e in s.get('ended',[])],'fault_hits':hits,'pending_ids':list(pending),'queued_count':len(queued),'runs':self.ran(n,'w')})
    def test_once_retry_started_lost(self):
        n=self.mknode('a',[{'name':'w','mode':'once','argv':rec_argv('w',keep=True),'x':{'retry_lost':True}}])
        self.itick(); self.wait_pid(n,'w'); self.wait_for(lambda:self.ran(n,'w'))
        pids=self.kill_runner_and_task(n,'w'); s=self.itock()
        self.assertFalse(any(e.get('never_started') for e in s['ended'])); self.assertEqual(retry_lost.scan(n),{})
        self.assertFalse(self.tasks(n))
        self.save('once_retry_started_lost',{'killed_pids':pids,'ended':s['ended'],'queued':self.tasks(n),'runs':self.ran(n,'w')})
    def test_tools_unknown_and_encoding(self):
        n=self.mknode('a',[{'name':'w','mode':'keep','argv':['sleep','60']}]); self.itick(); self.wait_pid(n,'w')
        errors=[]
        with fault('open:*/birth.json:EIO') as f:
            try: aos7_ctl.task_ctl(self.slot(n,'w'))
            except Exception as e: errors.append(str(e))
            hit=f.hits()
        self.assertTrue(errors); self.assertFalse(os.path.exists(os.path.join(self.slot(n,'w'),'ctl.json')))
        original=pathlib.Path(n,'.aos/tasks.json').read_bytes()
        with fault('open:*/tasks.json:EACCES') as f:
            try:aos7_ctl.add_items(n,[{'name':'x','argv':['true']}])
            except Exception as e:errors.append(str(e))
            hit2=f.hits()
        self.assertEqual(original,pathlib.Path(n,'.aos/tasks.json').read_bytes())
        names={v:aos7_ctl.fixed_name('cli','pause','a',v) for v in ['甲','乙','A/B','A+B','x?','x!','a'*300+'1','a'*300+'2']}
        self.assertEqual(len(set(names.values())),len(names))
        self.save('tools_unknown_and_encoding',{'errors':errors,'fault_hits':[hit,hit2],'names':names,'table_unchanged':True})
    def test_diag_unknown_readonly(self):
        n=self.mknode('a',[{'name':'w','mode':'keep','argv':['sleep','60']}]); self.itick(); self.wait_pid(n,'w'); self.itock()
        def snap():
            return {str(p.relative_to(self.root)):(p.stat().st_size,p.stat().st_mtime_ns,p.read_bytes().hex()) for p in pathlib.Path(self.root).rglob('*') if p.is_file()}
        before=snap()
        with fault('open:*/birth.json:EIO') as f:
            p=subprocess.run([sys.executable,str(TOP/'modules/diag/aos7-diag'),self.root,'a'],capture_output=True,text=True,timeout=10); hit=f.hits()
        out=json.loads(p.stdout); self.assertEqual(p.returncode,0); self.assertEqual(before,snap()); self.assertTrue(out['nodes']['a']['uncertain'])
        self.save('diag_unknown_readonly',{'fault_hits':hit,'files_unchanged':True,'report':out})
class AuditCase(DaemonCase):
    def setUp(self):super().setUp(); ROOTS.append(self.root)
    def test_registration_refresh(self):
        audit=str(TOP/'modules/audit/aos7-audit')
        code="import pathlib,time; p=pathlib.Path; p('ready').write_text('1');\nwhile not p('release').exists(): time.sleep(.02)\np('nested/result.txt').write_text('data')\np('own.txt').write_text('ok')"
        a=self.mknode('a',[{'name':'w','mode':'once','argv':[sys.executable,audit,'--',sys.executable,'-c',code]}],interval_ms=100)
        nested=self.mknode('a/nested',[])
        d=self.start_daemon(register=['a']); self.wait_for(lambda:pathlib.Path(a,'ready').exists())
        receipt=self.wait_receipt(self.ctl('register','a/nested'))
        self.assertTrue(receipt['result']['ok'])
        pathlib.Path(a,'release').write_text('go'); self.wait_for(lambda:pathlib.Path(nested,'result.txt').exists())
        scan=aos7_audit.scan(self.root)
        log=pathlib.Path(self.slot(a,'w'),'writes.jsonl')
        records=[json.loads(x) for x in log.read_text().splitlines()]
        hit=[r for r in records if r['path'].endswith('/nested/result.txt')]
        self.assertEqual(len(hit),1)
        RESULTS['audit_registration_refresh']={'registration':receipt,'write':hit,'scan':scan,'classification':'B if dynamic registration included in audit boundary guarantee; audit failed to flag caller misuse'}
        self.assertTrue(hit[0]['ok']) # observed regression: cached registrations mark this allowed
        self.stop_daemon(d)
class RecordResult(unittest.TextTestResult):
    def startTest(self,t):self.started=time.monotonic(); super().startTest(t)
    def stopTest(self,t):
        RESULTS.setdefault('_cases',[]).append({'test':t.id(),'seconds':round(time.monotonic()-self.started,3),'failed':any(x[0] is t for x in self.failures+self.errors)})
        super().stopTest(t)
if __name__=='__main__':
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Cases),unittest.defaultTestLoader.loadTestsFromTestCase(AuditCase)])
    # Selected subd contract checks, production tests remain untouched.
    spec=importlib.util.spec_from_file_location('subd_probe',TOP/'modules/subd/tests/test_subd_ownership.py'); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    for name in ['test_owner_blocks_and_stop_refused','test_allow_stop_writes_stopped_and_parent_does_not_restart']:
        suite.addTest(m.TestOwnership(name))
    suite.addTest(m.TestSubrootChecks('test_subroot_rules'))
    original_setup=m.SubCase.setUp
    def tracked_setup(case):
        original_setup(case); ROOTS.append(case.root)
    m.SubCase.setUp=tracked_setup
    r=unittest.TextTestRunner(verbosity=2,resultclass=RecordResult).run(suite)
    RESULTS['_summary']={'ran':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'own_roots_removed':all(not os.path.exists(p) for p in ROOTS),'own_roots':ROOTS}
    live=[]
    for p in pathlib.Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:envb=(p/'environ').read_bytes()
        except OSError:continue
        if any(('AOS7_ROOT='+root).encode() in envb for root in ROOTS):live.append(int(p.name))
    RESULTS['_summary']['live_pids_after_cleanup']=live
    (HERE/'modules-results.json').write_text(json.dumps(RESULTS,ensure_ascii=False,indent=2)+'\n')
    sys.exit(not r.wasSuccessful())
