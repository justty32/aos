# Verify the after_stop cause (B7) end to end: a real daemon writes stop_cause.json, its child aos-loop reads it, the after_stop handler run by aos-hook fire reads it from AOS_LOOP_CAUSE (11-21: the event has only event / hook / stack).
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest

from support import ENV, PROTO, Fixture, dc, read, until, write

CAUSE_FILE = 'stop_cause.json'   # 同 aos/loop.hpp 的 StopCauseWindow::default_name（測試另寫一份，不 import C++）
HOOK = PROTO / 'bin' / 'aos-hook'   # the templates' on_stop: aos-hook fire -q --stop-on-nonzero --def DEF after_stop
BODY = '''#!/usr/bin/env python3
# Test body: write ready, sleep; on SIGTERM wait SLOW seconds before exiting 0 (so the daemon is still "stopping").
import os, pathlib, signal, sys, time
s = pathlib.Path(os.environ['AOS_STACK'])
slow = float(sys.argv[2])
def term(signum, frame):
    time.sleep(slow)
    sys.exit(0)
signal.signal(signal.SIGTERM, term)
(s / 'ready').write_text('ready')
time.sleep(float(sys.argv[1]))
'''
HANDLER = '''#!%s
# after_stop handler: append the event JSON plus the loop's AOS_LOOP_CODE / AOS_LOOP_SIGNAL / AOS_LOOP_CAUSE to a log.
import json, os, sys
ev = json.load(sys.stdin)
env = {k: os.environ.get('AOS_LOOP_' + k.upper()) for k in ('code', 'signal', 'cause')}
with open(%r, 'a') as f:
    f.write(json.dumps({'event': ev, 'env': env}) + '\\n')
'''


def start_ticks(pid):
    text = Path('/proc/%d/stat' % pid).read_text()
    return int(text[text.rindex(')') + 2:].split()[19])   # 第 22 欄


class StopCause(unittest.TestCase):
    def fixture(self, name):
        f = Fixture('cause_' + name)
        self.addCleanup(f.close)
        body = f.root / 'cause_body.py'
        body.write_text(BODY)
        body.chmod(0o755)
        self.defn = f.root / 'def'   # 最小的 agent 定義：只有 after_stop 一格 hook
        self.defn.mkdir(exist_ok=True)
        self.events = f.root / 'events.jsonl'
        (self.defn / 'interfaces.json').write_text(json.dumps({'hookeds': 'hookeds.json'}))
        (self.defn / 'hookeds.json').write_text(json.dumps({'description': 'test', 'log': {'event': 'after_stop', 'handler': 'log.py'}}))
        handler = self.defn / 'log.py'
        handler.write_text(HANDLER % (sys.executable, str(self.events)))
        handler.chmod(0o755)
        self.body = body
        return f

    def add_loop(self, f, seconds=30, slow=0):
        spec = {'exec': [str(self.body), str(seconds), str(slow)], 'interval_ms': 30,
                'on_stop': [str(HOOK), 'fire', '-q', '--stop-on-nonzero', '--def', str(self.defn), 'after_stop']}
        reply = dc.ask(str(f.stack), {'procs_added': {'job': spec}})
        self.assertTrue(reply['applied'], reply)
        f.phase('running')
        until(lambda: (f.cell / 'ready').exists())
        self.assertTrue((f.cell / 'loop.json').exists())

    def causes(self, n=1):
        def got():
            try:
                lines = [json.loads(s) for s in self.events.read_text().splitlines()]
            except FileNotFoundError:
                return None
            return lines if len(lines) >= n else None
        events = until(got, timeout=15)
        for row in events:
            self.assertEqual(set(row['event']), {'event', 'hook', 'stack'})   # no code / signal / cause in the event
            self.assertEqual((row['event']['event'], row['event']['hook']), ('after_stop', 'log'))
            self.assertIsNotNone(row['env']['code'])
        return [row['env']['cause'] for row in events]

    def test_sleep(self):
        f = self.fixture('sleep').start()
        self.add_loop(f)
        f.ctl('sleep', 'job')
        self.assertEqual(self.causes(), ['sleep'])
        f.phase('sleeping')
        self.assertEqual(read(f.cell / CAUSE_FILE)['cause'], 'sleep')

    def test_rm(self):
        f = self.fixture('rm').start()
        self.add_loop(f)
        f.ctl('rm', 'job')
        self.assertEqual(self.causes(), ['remove'])

    def test_stop(self):
        f = self.fixture('stop').start()
        self.add_loop(f, seconds=.2)
        f.ctl('stop', 'job')
        self.assertEqual(self.causes(), ['stop'])
        f.phase('stopped')
        self.assertFalse((f.cell / CAUSE_FILE).exists())   # stop 走 ctl 窗，不寫原因檔

    def test_shutdown(self):
        f = self.fixture('shutdown').start()
        self.add_loop(f)
        f.close()
        self.assertEqual(self.causes(), ['shutdown'])

    def test_stop_then_rm_is_remove(self):   # stop 不寫原因檔：收的途中再 rm＝第一次寫，remove
        f = self.fixture('stop_rm').start()
        self.add_loop(f)
        f.ctl('stop', 'job')
        f.phase('stopping')
        f.ctl('rm', 'job')
        self.assertEqual(self.causes(), ['remove'])

    def test_sleep_then_rm_within_grace_is_remove(self):   # 定稿 2.3 唯一的覆寫例外
        f = self.fixture('sleep_rm').start()
        self.add_loop(f, slow=3)
        f.ctl('sleep', 'job')
        f.phase('stopping')
        self.assertEqual(read(f.cell / CAUSE_FILE)['cause'], 'sleep')
        f.ctl('rm', 'job')
        until(lambda: read(f.cell / CAUSE_FILE, {}).get('cause') == 'remove')
        self.assertFalse(self.events.exists())   # 身體還在 3 秒的收尾裡：on_stop 還沒跑
        self.assertEqual(self.causes(), ['remove'])
        until(lambda: f.row() is None)

    def test_sleep_then_shutdown_stays_sleep(self):   # 第一個原因不覆寫：收工不蓋 sleep
        f = self.fixture('sleep_shutdown').start()
        self.add_loop(f, slow=1.5)
        f.ctl('sleep', 'job')
        f.phase('stopping')
        f.close()
        self.assertEqual(self.causes(), ['sleep'])
        self.assertEqual(read(f.cell / CAUSE_FILE)['cause'], 'sleep')

    def test_adopt_does_not_rewrite(self):   # kill -9 daemon、重開：接回 stopping 的列重送 SIGTERM，原因檔一字不改
        f = self.fixture('adopt').start()
        self.add_loop(f, slow=2)
        f.ctl('sleep', 'job')
        f.phase('stopping')
        before = (f.cell / CAUSE_FILE).read_text()
        f.proc.kill()
        f.proc.wait()
        f.close()
        f.start()
        self.assertEqual(self.causes(), ['sleep'])
        self.assertEqual((f.cell / CAUSE_FILE).read_text(), before)

    def test_exec_row_writes_no_cause_file(self):
        f = self.fixture('exec').start()
        target = f.root / 'exec_body.json'
        write(target, [str(self.body), '30', '0'])
        f.ctl('add', '--name', 'job', str(target))
        f.phase('running')
        until(lambda: (f.cell / 'ready').exists())
        self.assertFalse((f.cell / 'loop.json').exists())
        f.ctl('rm', 'job')
        until(lambda: f.row() is None)
        self.assertFalse((f.cell / CAUSE_FILE).exists())


class DaemonOwnCause(unittest.TestCase):
    """aos-daemon 自己也是 loop：shutdown（ctl stop＝stopping_）收子項的途中再收到 SIGTERM（圖紙 6.3 第 1、2 條）。"""

    def fixture(self, name, cause_doc):
        f = Fixture('cause_daemon_' + name)
        self.addCleanup(f.close)
        log = f.root / 'daemon_cause.txt'
        sh = f.root / 'daemon_on_stop.sh'
        sh.write_text('#!/bin/sh\n# record the cause the daemon itself stopped with\necho "${AOS_LOOP_CAUSE-unset}" >> "%s"\n' % log)
        sh.chmod(0o755)
        write(f.config, {'interval_ms': 20, 'procs': {}, 'on_stop': [str(sh)]})
        f.start()
        body = f.root / 'cause_body.py'
        body.write_text(BODY)
        body.chmod(0o755)
        self.assertTrue(dc.ask(str(f.stack), {'procs_added': {'job': {'exec': [str(body), '30', '3'], 'interval_ms': 30}}})['applied'])
        f.phase('running')
        until(lambda: (f.cell / 'ready').exists())
        if cause_doc:
            with open('/proc/sys/kernel/random/boot_id') as b:
                boot = b.read().strip()
            ticks = start_ticks(f.proc.pid)
            write(f.stack / CAUSE_FILE, {'cause': 'remove', 'pid': f.proc.pid, 'started_at_ticks': ticks,
                                         'at_ticks': ticks + 1, 'boot_id': boot})
        p = subprocess.Popen(['aos-daemon-ctl', '--daemon', str(f.stack), 'shutdown'], cwd=f.root, env=ENV,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        until(lambda: read(f.cell / CAUSE_FILE, {}).get('cause') == 'shutdown')   # daemon 已在 finish 裡等子項（身體要 3 秒才退）
        f.proc.send_signal(signal.SIGTERM)
        f.proc.wait(timeout=15)
        p.wait(timeout=20)
        return until(lambda: log.exists() and log.read_text().split())

    def test_sigterm_while_stopping_with_cause_file(self):
        self.assertEqual(self.fixture('file', True), ['remove'])

    def test_sigterm_while_stopping_without_cause_file(self):
        self.assertEqual(self.fixture('nofile', False), ['stop'])


if __name__ == '__main__':
    unittest.main()
