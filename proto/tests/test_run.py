"""aosp/run.py（run+daemon 隊寫）：--steps / --until idle / --budget / 串失敗 / 鎖被佔。

run.py 現在可能還是空檔；空檔時整個模組跳過，不要讓 discover 炸掉。
"""
import os
import sys
import unittest

PROTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

from aosp import exits, fsutil  # noqa: E402
from .helpers import LandCase, write_source, run_cli  # noqa: E402

PY = sys.executable


def setUpModule():
    try:
        from aosp import run as runmod
    except Exception as e:  # pragma: no cover - 環境問題
        raise unittest.SkipTest("import aosp.run 失敗：%s" % e)
    if not hasattr(runmod, "cli_run"):
        raise unittest.SkipTest("aosp/run.py 還沒寫 cli_run()，先跳過整支")


class TestRunSteps(LandCase):
    def test_steps_n_stops_after_n_ticks(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst", "inst": {"argv": [PY, "-c", "pass"]}, "then": "s1"},
        ])
        rc, out, err = run_cli("run", self.land.root, "--steps", "3")
        self.assertEqual(rc, exits.OK, msg="正常跑完 N 格應該退出碼 0，stdout=%r stderr=%r" % (out, err))
        st = fsutil.read_json(self.land.stopped)
        self.assertIsNotNone(st, msg="跑完指定格數應該寫 .aos/stopped.json")
        self.assertEqual(st.get("reason"), "steps_done",
                          msg="因為步數跑完而停，reason 該是 steps_done，實際 %r" % st)

    def test_until_idle_stops_when_idle(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst", "inst": {"argv": [PY, "-c", "pass"]}, "then": "end"},
        ])
        rc, out, err = run_cli("run", self.land.root, "--until", "idle")
        self.assertEqual(rc, exits.OK, msg="跑到閒著應該正常結束，stdout=%r stderr=%r" % (out, err))
        st = fsutil.read_json(self.land.stopped)
        self.assertIsNotNone(st, msg="停下時該寫 .aos/stopped.json")
        self.assertEqual(st.get("reason"), "idle",
                          msg="因為閒著而停，reason 該是 idle，實際 %r" % st)


class TestRunBudget(LandCase):
    def test_budget_exceeded_stops_with_reason_budget(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst", "inst": {"argv": [PY, "-c", "pass"]}, "then": "s1"},
        ])
        rc, out, err = run_cli("run", self.land.root, "--budget", "2")
        self.assertEqual(rc, exits.STOPPED,
                          msg="超過 budget 該退出碼 5，實際 %r，stderr=%r" % (rc, err))
        st = fsutil.read_json(self.land.stopped)
        self.assertIsNotNone(st, msg="超過 budget 該寫 .aos/stopped.json")
        self.assertEqual(st.get("reason"), "budget",
                          msg="超過預算而停，reason 該是 budget，實際 %r" % st)


class TestRunSeriesFailure(LandCase):
    def test_series_failure_stops_run_with_reason_failed(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst", "inst": {"argv": ["/no/such/binary-xyz"]}},
        ])
        rc, out, err = run_cli("run", self.land.root, "--until", "idle")
        self.assertEqual(rc, exits.STOPPED,
                          msg="串失敗導致停該退出碼 5，實際 %r" % rc)
        st = fsutil.read_json(self.land.stopped)
        self.assertIsNotNone(st, msg="串失敗該寫 .aos/stopped.json")
        self.assertEqual(st.get("reason"), "failed",
                          msg="因為串失敗而停，reason 該是 failed，實際 %r" % st)


class TestRunLockBusy(LandCase):
    def test_lock_busy_exit_code_75(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst", "inst": {"argv": [PY, "-c", "pass"]}, "then": "end"},
        ])
        lock = fsutil.Lock(self.land.lock)
        lock.acquire()
        try:
            rc, out, err = run_cli("run", self.land.root, "--steps", "1")
            self.assertEqual(rc, exits.LOCK_BUSY,
                              msg="鎖被佔時跑 run 該退出碼 75，實際 %r，stderr=%r" % (rc, err))
        finally:
            lock.release()
