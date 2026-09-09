"""aos-daemon 的命令列：真的開一個 daemon 進程，家在 /tmp，跑完 stop 並清掉。

一條測試走完一輩子：start→add→ls→get→pause→resume→rm→stop。
（`_util.py` 的坑：TestCase 裡別放叫 `run()` 的方法，那是 unittest 自己的。）
"""
import io
import json
import os
import shutil
import signal
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout

import _util           # noqa: F401  （它把 proto4-3 放進 sys.path）
import aos_daemon_cli as cli
from aos_home import Home, alive


def wait_until(cond, secs=8.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < secs:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


class DaemonCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aos-proto4-3-daemon-")
        self.addCleanup(self.cleanup)
        self.home = Home(os.path.join(self.tmp, "home"))
        self.work = os.path.join(self.tmp, "work")
        os.makedirs(os.path.join(self.work, ".aos"))
        with open(os.path.join(self.work, ".aos", "inst.json"), "w") as f:
            json.dump({"argv": ["sh", "-c", "exit 0"]}, f)
        self.key = os.path.realpath(self.work)

    def cleanup(self):
        pid = self.home.pid()
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            cli.stop(self.home)
        if pid and alive(pid):                      # 保險：不留殭屍 daemon
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        for p in cli._spawned:                      # 收屍，不然留一隻 <defunct>
            try:
                p.wait(timeout=5)
            except Exception:
                pass
        cli._spawned.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def call(self, *args):
        """叫一次 CLI，回 (退出碼, 印出來的東西)。"""
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            code = cli.main([str(a) for a in args] + ["--home", self.home.dir])
        return code, buf.getvalue()

    def table(self):
        return (self.home.state() or {}).get("runs", {})

    def test_start_add_ls_pause_resume_rm_stop(self):
        code, out = self.call("start")
        self.assertEqual((code, "起來了" in out), (0, True), out)
        self.assertTrue(self.home.alive())

        code, out = self.call("ls")                                  # 還沒有半個
        self.assertEqual(code, 0)
        self.assertIn("DIR  PID  PAUSED  RUNS  LAST_EXIT", out)
        self.assertNotIn(self.key, out)

        code, out = self.call("add", self.work, "--interval-ms", "200")
        self.assertEqual((code, "ok=True" in out), (0, True), out)
        self.assertTrue(wait_until(lambda: self.key in self.table()))    # state.json 看得到

        code, out = self.call("ls")
        self.assertIn(self.key, out)
        pid = self.table()[self.key]["pid"]
        self.assertTrue(alive(pid))
        code, out = self.call("get", self.work)                      # get 也吃沒 realpath 的寫法
        self.assertEqual((code, self.key in out), (0, True), out)
        self.assertEqual(self.call("get", os.path.join(self.tmp, "nope"))[0], 1)

        self.assertEqual(self.call("add", self.work)[0], 1)          # 同一個資料夾第二次＝1

        self.assertEqual(self.call("pause", self.key)[0], 0)
        self.assertTrue(wait_until(lambda: self.table()[self.key]["paused"]))
        self.assertIn("yes", self.call("ls")[1])
        self.assertEqual(self.call("resume", self.key)[0], 0)
        self.assertTrue(wait_until(lambda: not self.table()[self.key]["paused"]))

        code, out = self.call("rm", self.key)
        self.assertEqual((code, "ok=True" in out), (0, True), out)
        self.assertTrue(wait_until(lambda: self.key not in self.table()))
        self.assertTrue(wait_until(lambda: not alive(pid)))          # aos-run 也不在了

        dpid = self.home.pid()
        code, out = self.call("stop")
        self.assertEqual((code, "收工了" in out), (0, True), out)
        self.assertFalse(alive(dpid))
        self.assertFalse(os.path.exists(self.home.statef))
        self.assertFalse(os.path.exists(self.home.pidf))
        with open(self.home.logf, encoding="utf-8") as f:
            self.assertIn("add %s" % self.key, f.read())

    def test_second_start_says_already_running(self):
        self.assertEqual(self.call("start")[0], 0)
        pid = self.home.pid()
        code, out = self.call("start")
        self.assertEqual(code, 1)
        self.assertIn("已經在跑", out)
        self.assertEqual(self.home.pid(), pid)                       # 還是原來那隻

    def test_stop_takes_the_aos_runs_with_it(self):
        self.assertEqual(self.call("start")[0], 0)
        self.assertEqual(self.call("add", self.work, "--interval-ms", "200")[0], 0)
        self.assertTrue(wait_until(lambda: self.key in self.table()))
        pid = self.table()[self.key]["pid"]

        self.assertEqual(self.call("stop")[0], 0)
        self.assertTrue(wait_until(lambda: not alive(pid)))           # daemon 收工＝一起收掉
        self.assertFalse(self.home.alive())
        code, out = self.call("stop")                                 # 再 stop 一次
        self.assertEqual((code, "本來就沒在跑" in out), (0, True), out)

    def test_asking_a_dead_daemon_and_bad_usage(self):
        code, out = self.call("add", self.work)                       # daemon 沒起來
        self.assertEqual((code, "沒在跑" in out), (1, True), out)
        self.assertEqual(self.call("ls")[0], 1)                       # 連 state.json 都沒有
        self.assertEqual(self.call("nope")[0], 2)
        self.assertEqual(self.call("get")[0], 2)                      # get 要給 DIR
