"""aos-kernel 測試的共用底座：真的開一支 aos-daemon（家在 /tmp、走 `AOS_DAEMON_HOME`）、
真的跑 aos-kernel-init／aos-kernel-tick／aos-kernel 的小幫手，與 `KernelTest` 基底類別（只有 helper、沒有測試）。
三個測試檔各拿一塊：`test_kernel_init.py`（init／boot／add／rm／ls）、`test_kernel_exit.py`（退出碼政策：done、
waiting、bad_after）、`test_kernel_daemon.py`（真開 daemon 跑整條）。
每條測試跑完 kill daemon、刪家，不留孤兒。
（`_util.py` 的坑：TestCase 裡別放叫 `run()` 的方法，那是 unittest 自己的。）
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

import _util           # noqa: F401  （它把 proto4-3 放進 sys.path）
from aos_home import Home, alive
from aos_kernel import IDLE_INST, KHome
from aos_kernel_syscall import handle_syscalls
from aos_kernel_schedule import _observe_exit, _one_cpu

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KERNEL_BIN = os.path.join(ROOT, "aos-kernel")
INIT_BIN = os.path.join(ROOT, "aos-kernel-init")
BOOT_BIN = os.path.join(ROOT, "aos-kernel-boot")
TICK_BIN = os.path.join(ROOT, "aos-kernel-tick")
DAEMON_BIN = os.path.join(ROOT, "aos-daemon")
CTL_BIN = os.path.join(ROOT, "aos-daemon-ctl")


def wait_until(cond, secs=8.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < secs:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


class KernelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aos-proto4-3-kernel-")
        self.addCleanup(self.cleanup)
        self.home = Home(os.path.join(self.tmp, "dhome"))
        self.env = dict(os.environ, AOS_DAEMON_HOME=self.home.dir)
        self.k = os.path.join(self.tmp, "k")
        self.proc = None

    # ---- 開關機 ----
    def spawn_daemon(self):
        self.home.ensure()
        log = open(os.path.join(self.tmp, "daemon.out"), "ab")
        self.addCleanup(log.close)
        self.proc = subprocess.Popen([sys.executable, DAEMON_BIN], env=self.env,
                                     stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                     start_new_session=True, cwd=self.home.dir)
        self.assertTrue(wait_until(lambda: self.home.alive()))

    def cleanup(self):
        pid = self.home.pid()
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except OSError:
                    pass
        if pid and alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- 叫程式 ----
    def kernel(self, *args, cwd=None):
        return subprocess.run([sys.executable, KERNEL_BIN] + [str(a) for a in args],
                              env=self.env, cwd=cwd, capture_output=True, text=True,
                              timeout=60)
    def ctl(self, *args):
        return subprocess.run([sys.executable, CTL_BIN] + [str(a) for a in args],
                              env=self.env, capture_output=True, text=True, timeout=30)

    def kernel_init(self, *args):
        return subprocess.run([sys.executable, INIT_BIN] + [str(a) for a in args],
                              env=self.env, capture_output=True, text=True, timeout=30)

    def kernel_tick(self, *args, cwd=None):
        return subprocess.run([sys.executable, TICK_BIN] + [str(a) for a in args],
                              env=self.env, cwd=cwd, capture_output=True, text=True,
                              timeout=60)

    def kernel_boot(self, *args, cwd=None):
        return subprocess.run([sys.executable, BOOT_BIN] + [str(a) for a in args],
                              env=self.env, cwd=cwd, capture_output=True, text=True,
                              timeout=30)

    def init(self, ncpu=2, **kw):
        args = [self.k, "--ncpu", ncpu]
        for flag, v in kw.items():
            args += ["--" + flag.replace("_", "-"), v]
        r = self.kernel_init(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def tick(self):
        r = self.kernel_tick(cwd=self.k)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    # ---- 看東西 ----
    def at(self, *rel):
        return os.path.join(self.k, *rel)

    def table(self):
        return (self.home.state() or {}).get("runs", {})

    def cpu_key(self, n):
        return os.path.realpath(self.at("cpus", "%d.json" % n))

    def kstate(self):
        with open(self.at("state.json"), encoding="utf-8") as f:
            return json.load(f)

    def on_cpus(self):
        cpus = self.kstate()["cpus"]
        return {n: (c or {}).get("pid") for n, c in cpus.items()}

    def put_proc(self, pid, body=None, cwd=True):
        """寫一個等著上 cpu 的行程：它每跑一次就往自己 cwd 的 log.txt 加一行。"""
        d = os.path.join(self.tmp, "p%s" % pid)
        os.makedirs(d, exist_ok=True)
        if body is None:
            body = {"argv": ["sh", "-c", "echo hi >> log.txt"]}
            if cwd:
                body["cwd"] = d
        with open(self.at("procs", "%s.json" % pid), "w", encoding="utf-8") as f:
            f.write(body if isinstance(body, str) else json.dumps(body))
        return os.path.join(d, "log.txt")

    def write_inst(self, rel, body):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False)
        return path

    def put_syscall(self, name, body):
        path = self.at("syscalls", name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body if isinstance(body, str) else json.dumps(body))
        return path
