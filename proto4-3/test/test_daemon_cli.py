"""aos-daemon（普通前台程式）＋ aos-daemon-ctl（下指令）：真的開一支 daemon 進程，
家在 /tmp，跑完 stop 並清掉。

一條測試走完一輩子：開 daemon→add→ls→get→pause→resume→rm→stop（daemon 進程真的
退出、退出碼 0）。
（`_util.py` 的坑：TestCase 裡別放叫 `run()` 的方法，那是 unittest 自己的。）
"""
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout

import _util           # noqa: F401  （它把 proto4-3 放進 sys.path）
import aos_daemon_ctl as ctl
from aos_home import Home, alive

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DAEMON_BIN = os.path.join(ROOT, "aos-daemon")


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
        self.proc = None

    def spawn(self):
        """真的開一支 `aos-daemon --home H`——它自己不會背景化，這裡測的就是它前台跑著。"""
        self.home.ensure()          # cwd 得先存在，daemon 自己也會 ensure 但那是進程裡的事
        with open(os.path.join(self.tmp, "daemon.stdout"), "ab") as log:
            p = subprocess.Popen([sys.executable, DAEMON_BIN, "--home", self.home.dir],
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                 start_new_session=True, cwd=self.home.dir)
        self.proc = p
        return p

    def cleanup(self):
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except OSError:
                pass
            try:
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except OSError:
                    pass
        pid = self.home.pid()
        if pid and alive(pid):                      # 保險：不留殭屍 daemon
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def call(self, *args):
        """叫一次 ctl，回 (退出碼, 印出來的東西)。"""
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            code = ctl.main([str(a) for a in args] + ["--home", self.home.dir])
        return code, buf.getvalue()

    def table(self):
        return (self.home.state() or {}).get("runs", {})

    def test_daemon_up_add_ls_pause_resume_rm_stop(self):
        self.spawn()
        self.assertTrue(wait_until(lambda: self.home.state() is not None))
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
        self.assertTrue(wait_until(lambda: not alive(dpid)))
        self.assertTrue(wait_until(lambda: self.proc.poll() is not None))    # daemon 進程真的退出
        self.assertEqual(self.proc.wait(timeout=5), 0)                       # 退出碼 0
        self.assertFalse(os.path.exists(self.home.statef))
        self.assertFalse(os.path.exists(self.home.pidf))
        with open(self.home.logf, encoding="utf-8") as f:
            self.assertIn("add %s" % self.key, f.read())

    def test_second_daemon_says_already_running(self):
        self.spawn()
        self.assertTrue(wait_until(lambda: self.home.alive()))
        pid = self.home.pid()
        p2 = subprocess.run([sys.executable, DAEMON_BIN, "--home", self.home.dir],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            cwd=self.home.dir, text=True, timeout=5)
        self.assertEqual(p2.returncode, 1)
        self.assertIn("已經在跑", p2.stdout)
        self.assertEqual(self.home.pid(), pid)                       # 還是原來那隻

    def test_stop_takes_the_aos_runs_with_it(self):
        self.spawn()
        self.assertTrue(wait_until(lambda: self.home.alive()))
        self.assertEqual(self.call("add", self.work, "--interval-ms", "200")[0], 0)
        self.assertTrue(wait_until(lambda: self.key in self.table()))
        pid = self.table()[self.key]["pid"]

        self.assertEqual(self.call("stop")[0], 0)
        self.assertTrue(wait_until(lambda: not alive(pid)))           # daemon 收工＝一起收掉
        self.assertTrue(wait_until(lambda: not self.home.alive()))
        code, out = self.call("stop")                                 # 再 stop 一次
        self.assertEqual((code, "沒在跑" in out), (1, True), out)

    def test_asking_a_dead_daemon_and_bad_usage(self):
        code, out = self.call("add", self.work)                       # daemon 沒起來
        self.assertEqual((code, "沒在跑" in out), (1, True), out)
        self.assertEqual(self.call("ls")[0], 1)                       # 連 state.json 都沒有
        self.assertEqual(self.call("nope")[0], 2)
        self.assertEqual(self.call("get")[0], 2)                      # get 要給 DIR


if __name__ == "__main__":
    unittest.main()
