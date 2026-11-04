#!/usr/bin/env python3
"""獨立 daemon 邊界探針；從任意目錄執行，僅在本證據資料夾建立並清掉暫存空間。
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-1-infra-evidence/daemon-probes.py
"""
import datetime, errno, json, os, pathlib, shutil, signal, subprocess, sys, tempfile, time, unittest
from unittest.mock import patch
HERE = pathlib.Path(__file__).resolve().parent
TOP = HERE.parents[2]
sys.path.insert(0, str(TOP / 'tests'))
sys.path.insert(0, str(TOP / 'lib'))
from base import DaemonCase, SLEEP
from aos7_fs import read_json, write_json
import aos7_daemon, aos7_proc
import aos7_tick

RESULT = {}
def sec(a, b):
    return round((datetime.datetime.fromisoformat(b)-datetime.datetime.fromisoformat(a)).total_seconds(), 3)

class Probe(DaemonCase):
    def rec(self, key, **values):
        RESULT[key] = values

    def test_unverified_holder_long_path_diagnostic(self):
        node=self.mknode('a',action_timeout_s=0.3)
        mark=self.root+'/held'
        code=('import sys,time;sys.path.insert(0,%r);import aos7_fs\n'
              'with aos7_fs.action_lock(%r,%r):\n open(%r,"w").write("held")\n time.sleep(60)\n')
        holder=subprocess.Popen([sys.executable,'-c',code % (str(TOP/'lib'),self.root,node,mark)])
        self.procs.append(holder)
        self.wait_for(lambda:os.path.exists(mark))
        self.start_daemon(register=['a'])
        self.wait_for(lambda:(self.nstat().get('last_event') or {}).get('ev')=='stale-holder-unverified')
        samples=[]
        for _ in range(5):
            time.sleep(0.22)
            samples.append(self.nstat())
        self.rec('unverified_holder_diagnostic',holder_alive=holder.poll() is None,samples=samples,
                 prefix_visible=any('stale-holder-unverified' in (s.get('last_error') or {}).get('err','') for s in samples))

    def test_fd_write_tick_move_and_runner_move(self):
        node=self.mknode('a',[{'name':'s','argv':['true']}])
        moved=self.root+'/moved'
        def move(point):
            if point=='tick-opened':
                os.rename(node,moved)
        with patch.object(aos7_tick,'test_point',move):
            tick=self.itick()
        first=dict(tick=tick,original_recreated=os.path.exists(node),
                   moved_birth=self.birth(moved,'s'),moved_exit=self.exit_of(moved,'s'))
        node=self.mknode('b',[{'name':'s','argv':['sleep','0.35']}])
        self.tick('b')
        self.wait_pid(node,'s')
        moved2=self.root+'/moved2'
        os.rename(node,moved2)
        self.wait_ended(moved2,'s',1)
        self.rec('fd_mid_move',tick_move=first,runner_move=dict(original_recreated=os.path.exists(node),
                 moved_exit=self.exit_of(moved2,'s')))

    def test_generation_rejects_stale_action(self):
        node=self.mknode('a',[{'name':'s','argv':['true']}])
        write_json(self.root+'/.aosd/gen.json',{'gen':9})
        tick=self.tick(env={'AOS7_GEN':'8'})
        tock=self.tock(env={'AOS7_GEN':'8'})
        self.rec('stale_generation',tick=tick,tock=tock,
                 round_created=os.path.exists(node+'/.aos/round.json'),birth=self.birth(node,'s'))

    def test_symlink_same_inode(self):
        node = self.mknode('a', [{'name':'s','mode':'keep','argv':SLEEP}], interval_ms=200)
        self.start_daemon(register=['a'])
        pid = self.wait_pid(node, 's')['pid']
        self.wait_round(2)
        before = self.node_round()
        os.rename(node, self.root+'/moved')
        os.symlink('moved', node)
        time.sleep(0.8)
        self.rec('symlink_same_inode', phase=self.nstat().get('phase'), before_round=before,
                 after_round=self.node_round(), task_still_alive=aos7_proc.pid_alive(pid),
                 node_is_symlink=os.path.islink(node), status=self.nstat())

    def test_symlink_different_target_outside_root(self):
        node = self.mknode('a', interval_ms=150)
        target = self.root+'-target'
        os.makedirs(target)
        self.addCleanup(shutil.rmtree, target, True)
        self.start_daemon(register=['a'])
        self.wait_round(2)
        os.rename(node, self.root+'/moved')
        os.symlink(target, node)
        self.wait_for(lambda: os.path.exists(target+'/.aos/round.json'), 5,
                      'outside target did not receive round.json')
        time.sleep(0.3)
        self.rec('symlink_outside_root', phase=self.nstat().get('phase'),
                 wrote_target_aos=os.path.isdir(target+'/.aos'), target_round=read_json(target+'/.aos/round.json'))

    def test_stat_io_errors_keep_timeline(self):
        node = self.mknode('a')
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        d.registry = {'a': {}}
        class Fake:
            last_error = None
        tl = Fake()
        d.timelines['a'] = tl
        orig = os.stat
        rows = []
        for error in [errno.EACCES, errno.EIO, errno.ESTALE]:
            def stat(p, *a, **kw):
                if p == node:
                    raise OSError(error, os.strerror(error))
                return orig(p, *a, **kw)
            with patch.object(aos7_daemon.os, 'stat', stat):
                d.check_nodes()
            rows.append(dict(errno=error, preserved=d.timelines.get('a') is tl,
                             missing='a' in d.missing, reaping='a' in d.reapers, error=tl.last_error))
        self.rec('stat_io_fault_injection', cases=rows)

    def test_actual_eacces_recovery(self):
        parent = self.root+'/locked'
        node = self.mknode('locked/a', [{'name':'s','mode':'keep','argv':SLEEP}], interval_ms=200)
        self.addCleanup(os.chmod, parent, 0o700)
        self.start_daemon(register=['locked/a'])
        pid = self.wait_pid(node, 's')['pid']
        self.wait_round(2, 'locked/a')
        os.chmod(parent, 0)
        time.sleep(0.7)
        fault = self.nstat('locked/a')
        alive = aos7_proc.pid_alive(pid)
        os.chmod(parent, 0o700)
        self.wait_round((fault.get('round') or 0)+2, 'locked/a')
        self.rec('actual_eacces', uid=os.geteuid(), status_during=fault, task_alive_during=alive,
                 status_recovered=self.nstat('locked/a'), same_task_pid=self.wait_pid(node,'s')['pid']==pid)

    def test_timing_modes_and_wake(self):
        for early in [False, True]:
            nid = 'early' if early else 'fixed'
            self.mknode(nid, [{'name':'s','argv':['true']}], interval_ms=1800, early=early)
        self.start_daemon(register=['early','fixed'])
        self.wait_for(lambda: self.nstat('early').get('phase')=='idle')
        self.wait_for(lambda: self.nstat('fixed').get('phase')=='running')
        fixed_before = self.node_round('fixed')
        early_before = self.node_round('early')
        t0 = time.monotonic()
        self.wait_receipt(self.ctl('wake', 'fixed'))
        self.wait_receipt(self.ctl('wake', 'early'))
        self.wait_round(early_before+1, 'early', timeout=1)
        wake_elapsed = round(time.monotonic()-t0, 3)
        fixed_unchanged = self.node_round('fixed') == fixed_before
        self.wait_for(lambda: self.last_round(self.root+'/fixed').get('round')==1, 4)
        fixed = self.last_round(self.root+'/fixed')
        early = self.last_round(self.root+'/early')
        self.rec('timing_modes', interval_ms=1800, wake_to_early_next_s=wake_elapsed,
                 fixed_unchanged_at_early_wake=fixed_unchanged,
                 fixed_round_s=sec(fixed['tick_at'],fixed['tock_at']), fixed_early=fixed['early'],
                 early_round_s=sec(early['tick_at'],early['tock_at']), early_early=early['early'])

    def test_wake_during_early_active_round(self):
        self.mknode('a',[{'name':'s','argv':['sleep','0.7']}],interval_ms=2500,early=True)
        self.start_daemon(register=['a'])
        self.wait_for(lambda: self.nstat().get('phase')=='running')
        t0=time.monotonic()
        self.wait_receipt(self.ctl('wake','a'))
        self.wait_round(2,timeout=3)
        elapsed=round(time.monotonic()-t0,3)
        self.rec('wake_in_active_early_round', interval_ms=2500, wake_to_next_tick_s=elapsed,
                 skipped_remaining_idle=elapsed<1.6)

    def test_pause_owner_and_restart(self):
        self.mknode('a',interval_ms=150)
        p=self.start_daemon(register=['a'])
        self.wait_round(2)
        for owner in ['A','B']:
            self.wait_receipt(self.ctl('pause','a','--owner',owner))
        self.wait_for(lambda:self.nstat().get('phase')=='paused')
        self.wait_receipt(self.ctl('resume','a','--owner','A'))
        after_a=self.nstat()
        self.stop_daemon(p)
        p=self.start_daemon()
        self.wait_for(lambda:self.nstat().get('phase')=='paused')
        after_restart=self.nstat()
        n=self.node_round()
        t0=time.monotonic()
        self.wait_receipt(self.ctl('resume','a','--owner','B'))
        self.wait_round(n+1)
        self.rec('pause_owners',after_A_resume=after_a,after_restart=after_restart,
                 B_resume_to_next_tick_s=round(time.monotonic()-t0,3))

    def test_rounds_other_owner_overwrites(self):
        self.mknode('a',interval_ms=120)
        self.ctl('pause','a','--owner','A')
        self.ctl('pause','a','--owner','B')
        self.start_daemon(register=['a'])
        self.wait_for(lambda:self.nstat().get('phase')=='paused')
        self.wait_receipt(self.ctl('resume','a','--owner','A','--rounds','1'))
        a_step=self.nstat()
        self.wait_receipt(self.ctl('resume','a','--owner','B','--rounds','3'))
        self.wait_for(lambda:self.nstat().get('phase')=='paused' and self.node_round()>=3)
        self.rec('rounds_owner_collision',after_A_resume_1=a_step,final=self.nstat(),
                 expected_A_pause_after_one_missing='A' not in self.nstat().get('paused_by',[]))

if __name__=='__main__':
    transient=tempfile.mkdtemp(prefix='daemon-temp-',dir=HERE)
    tempfile.tempdir=transient
    started=time.monotonic()
    try:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(Probe)
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        RESULT['_suite']={'tests':result.testsRun,'failures':[(str(t),e) for t,e in result.failures],
                          'errors':[(str(t),e) for t,e in result.errors],
                          'elapsed_s':round(time.monotonic()-started,3)}
    finally:
        shutil.rmtree(transient,ignore_errors=True)
        remaining=[]
        for entry in pathlib.Path('/proc').iterdir():
            if not entry.name.isdigit() or int(entry.name)==os.getpid():
                continue
            try:
                env=(entry/'environ').read_bytes()
                cmd=(entry/'cmdline').read_bytes()
                if transient.encode() in env or transient.encode() in cmd:
                    remaining.append(int(entry.name))
            except OSError:
                pass
        RESULT['_cleanup']={'transient_removed':not os.path.exists(transient),'remaining_pids':remaining}
        (HERE/'daemon-probes.json').write_text(json.dumps(RESULT,ensure_ascii=False,indent=2)+'\n')
