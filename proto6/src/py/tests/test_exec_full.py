"""cpu.md §4.1 完整結果入口；原來 run_target／run_inst 的契約另外保留。"""
import contextlib
import io
import os
import signal
import sys
import time

import aos_exec
from _util import Base


class FullTargetTests(Base):
    def job(self, body, rel="inst.json", **fields):
        return self.inst(dict(argv=[sys.executable, "-c", body], **fields), rel)

    def run_full(self, target, **kw):
        observer = kw.pop("on_spawn", None)
        def spawned(proc):
            if proc is not None:
                self.addCleanup(self.reap, proc)
            if observer:
                observer(proc)
        with contextlib.redirect_stderr(io.StringIO()):
            return aos_exec.run_target_full(target, poll_ms=2, on_spawn=spawned, **kw)

    @staticmethod
    def reap(proc):
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.wait(timeout=5)

    def assert_result(self, result, code, kind="child", timed_out=False, stopped=False):
        self.assertEqual((result.code, result.kind, result.timed_out, result.stopped),
                         (code, kind, timed_out, stopped))
        self.assertIsInstance(result.ms, int)
        self.assertGreaterEqual(result.ms, 0)

    def test_plain_args(self):
        path = self.write("script", "#!/bin/sh\n[ \"$1\" = 'a b' ]\n", executable=True)
        self.assert_result(self.run_full(path, args=["a b"]), 0)

    def test_inst_normal_and_exit_file(self):
        path = self.job("raise SystemExit(7)", exit="status")
        self.assert_result(self.run_full(path), 7)
        self.assertEqual(self.read("status"), "7\n")

    def test_directory_base(self):
        self.job("import os; assert os.getcwd() == %r" % self.d, rel=".aos/inst.json")
        self.assert_result(self.run_full(self.d), 0)

    def test_timeout_three_targets(self):
        plain = self.write("slow", "#!/bin/sh\nsleep 30\n", executable=True)
        inst = self.job("import time; time.sleep(30)")
        self.job("import time; time.sleep(30)", rel=".aos/inst.json")
        for target in (plain, inst, self.d):
            with self.subTest(target=target):
                self.assert_result(self.run_full(target, timeout_ms=40), 143, timed_out=True)

    def test_timeout_term_handler_exit_zero(self):
        ready = os.path.join(self.d, "ready")
        path = self.job("import signal,time,pathlib; "
                        "signal.signal(signal.SIGTERM, lambda *a: exit(0)); "
                        "pathlib.Path(%r).touch(); time.sleep(30)" % ready)
        result = self.run_full(path, timeout_ms=300)
        self.assertTrue(os.path.exists(ready))
        self.assert_result(result, 0, timed_out=True)

    def test_natural_143_is_not_timeout(self):
        self.assert_result(self.run_full(self.job("raise SystemExit(143)")), 143)

    def test_missing_json_is_aos(self):
        self.assert_result(self.run_full(os.path.join(self.d, "missing.json")), 1, "aos")

    def test_usage_unchanged(self):
        inst = self.job("pass")
        for target, kw in ((os.path.join(self.d, "missing"), {}), (self.d, {}),
                           (inst, {"args": []})):
            with self.subTest(target=target, kw=kw):
                self.assert_result(self.run_full(target, **kw), 2, "usage")

    def test_missing_program_is_child(self):
        path = self.inst({"argv": ["/no-such-full-test-program"], "exit": "status"}, "inst.json")
        self.assert_result(self.run_full(path), 127)
        self.assertEqual(self.read("status"), "127\n")

    def test_poll_cancel(self):
        polls, spawned = [], []
        def poll(proc):
            polls.append(proc.pid)
            return True
        result = self.run_full(self.job("import time; time.sleep(30)"),
                               on_poll=poll, on_spawn=spawned.append)
        self.assert_result(result, 143, stopped=True)
        self.assertTrue(polls)
        self.assertEqual(len(spawned), 2)
        self.assertIsNone(spawned[-1])
        self.assertIsNotNone(spawned[0].returncode)

    def test_finished_before_callback_is_not_stopped(self):
        def spawned(proc):
            if proc is not None:
                proc.wait(timeout=5)
        self.assert_result(self.run_full(self.job("pass"), on_spawn=spawned,
                                        on_poll=lambda proc: True), 0)

    def test_cancel_grace_still_polls_then_kills(self):
        ready = os.path.join(self.d, "ready")
        path = self.job("import signal,time,pathlib; "
                        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                        "pathlib.Path(%r).touch(); time.sleep(30)" % ready)
        polls = []
        def poll(proc):
            if os.path.exists(ready):
                polls.append(time.monotonic())
                return True
            return False
        result = self.run_full(path, on_poll=poll)
        self.assert_result(result, 137, stopped=True)
        self.assertGreater(polls[-1] - polls[0], 1.8)

    def test_cancel_during_timeout_grace(self):
        path = self.job("import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)")
        start = time.monotonic()
        result = self.run_full(path, timeout_ms=100,
                               on_poll=lambda proc: time.monotonic() - start > .2)
        self.assert_result(result, 137, timed_out=True, stopped=True)

    def test_old_run_target_is_two_value_tuple(self):
        result = aos_exec.run_target(self.job("pass"))
        self.assertEqual(result, (0, "child"))
        self.assertIs(type(result), tuple)
