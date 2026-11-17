# Check loop.json on_start / on_stop: run once before the first run and once on every way out (11-11 clock-hook).
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

LOG_SH = '#!/bin/sh\n# append one line: the name, the code and signal given to on_stop\necho "%s ${AOS_LOOP_CODE-unset} ${AOS_LOOP_SIGNAL-unset}" >> "$LOG"\n'


class Fixture(unittest.TestCase):
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


class OnStartStop(Fixture):
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

    def test_zero_timeout_does_not_limit_lifecycle_targets(self):
        self.script('start', '#!/bin/sh\n# Complete a delayed startup.\nsleep 0.1\necho start >> "$LOG"\n')
        self.body('exit 10\n')
        code, err = self.run_loop(self.cfg(on_timeout_ms=0, on_stop={
            'argv': ['sh', '-c', 'sleep 0.1; echo inline-stop >> "$LOG"']}))
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(self.lines(), ['start', 'body', 'inline-stop'])

    def test_inline_zero_timeout_overrides_lifecycle_default(self):
        self.body('exit 10\n')
        code, err = self.run_loop(self.cfg(on_start=None, on_timeout_ms=1, on_stop={
            'argv': ['sh', '-c', 'sleep 0.1; echo inline-stop >> "$LOG"'], 'timeout_ms': 0}))
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(self.lines(), ['body', 'inline-stop'])

    def test_bad_timeout(self):
        self.body('exit 10\n')
        for value in (-1, .5, True, '0'):
            with self.subTest(value=value):
                code, err = self.run_loop(self.cfg(on_timeout_ms=value))
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


# 11-14 B7：on_stop 的 AOS_LOOP_CAUSE 與原因檔（名字照 ok-devt 定稿；測試各只在這裡寫一次，同 aos/loop.hpp 的 StopCauseWindow::default_name、cause_env）
CAUSE_FILE = 'stop_cause.json'
CAUSE_ENV = 'AOS_LOOP_CAUSE'
CAUSE_SH = '#!/bin/sh\n# append the cause given to on_stop (or what on_start / the body sees)\necho "%%s ${%s-unset}" >> "$LOG"\n' % CAUSE_ENV


def start_ticks(pid):
    text = Path('/proc/%d/stat' % pid).read_text()
    return int(text[text.rindex(')') + 2:].split()[19])   # 第 22 欄


def now_ticks():
    return int(time.clock_gettime(time.CLOCK_BOOTTIME) * os.sysconf('SC_CLK_TCK'))


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


class StopCause(Fixture):
    def setUp(self):
        super().setUp()
        for name in ('start', 'stop'):
            self.script(name, CAUSE_SH % name)

    def cause_doc(self, pid, cause='sleep', **kw):
        doc = {'cause': cause, 'pid': pid, 'started_at_ticks': start_ticks(pid), 'at_ticks': now_ticks(), 'boot_id': boot_id()}
        doc.update(kw)
        return doc

    def write_cause(self, doc):
        (self.d / 'stack' / CAUSE_FILE).write_text(doc if isinstance(doc, str) else json.dumps(doc))

    def stop_line(self):
        return [line for line in self.lines() if line.startswith('stop ')]

    def start_body_loop(self, cfg=None, env=None):
        self.body('trap \'kill $! 2>/dev/null; exit 0\' TERM INT\nsleep 30 & wait\n')   # 收掉背景的 sleep：不然它拿著 stderr 管子，讀 stderr 要等滿 30 秒
        p = subprocess.Popen([str(BIN), cfg or self.cfg()], env=env or self.env, cwd=self.d, stderr=subprocess.PIPE, text=True)
        end = time.monotonic() + 5
        while 'body' not in self.lines() and time.monotonic() < end:
            time.sleep(.02)
        return p

    def signalled(self, doc=None, sig=signal.SIGTERM):
        """起一支跑著身體的 loop；doc（函式：pid → 原因檔內容）有給就先寫原因檔，再送 sig；回 stderr。"""
        p = self.start_body_loop()
        if doc is not None:
            self.write_cause(doc(p.pid))
        p.send_signal(sig)
        self.assertEqual(p.wait(timeout=10), 128 + sig)
        err = p.stderr.read()
        p.stderr.close()
        return err

    def test_cause_ctl_stop(self):
        self.body('sleep 0.05\n')
        p = subprocess.Popen([str(BIN), self.cfg(ctl='ctl.json', interval_ms=50)], env=self.env, cwd=self.d, stderr=subprocess.PIPE, text=True)
        time.sleep(.3)
        (self.d / 'stack' / 'ctl.json').write_text('{"cmd": "stop", "seq": 1}\n')
        self.assertEqual(p.wait(timeout=10), 0)
        p.stderr.close()
        self.assertEqual(self.stop_line(), ['stop stop'])

    def test_cause_max(self):
        self.body('exit 0\n')
        self.assertEqual(self.run_loop(self.cfg(max=2)), (0, ''))
        self.assertEqual(self.stop_line(), ['stop max'])

    def test_cause_body_exit(self):
        self.body('exit 10\n')
        self.assertEqual(self.run_loop(self.cfg())[0], 0)
        self.assertEqual(self.stop_line(), ['stop body_exit'])

    def test_cause_body_fails(self):
        self.body('exit 3\n')
        self.assertEqual(self.run_loop(self.cfg())[0], 3)
        self.assertEqual(self.stop_line(), ['stop error'])

    def test_cause_from_fresh_file(self):
        err = self.signalled(lambda pid: self.cause_doc(pid, 'sleep'))
        self.assertEqual(err, '')
        self.assertEqual(self.stop_line(), ['stop sleep'])

    def test_cause_old_file_is_signal(self):   # 上一輪留下的：started_at_ticks 比自己早、at_ticks 也比自己早
        err = self.signalled(lambda pid: self.cause_doc(pid, 'sleep', started_at_ticks=start_ticks(pid) - 200, at_ticks=start_ticks(pid) - 100))
        self.assertEqual(err, '')
        self.assertEqual(self.stop_line(), ['stop signal'])

    def test_cause_no_file_is_signal(self):
        self.assertEqual(self.signalled(), '')
        self.assertEqual(self.stop_line(), ['stop signal'])

    def test_cause_bad_json_warns(self):
        err = self.signalled(lambda pid: '{"cause": "sleep", ')
        self.assertIn('aos-loop: warning: stop cause file unusable', err)
        self.assertEqual(self.stop_line(), ['stop signal'])

    def test_cause_missing_field_warns(self):
        err = self.signalled(lambda pid: {k: v for k, v in self.cause_doc(pid).items() if k != 'at_ticks'})
        self.assertIn('aos-loop: warning: stop cause file unusable', err)
        self.assertEqual(self.stop_line(), ['stop signal'])

    def test_cause_other_boot_is_signal(self):
        err = self.signalled(lambda pid: self.cause_doc(pid, boot_id='00000000-0000-0000-0000-000000000000'))
        self.assertEqual(err, '')
        self.assertEqual(self.stop_line(), ['stop signal'])

    def test_cause_other_process_is_signal(self):   # started_at_ticks 不同、也不在外殼的區間（at_ticks 比自己早）內
        for shift in (+50, -50):
            with self.subTest(shift=shift):
                if self.log.exists():
                    self.log.unlink()
                err = self.signalled(lambda pid: self.cause_doc(pid, started_at_ticks=start_ticks(pid) + shift,
                                                                 at_ticks=start_ticks(pid) - 1 if shift < 0 else now_ticks()))
                self.assertEqual(err, '')
                self.assertEqual(self.stop_line(), ['stop signal'])

    def test_cause_under_a_wrapper(self):   # daemon 起的是外殼（sh）、loop 是它的子行程：started_at_ticks < 自己 <= at_ticks
        self.body('trap \'kill $! 2>/dev/null; exit 0\' TERM INT\nsleep 30 & wait\n')   # 收掉背景的 sleep：不然它拿著 stderr 管子，讀 stderr 要等滿 30 秒
        w = subprocess.Popen(['sh', '-c', 'sleep 0.1; "$0" "$1"; exit $?', str(BIN), self.cfg()], env=self.env, cwd=self.d,
                             stderr=subprocess.PIPE, text=True)
        end = time.monotonic() + 5
        while 'body' not in self.lines() and time.monotonic() < end:
            time.sleep(.02)
        kids = Path('/proc/%d/task/%d/children' % (w.pid, w.pid)).read_text().split()
        self.assertEqual(len(kids), 1)
        loop = int(kids[0])
        self.assertLess(start_ticks(w.pid), start_ticks(loop))
        self.write_cause(self.cause_doc(w.pid, 'remove'))
        os.kill(loop, signal.SIGTERM)
        self.assertEqual(w.wait(timeout=10), 143)
        w.stderr.close()
        self.assertEqual(self.stop_line(), ['stop remove'])

    def test_cause_unknown_word_is_copied(self):
        self.signalled(lambda pid: self.cause_doc(pid, 'future_x'))
        self.assertEqual(self.stop_line(), ['stop future_x'])

    def test_cause_bad_word_warns(self):
        for word in ('Sleep', 'a' * 33, '', 'x-y'):
            with self.subTest(word=word):
                if self.log.exists():
                    self.log.unlink()
                err = self.signalled(lambda pid: self.cause_doc(pid, word))
                self.assertIn('aos-loop: warning: stop cause file unusable', err)
                self.assertEqual(self.stop_line(), ['stop signal'])

    def test_cause_sigint_ignores_file(self):
        err = self.signalled(lambda pid: self.cause_doc(pid, 'remove'), sig=signal.SIGINT)
        self.assertEqual(err, '')
        self.assertEqual(self.stop_line(), ['stop signal'])

    def test_cause_env_from_outside_is_cleared(self):
        self.body('echo "body ${%s-unset}" >> "$LOG"\nexit 0\n' % CAUSE_ENV)
        self.env[CAUSE_ENV] = 'junk'
        self.assertEqual(self.run_loop(self.cfg(max=1)), (0, ''))
        self.assertEqual(self.lines(), ['start unset', 'body', 'body unset', 'stop max'])


if __name__ == '__main__':
    unittest.main()
