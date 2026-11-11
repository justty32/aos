# Check loop.json on_start / on_stop: run once before the first run and once on every way out (11-11 clock-hook).
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest

BIN = Path(__file__).resolve().parents[1] / 'bin' / 'aos-loop'
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}

LOG_SH = '#!/bin/sh\n# append one line: the name, the code and signal given to on_stop\necho "%s ${AOS_LOOP_CODE-unset} ${AOS_LOOP_SIGNAL-unset}" >> "$LOG"\n'


class OnStartStop(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-loop-onss-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))
        self.log = self.d / 'log.txt'
        self.env = dict(ENV, LOG=str(self.log), AOS_STACK=str(self.d / 'stack') + '/')
        (self.d / 'stack').mkdir()
        for name in ('start', 'stop'):
            self.script(name, LOG_SH % name)

    def script(self, name, text):
        p = self.d / name
        p.write_text(text)
        p.chmod(0o755)
        return str(p)

    def body(self, text):
        return self.script('body', '#!/bin/sh\n# test body\necho body >> "$LOG"\n' + text)

    def cfg(self, **kw):
        doc = {'exec': str(self.d / 'body'), 'on_start': str(self.d / 'start'), 'on_stop': str(self.d / 'stop'),
               'ctl': None, 'state': None, 'state_flux': None}
        doc.update(kw)
        p = self.d / 'loop.json'
        p.write_text(json.dumps(doc))
        return str(p)

    def lines(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def run_loop(self, cfg, timeout=15):
        p = subprocess.run([str(BIN), cfg], env=self.env, cwd=self.d, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stderr

    def test_max_runs_then_stop(self):
        self.body('exit 0\n')
        code, err = self.run_loop(self.cfg(max=2))
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(self.lines(), ['start unset unset', 'body', 'body', 'stop 0 '])

    def test_body_10_and_failure(self):
        self.body('exit 10\n')
        self.assertEqual(self.run_loop(self.cfg())[0], 0)
        self.assertEqual(self.lines()[-1], 'stop 0 ')
        self.log.unlink()
        self.body('exit 7\n')
        code, err = self.run_loop(self.cfg())
        self.assertEqual(code, 7)
        self.assertIn('RunFailed', err)
        self.assertEqual(self.lines(), ['start unset unset', 'body', 'stop 7 '])

    def test_sigterm_during_body(self):
        self.body('trap "exit 0" TERM\nsleep 30 & wait\n')
        p = subprocess.Popen([str(BIN), self.cfg()], env=self.env, cwd=self.d, stderr=subprocess.PIPE, text=True)
        end = time.monotonic() + 5
        while 'body' not in self.lines() and time.monotonic() < end:
            time.sleep(.02)
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(timeout=10), 143)
        p.stderr.close()
        self.assertEqual(self.lines()[-1], 'stop 143 15')

    def test_ctl_stop(self):
        self.body('sleep 0.05\n')
        cfg = self.cfg(ctl='ctl.json', interval_ms=50)
        p = subprocess.Popen([str(BIN), cfg], env=self.env, cwd=self.d, stderr=subprocess.PIPE, text=True)
        time.sleep(.3)
        (self.d / 'stack' / 'ctl.json').write_text('{"cmd": "stop", "seq": 1}\n')
        self.assertEqual(p.wait(timeout=10), 0)
        p.stderr.close()
        self.assertEqual(self.lines()[0], 'start unset unset')
        self.assertEqual(self.lines()[-1], 'stop 0 ')

    def test_failing_on_start_only_warns(self):
        self.script('start', '#!/bin/sh\n# fails\nexit 3\n')
        self.body('exit 10\n')
        code, err = self.run_loop(self.cfg())
        self.assertEqual(code, 0)
        self.assertIn('aos-loop: warning: on_start', err)
        self.assertIn('exited 3', err)
        self.assertEqual(self.lines(), ['body', 'stop 0 '])

    def test_on_stop_timeout(self):
        self.script('stop', '#!/bin/sh\n# hangs\nsleep 30\n')
        self.body('exit 10\n')
        t0 = time.monotonic()
        code, err = self.run_loop(self.cfg(on_timeout_ms=300))
        self.assertEqual(code, 0)
        self.assertLess(time.monotonic() - t0, 5)
        self.assertIn('did not finish in 300 ms', err)

    def test_inline_inst(self):
        self.body('exit 10\n')
        cfg = self.cfg(on_start={'argv': ['sh', '-c', 'echo inline $AOS_CO >> "$LOG"']}, on_stop=None)
        self.assertEqual(self.run_loop(cfg)[0], 0)
        self.assertEqual(self.lines(), ['inline /on_start', 'body'])

    def test_bad_timeout(self):
        self.body('exit 10\n')
        code, err = self.run_loop(self.cfg(on_timeout_ms=0))
        self.assertEqual(code, 1)
        self.assertIn('CfgBad on_timeout_ms', err)
        self.assertEqual(self.lines(), [])

    def test_sigkill_skips_on_stop(self):
        self.body('sleep 30\n')
        p = subprocess.Popen([str(BIN), self.cfg()], env=self.env, cwd=self.d, stderr=subprocess.DEVNULL)
        end = time.monotonic() + 5
        while 'body' not in self.lines() and time.monotonic() < end:
            time.sleep(.02)
        p.kill()
        p.wait(timeout=5)
        subprocess.run(['pkill', '-f', str(self.d / 'body')])
        self.assertEqual(self.lines(), ['start unset unset', 'body'])


if __name__ == '__main__':
    unittest.main()
