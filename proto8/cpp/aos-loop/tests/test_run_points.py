# Check loop.json on_before_run / on_after_run and their _if flag files (11-20 hook cut 5): order, exit codes, skip, ctl, signals, environment.
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest

BIN = Path(__file__).resolve().parents[3] / 'bin' / 'aos-loop'
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}

# 每格各記一行：名字、AOS_LOOP_RUNS、AOS_LOOP_RUN_CODE、AOS_LOOP_RUN_SIGNAL（沒設＝unset，空的＝空）
LOG_SH = '#!/bin/sh\n# append one line: the name and the run variables it sees\necho "%s ${AOS_LOOP_RUNS-unset} ${AOS_LOOP_RUN_CODE-unset} [${AOS_LOOP_RUN_SIGNAL-unset}]" >> "$LOG"\n%s'


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-loop-points-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))
        self.log = self.d / 'log.txt'
        self.stack = self.d / 'stack'
        self.stack.mkdir()
        self.env = dict(ENV, LOG=str(self.log), AOS_STACK=str(self.stack) + '/')
        self.point('before')
        self.point('after')
        self.point('stop')
        self.point('body')

    def point(self, name, tail=''):
        p = self.d / name
        p.write_text(LOG_SH % (name, tail))
        p.chmod(0o755)
        return str(p)

    def cfg(self, **kw):
        doc = {'exec': str(self.d / 'body'), 'on_before_run': str(self.d / 'before'), 'on_after_run': str(self.d / 'after'),
               'on_stop': str(self.d / 'stop'), 'ctl': None, 'state': None, 'state_flux': None}
        doc.update(kw)
        p = self.d / 'loop.json'
        p.write_text(json.dumps({k: v for k, v in doc.items() if v != 'omit'}))
        return str(p)

    def lines(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def names(self):
        return [line.split()[0] for line in self.lines()]

    def run_loop(self, cfg, timeout=15):
        p = subprocess.run([str(BIN), cfg], env=self.env, cwd=self.d, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stderr

    def wait_for(self, word, secs=5):
        end = time.monotonic() + secs
        while word not in self.names() and time.monotonic() < end:
            time.sleep(.02)
        return word in self.names()


class Order(Fixture):
    def test_before_body_after_and_environment(self):
        self.point('after', 'echo "ms ${AOS_LOOP_RUN_MS-unset}" >> "$LOG"\n')
        code, err = self.run_loop(self.cfg(max=2))
        self.assertEqual((code, err), (0, ''))
        lines = self.lines()
        for i in (3, 7):
            self.assertRegex(lines[i], r'^ms \d+$')
        self.assertEqual([line for i, line in enumerate(lines) if i not in (3, 7)],
                         ['before 1 unset [unset]', 'body unset unset [unset]',   # 身體看不到這幾個變數
                          'after 1 0 []',                                         # 沒被訊號停＝空字串
                          'before 2 unset [unset]', 'body unset unset [unset]', 'after 2 0 []',
                          'stop unset unset [unset]'])                            # on_stop 也看不到

    def test_body_10_still_fires_after_run_then_on_stop(self):
        self.point('body', 'exit 10\n')
        self.assertEqual(self.run_loop(self.cfg()), (0, ''))
        self.assertEqual(self.lines(), ['before 1 unset [unset]', 'body unset unset [unset]', 'after 1 10 []', 'stop unset unset [unset]'])

    def test_no_points_written(self):
        self.point('body', 'exit 10\n')
        self.assertEqual(self.run_loop(self.cfg(on_before_run='omit', on_after_run='omit')), (0, ''))
        self.assertEqual(self.names(), ['body', 'stop'])

    def test_inline_inst_and_its_timeout(self):
        self.point('body', 'exit 10\n')
        code, err = self.run_loop(self.cfg(on_before_run={'argv': ['sh', '-c', 'echo "inline $AOS_CO $AOS_LOOP_RUNS" >> "$LOG"']}))
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(self.lines()[0], 'inline /on_before_run 1')
        t0 = time.monotonic()
        code, err = self.run_loop(self.cfg(on_before_run={'argv': ['sleep', '30'], 'timeout_ms': 200}))
        self.assertLess(time.monotonic() - t0, 5)
        self.assertEqual(code, 143)
        self.assertIn('aos-loop: error: PointFailed run 1: on_before_run loop.json#/on_before_run exited 143', err)


class BeforeRun(Fixture):
    def test_10_skips_a_run_without_counting_it(self):
        # 第一次退 10，之後退 0：被跳過的不算 max、不發 after_run，下一次要等 interval_ms
        self.point('before', 'date +%%s%%N >> "%s"\nif [ ! -e "%s" ]; then touch "%s"; exit 10; fi\n' % (self.d / 'times', self.d / 'once', self.d / 'once'))
        code, err = self.run_loop(self.cfg(max=1, interval_ms=300))
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(self.names(), ['before', 'before', 'body', 'after', 'stop'])
        self.assertEqual(self.lines()[1], 'before 1 unset [unset]')   # 跳過後仍是第 1 次
        t = [int(x) for x in (self.d / 'times').read_text().split()]
        self.assertGreaterEqual((t[1] - t[0]) / 1e6, 250)

    def test_other_code_stops_and_on_stop_runs(self):
        self.point('before', 'exit 4\n')
        code, err = self.run_loop(self.cfg())
        self.assertEqual(code, 4)
        self.assertEqual(err.splitlines(), ['aos-loop: error: PointFailed run 1: on_before_run %s exited 4' % (self.d / 'before')])
        self.assertEqual(self.names(), ['before', 'stop'])

    def test_cannot_run_stops(self):
        code, err = self.run_loop(self.cfg(on_before_run=str(self.d / 'nope')))
        self.assertEqual(code, 1)
        self.assertIn('PointFailed run 1: on_before_run', err)
        self.assertNotIn('body', self.names())

    def test_ctl_stop_given_during_before_run_wins(self):
        ctl = self.stack / 'ctl.json'
        self.point('before', 'echo \'{"cmd": "stop", "seq": 1}\' > "%s"\n' % ctl)
        code, err = self.run_loop(self.cfg(ctl='ctl.json', interval_ms=20))
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(self.names(), ['before', 'stop'])

    def test_paused_fires_nothing(self):
        ctl = self.stack / 'ctl.json'
        ctl.write_text('{"cmd": "pause", "seq": 1}\n')
        p = subprocess.Popen([str(BIN), self.cfg(ctl='ctl.json', interval_ms=20, max=2)], env=self.env, cwd=self.d,
                             stderr=subprocess.PIPE, text=True)
        time.sleep(.6)
        self.assertEqual(self.lines(), [])
        ctl.write_text('{"cmd": "resume", "seq": 2}\n')
        self.assertEqual(p.wait(timeout=10), 0)
        p.stderr.close()
        self.assertEqual(self.names(), ['before', 'body', 'after', 'before', 'body', 'after', 'stop'])

    def test_signal_during_before_run_is_not_a_failure(self):
        self.point('before', 'echo started >> "$LOG"\ntrap "exit 0" TERM\nsleep 30 & wait\n')
        p = subprocess.Popen([str(BIN), self.cfg()], env=self.env, cwd=self.d, stderr=subprocess.PIPE, text=True)
        self.assertTrue(self.wait_for('started'))
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(timeout=10), 143)
        err = p.stderr.read()
        p.stderr.close()
        self.assertNotIn('PointFailed', err)
        self.assertEqual(self.names(), ['before', 'started', 'stop'])


class AfterRun(Fixture):
    def test_failure_after_a_good_run_stops_with_its_code(self):
        self.point('after', 'exit 5\n')
        code, err = self.run_loop(self.cfg())
        self.assertEqual(code, 5)
        self.assertEqual(err.splitlines(), ['aos-loop: error: PointFailed run 1: on_after_run %s exited 5' % (self.d / 'after')])
        self.assertEqual(self.names(), ['before', 'body', 'after', 'stop'])

    def test_failure_after_a_failed_run_is_a_warning(self):
        self.point('after', 'exit 5\n')
        self.point('body', 'exit 7\n')
        code, err = self.run_loop(self.cfg())
        self.assertEqual(code, 7)
        lines = err.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith('aos-loop: error: RunFailed run 1:'), lines)   # RunFailed 先印
        self.assertTrue(lines[1].startswith('aos-loop: warning: run 1: on_after_run'), lines)
        self.assertEqual(self.lines()[2], 'after 1 7 []')

    def test_not_fired_when_the_loop_got_a_signal(self):
        self.point('body', 'echo started >> "$LOG"\ntrap "exit 0" TERM\nsleep 30 & wait\n')
        p = subprocess.Popen([str(BIN), self.cfg()], env=self.env, cwd=self.d, stderr=subprocess.PIPE, text=True)
        self.assertTrue(self.wait_for('started'))
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(timeout=10), 143)
        p.stderr.close()
        self.assertEqual(self.names(), ['before', 'body', 'started', 'stop'])

    def test_body_killed_by_a_signal_gives_it(self):
        self.point('body', 'kill -KILL $$\n')
        code, _ = self.run_loop(self.cfg())
        self.assertEqual(code, 137)
        self.assertEqual(self.lines()[2], 'after 1 137 [9]')


class Flags(Fixture):
    def test_flag_file_turns_a_point_on(self):
        flag = self.stack / 'hook_before_run.flag'
        self.point('body', 'touch "%s"\n' % flag)   # 第一次跑完才有旗標檔
        code, err = self.run_loop(self.cfg(max=2, on_after_run='omit', on_before_run_if=str(flag)))
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(self.lines(), ['body unset unset [unset]', 'before 2 unset [unset]', 'body unset unset [unset]', 'stop unset unset [unset]'])

    def test_after_flag_and_directive(self):
        (self.stack / 'hook_after_run.flag').write_text('')
        self.point('body', 'exit 10\n')
        cfg = self.cfg(on_before_run_if={'$env': 'AOS_STACK', '$path': 'hook_before_run.flag'},
                       on_after_run_if={'$env': 'AOS_STACK', '$path': 'hook_after_run.flag'})
        self.assertEqual(self.run_loop(cfg), (0, ''))
        self.assertEqual(self.names(), ['body', 'after', 'stop'])

    def test_bad_flags(self):
        for kw, why in (({'on_before_run_if': ''}, 'CfgBad on_before_run_if must be a file path'),
                        ({'on_after_run_if': 3}, 'CfgBad on_after_run_if must be a file path'),
                        ({'on_before_run': 'omit', 'on_before_run_if': 'x'}, 'CfgBad on_before_run_if without on_before_run'),
                        ({'on_after_run': 5}, 'CfgBad on_after_run must be an aos-exec target')):
            with self.subTest(kw=kw):
                code, err = self.run_loop(self.cfg(**kw))
                self.assertEqual(code, 1)
                self.assertIn(why, err)
                self.assertEqual(self.lines(), [])


if __name__ == '__main__':
    unittest.main()
