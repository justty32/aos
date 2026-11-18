# 此檔以獨立 transient scope 驗證 daemon 的可選 cgroup 份額與整格回收。
import errno
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import ENV, Fixture, dc, read, until, write


class ScopedDaemon(Fixture):
    def __init__(self, case, mode='auto', wrapper=''):
        self.unit = 'aos-limits-test-' + uuid.uuid4().hex + '.scope'
        super().__init__(self.unit)
        self.case = case
        self.scope = None
        self.pid = None
        case.addCleanup(self.close)
        self.log = open(self.root / 'daemon.log', 'a')
        self.err = open(self.root / 'daemon.err', 'a')
        cfg = {'interval_ms': 20, 'procs': {}}
        if mode is not None:
            cfg['cgroup'] = mode
        write(self.config, cfg)
        launch = self.root / 'launch.sh'
        launch.write_text('#!/bin/sh\n# 此腳本記錄測試 PID 並建立圖紙指定的隔離前提。\n'
                          'echo $$ > daemon.pid\n'
                          'S=/sys/fs/cgroup$(cut -d: -f3 /proc/self/cgroup)\n'
                          'echo "$S" > scope.path\n' + wrapper + '\n'
                          'exec aos-daemon --enable-logs "$1"\n')
        launch.chmod(0o755)
        print('transient_unit=' + self.unit, flush=True)
        self.proc = subprocess.Popen(['systemd-run', '--user', '--scope', '--collect', '-p',
            'TimeoutStopSec=2s', '-p', 'Delegate=yes', '--unit=' + self.unit, '--',
            str(launch), str(self.config)], cwd=self.root, env=dict(ENV, AOS_STACK=str(self.stack)),
            stdout=self.log, stderr=self.err)
        (self.root / 'runner.pid').write_text(str(self.proc.pid))
        until(lambda: (self.root / 'scope.path').exists(), timeout=10)
        self.scope = Path((self.root / 'scope.path').read_text().strip())
        self.pid = int((self.root / 'daemon.pid').read_text())

    def ready(self):
        until(lambda: read(self.stack / 'procs_state.json', {}).get('pid') == self.pid, timeout=10)
        return self

    def close(self):
        if self.pid is not None and Path(f'/proc/{self.pid}').exists():
            cwd = Path(f'/proc/{self.pid}/cwd').readlink()
            assert cwd == self.root, (self.pid, cwd)
            os.kill(self.pid, signal.SIGTERM)
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                pass
        if self.scope is not None and (self.scope / 'cgroup.kill').exists():
            try:
                (self.scope / 'cgroup.kill').write_text('1')
            except OSError as e:     # the scope emptied and is being removed between exists() and write: ENODEV/ENOENT
                if e.errno not in (errno.ENODEV, errno.ENOENT):
                    raise
        subprocess.run(['systemctl', '--user', 'stop', self.unit], env=ENV, capture_output=True)
        subprocess.run(['systemctl', '--user', 'reset-failed', self.unit], env=ENV, capture_output=True)
        if self.proc is not None:
            self.proc.wait(timeout=8)
        def gone():
            p = subprocess.run(['systemctl', '--user', 'list-units', '--all', '--no-legend', self.unit],
                               env=ENV, capture_output=True, text=True, check=True)
            return self.unit not in p.stdout
        until(gone, timeout=8)
        print('transient_unit_gone=' + self.unit, flush=True)
        self.log.close()
        self.err.close()

    def job(self, text, limits=None):
        script = self.root / 'job.sh'
        script.write_text('#!/bin/sh\n# 此腳本執行單一有界的測試工作。\n' + text + '\n')
        script.chmod(0o755)
        spec = {'exec': str(script)}
        if limits is not None:
            spec['limits'] = limits
        result = dc.ask(str(self.stack), {'procs_added': {'job': spec}})
        self.case.assertTrue(result['applied'], result)
        return script

    def state(self):
        return read(self.stack / 'state.json', {})


class CgroupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = subprocess.run(['systemctl', '--user', 'show-environment'], env=ENV,
                           capture_output=True, text=True)
        if p.returncode:
            raise unittest.SkipTest('systemd user manager unavailable: ' + p.stderr.strip())

    def fixture(self, mode='auto', wrapper=''):
        return ScopedDaemon(self, mode, wrapper)

    def test_off_ignored(self):
        f = self.fixture(None).ready()
        self.assertEqual(f.state()['cgroup'], 'off')
        before = sorted(p.name for p in f.scope.iterdir() if p.is_dir())
        f.job('sleep 0.2; exit 3', {'mem_total_mb': 256})
        r = f.phase('stopped')
        self.assertEqual(r['limits_ignored'], ['mem_total_mb'])
        self.assertNotIn('cgroup', r)
        self.assertIn('job: mem_total_mb need cgroup (cgroup is off), ignored',
                      (f.root / 'daemon.err').read_text())
        self.assertEqual(before, sorted(p.name for p in f.scope.iterdir() if p.is_dir()))
        self.assertFalse((f.scope / 'daemon').exists())
        self.assertFalse((f.scope / 'procs').exists())

    def test_memory_and_recreate(self):
        f = self.fixture().ready()
        self.assertEqual(f.state()['cgroup'], str(f.scope))
        f.job('exec python3 -c "x = bytearray(512 * 1024 * 1024); import time; time.sleep(5)"',
              {'mem_total_mb': 128})
        r = f.phase('stopped')
        self.assertEqual(r['limit_hit'], 'mem')
        self.assertEqual(r['signal'], 9)
        self.assertEqual(r['code'], 137)
        self.assertNotIn('limit_suspect', r)
        (f.root / 'job.sh').write_text('#!/bin/sh\n# 此腳本等待第二輪觀測。\nexec sleep 30\n')
        f.ctl('start', 'job')
        f.phase('running')
        until(lambda: 'oom_kill 0' in (Path(r['cgroup']) / 'memory.events').read_text())

    def test_pids(self):
        f = self.fixture().ready()
        code = ('import os,time; n=0\n'
                'for i in range(40):\n'
                ' try: p=os.fork()\n'
                ' except BlockingIOError: os._exit(3 if n <= 19 else 4)\n'
                ' if p == 0: time.sleep(30); os._exit(0)\n'
                ' n += 1\n'
                'os._exit(4)')
        script = f.root / 'fork.py'
        script.write_text('# 此檔只嘗試四十次 fork 並保留可辨認的退出碼。\n' + code)
        f.job('exec python3 ' + str(script), {'procs_total': 20})
        r = f.phase('stopped')
        self.assertEqual(r['code'], 3)
        self.assertEqual(r['limit_hit'], 'procs')
        self.assertNotIn('limit_suspect', r)
        events = Path(r['cgroup']) / 'cgroup.events'
        until(lambda: not events.exists() or 'populated 0' in events.read_text(), timeout=5)

    def test_missing_controllers_auto(self):
        f = self.fixture('auto', 'mkdir "$S/noctrl"\necho $$ > "$S/noctrl/cgroup.procs"').ready()
        self.assertEqual(f.state()['cgroup'], 'none (controllers lack memory/pids)')
        self.assertIn('cgroup: none (controllers lack memory/pids)', (f.root / 'daemon.err').read_text())

    def test_missing_controllers_on(self):
        f = self.fixture('on', 'mkdir "$S/noctrl"\necho $$ > "$S/noctrl/cgroup.procs"')
        self.assertEqual(f.proc.wait(timeout=10), 1)
        self.assertIn('CfgBad cgroup on: controllers lack memory/pids', (f.root / 'daemon.err').read_text())

    def test_busy_rollback(self):
        f = self.fixture('auto', 'sleep 60 &\necho $! > blocker.pid').ready()
        self.assertTrue(f.state()['cgroup'].startswith('none ('))
        self.assertIn('cgroup: none (', (f.root / 'daemon.err').read_text())
        self.assertFalse((f.scope / 'daemon').exists())
        self.assertFalse((f.scope / 'procs').exists())

    def test_sleep_kills_setsid(self):
        self.check_setsid(False)

    def test_grace_kills_setsid(self):
        self.check_setsid(True)

    def check_setsid(self, stubborn):
        f = self.fixture().ready()
        tail = "trap '' TERM\nwhile :; do sleep 1; done" if stubborn else 'exec sleep 999'
        f.job(('trap \'\' TERM\n' if stubborn else '') +
              'setsid sleep 999 &\necho $! > escaped.pid\n' + tail)
        r = f.phase('running')
        until(lambda: (f.root / 'escaped.pid').exists())
        escaped = int((f.root / 'escaped.pid').read_text())
        f.ctl('sleep', 'job')
        until(lambda: f.row() and f.row()['phase'] == 'sleeping', timeout=15 if stubborn else 5)
        def absent(pid):
            p = Path(f'/proc/{pid}/stat')
            return not p.exists() or p.read_text().rsplit(')', 1)[1].split()[0] == 'Z'
        until(lambda: absent(escaped) and absent(r['pid']), timeout=2)

    def test_rlimit_and_membership(self):
        f = self.fixture().ready()
        f.job('touch ready; exec sleep 30', {'cpu_s': 30, 'mem_total_mb': 256})
        until(lambda: (f.root / 'ready').exists())
        r = f.phase('running')
        self.assertEqual(Path(f'/proc/{r["pid"]}/cgroup').read_text().strip(),
                         '0::' + r['cgroup'].removeprefix('/sys/fs/cgroup'))
        cpu = next(s for s in Path(f'/proc/{r["pid"]}/limits').read_text().splitlines()
                   if s.startswith('Max cpu time'))
        self.assertEqual(cpu.split()[3:5], ['30', '31'])


if __name__ == '__main__':
    unittest.main()
