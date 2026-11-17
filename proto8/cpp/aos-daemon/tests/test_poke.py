# Verify daemon poke modes, prompt wakeups and pid identity guards with isolated fixtures.
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from support import ENV, PROTO, dc, read, until, write


class Poke(unittest.TestCase):
    # Allow busy CI hosts more than the target 300 ms, but far less than one normal round.
    WAKE_TIMEOUT = 1.0

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-poke-')
        self.addCleanup(self.tmp.cleanup)
        self.stack = Path(self.tmp.name)
        self.config = self.stack / 'daemon.json'
        self.state = self.stack / 'state.json'
        self.proc = None
        self.cli = PROTO / 'cmd' / 'aos-daemon-ctl' / 'bin' / 'aos-daemon-ctl'
        self.addCleanup(self.close)

    def start(self, body=False):
        cfg = {'interval_ms': 10000, 'procs': {}}
        if body:
            cfg['exec'] = [sys.executable, '-c',
                           'import os,pathlib; '
                           'p=pathlib.Path(os.environ["AOS_STACK"])/"runs.txt"; '
                           'p.open("a").write("run\\n")']
        write(self.config, cfg)
        self.log = open(self.stack / 'daemon.log', 'w')
        self.err = open(self.stack / 'daemon.err', 'w')
        self.proc = subprocess.Popen(['aos-daemon', '--enable-logs', str(self.config)],
                                     cwd=self.stack, env=dict(ENV, AOS_STACK=str(self.stack)),
                                     stdout=self.log, stderr=self.err)
        until(lambda: read(self.state, {}).get('pid') == self.proc.pid)
        until(lambda: read(self.stack / 'procs_state.json'))
        if body:
            until(lambda: self.runs() == 1 and read(self.state, {}).get('body_code') == 0)
        # The ctl echo is written after tend: this also proves the startup mailbox
        # pass and body have finished before tests place their pending letters.
        write(self.stack / 'ctl.json', {'cmd': 'resume', 'seq': 1})
        self.ctl('poke')
        until(lambda: read(self.stack / 'state_flux.json', {}).get('ctl_seq') == 1)
        return self

    def close(self):
        if self.proc is None:
            return
        try:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=5)
        finally:
            self.log.close()
            self.err.close()

    def ctl(self, *args, code=0):
        result = subprocess.run([str(self.cli), '--daemon', str(self.stack), *args],
                                env=ENV, text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, code, result.stderr)
        self.assertEqual(result.stdout, '')
        if code == 0:
            self.assertEqual(result.stderr, '')
        return result

    def rows(self):
        return read(self.stack / 'procs_state.json', {}).get('procs', {})

    def add_stopped_row(self):
        # A held row exercises reconcile without leaving a live child to clean up.
        write(self.stack / 'procs_ctl.json', {
            'procs_added': {'job': {'exec': ['/bin/true']}}, 'procs_stopped': ['job']})

    def runs(self):
        path = self.stack / 'runs.txt'
        return len(path.read_text().splitlines()) if path.exists() else 0

    def letter(self):
        name = dc.send(str(self.stack), {'ping': True}, direct=True)
        path = self.stack / 'procs_requests' / 'new' / name
        self.assertTrue(path.exists())
        return path

    def test_default_ctl_applies_table_promptly(self):
        self.start()
        self.add_stopped_row()
        started = time.monotonic()
        self.ctl('poke')
        until(lambda: 'job' in self.rows(), timeout=self.WAKE_TIMEOUT)
        self.assertLess(time.monotonic() - started, self.WAKE_TIMEOUT)
        self.assertEqual(self.rows()['job']['phase'], 'stopped')

    def test_mail_claims_letter_without_running_body(self):
        self.start(body=True)
        letter = self.letter()
        self.ctl('poke', '--mail')
        until(lambda: not letter.exists(), timeout=self.WAKE_TIMEOUT)
        self.assertEqual(self.runs(), 1)
        self.assertIsNone(self.proc.poll())

    def test_ctl_leaves_mail_and_body_alone(self):
        self.start(body=True)
        letter = self.letter()
        self.add_stopped_row()
        self.ctl('poke', '--ctl')
        until(lambda: 'job' in self.rows(), timeout=self.WAKE_TIMEOUT)
        self.assertTrue(letter.exists())
        self.assertEqual(self.runs(), 1)

    def test_all_forces_an_early_body_run_and_claims_mail(self):
        self.start(body=True)
        letter = self.letter()
        self.add_stopped_row()
        self.ctl('poke', '--all')
        until(lambda: self.runs() == 2, timeout=self.WAKE_TIMEOUT)
        until(lambda: not letter.exists(), timeout=self.WAKE_TIMEOUT)
        self.assertIn('job', self.rows())
        self.assertIsNone(self.proc.poll())

    def test_twenty_pokes_apply_ctl_without_restarting_the_proc(self):
        self.start()
        marker = self.stack / 'starts.txt'
        script = ('import pathlib,sys; '
                  'pathlib.Path(sys.argv[1]).open("a").write("start\\n"); sys.exit(7)')
        write(self.stack / 'procs_ctl.json', {
            'procs_added': {'job': {'exec': [sys.executable, '-c', script, str(marker)]}}})
        for _ in range(20):
            self.ctl('poke')
        until(lambda: marker.exists(), timeout=self.WAKE_TIMEOUT)
        # Reap the finished child even if all twenty requests arrived before it exited.
        def finished():
            row = self.rows().get('job', {})
            pid = row.get('pid')
            if row.get('phase') == 'stopped' or not pid:
                return row.get('phase') == 'stopped'
            try:
                return Path('/proc/%d/stat' % pid).read_text().rsplit(')', 1)[1].split()[0] == 'Z'
            except FileNotFoundError:
                return True
        until(finished, timeout=self.WAKE_TIMEOUT)
        self.ctl('poke')
        until(lambda: self.rows().get('job', {}).get('phase') == 'stopped',
              timeout=self.WAKE_TIMEOUT)
        self.assertEqual(list(self.rows()), ['job'])
        self.assertEqual(marker.read_text().splitlines(), ['start'])
        self.assertIsNone(self.proc.poll())

    def test_usr_signals_survive_and_ctl_stop_exits_zero(self):
        self.start()
        os.kill(self.proc.pid, signal.SIGUSR1)
        os.kill(self.proc.pid, signal.SIGUSR2)
        self.add_stopped_row()
        self.ctl('poke')
        until(lambda: 'job' in self.rows(), timeout=self.WAKE_TIMEOUT)
        self.assertIsNone(self.proc.poll())
        write(self.stack / 'ctl.json', {'cmd': 'stop', 'seq': 2})
        self.ctl('poke')
        self.assertEqual(self.proc.wait(timeout=5), 0)

    def test_reused_pid_is_rejected_without_signalling_sleep(self):
        self.start()
        original = read(self.state)
        # Avoid sharing the daemon's start tick on a fast host.
        time.sleep(.03)
        sleeper = subprocess.Popen(['sleep', '300'])
        try:
            ticks = int(Path('/proc/%d/stat' % sleeper.pid).read_text().rsplit(')', 1)[1].split()[19])
            self.assertNotEqual(ticks, original['started_at_ticks'])
            forged = dict(original, pid=sleeper.pid)
            write(self.state, forged)
            result = self.ctl('poke', code=1)
            self.assertIn('DaemonMissing', result.stderr)
            self.assertIsNone(sleeper.poll())
        finally:
            write(self.state, original)
            if sleeper.poll() is None:
                sleeper.terminate()
            sleeper.wait(timeout=5)

    def test_stopped_daemon_is_missing(self):
        self.start()
        write(self.stack / 'ctl.json', {'cmd': 'stop', 'seq': 2})
        self.ctl('poke')
        self.assertEqual(self.proc.wait(timeout=5), 0)
        self.assertIn('DaemonMissing', self.ctl('poke', code=1).stderr)

    def test_absent_poke_declaration_is_rejected(self):
        self.start()
        original = read(self.state)
        without = dict(original)
        without.pop('poke')
        try:
            write(self.state, without)
            self.assertIn('PokeFailed', self.ctl('poke', code=1).stderr)
            self.assertIsNone(self.proc.poll())
        finally:
            write(self.state, original)

    def test_flags_are_mutually_exclusive_and_take_no_arguments(self):
        for args in (('--ctl', '--mail'), ('--mail', '--all'), ('--ctl', '--all'),
                     ('--ctl', '--mail', '--all'), ('unexpected',)):
            with self.subTest(args=args):
                self.assertIn('ArgumentsBad', self.ctl('poke', *args, code=1).stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
