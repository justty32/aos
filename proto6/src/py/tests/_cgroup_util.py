"""收屍／cgroup 模組系列測試共用：systemd-run scope、跳過條件、程序查詢與 CgCase 基底。"""
import os
import shutil
import subprocess
import threading
import unittest

import aos_daemon_cgroup
from _util import PY
from _daemon_util import CLEAN_ENV, DAEMON
from test_daemon_reload import ReloadCase


CG = {"cgroup": {}}
SCOPE = ["systemd-run", "--user", "--scope", "-p", "Delegate=yes", "--quiet", "--"]


def _probe():
    """拿得到可委派、有 cgroup.kill 的 scope 就回 None，不然回跳過的理由。"""
    if shutil.which("systemd-run") is None:
        return "沒有 systemd-run"
    check = 'p=/sys/fs/cgroup$(sed -n "s/^0:://p" /proc/self/cgroup); test -e "$p/cgroup.kill" && test -w "$p/cgroup.procs"'
    try:
        r = subprocess.run(SCOPE + ["sh", "-c", check], env=CLEAN_ENV, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "systemd-run 不能用：%s" % e
    return None if r.returncode == 0 else "拿不到委派的 cgroup v2 scope：%s" % r.stderr.decode(errors="replace").strip()


SKIP = _probe()


def alive(pid):
    """pid 還在而且不是殭屍。"""
    try:
        with open("/proc/%d/stat" % pid) as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


def procs(frame):
    with open(os.path.join(frame, "cgroup.procs")) as f:
        return [int(x) for x in f.read().split()]


def cat(path):
    with open(path) as f:
        return f.read().strip()


@unittest.skipIf(SKIP is not None, SKIP or "")
class CgCase(ReloadCase):

    def start(self, cfg, cwd=None, argv=None):
        """跟 DaemonCase.start 一樣，但包在 systemd-run 的委派 scope 裡；等 daemon 搬進 `<根>/daemon`，記下根。"""
        args = SCOPE + (argv or [PY, DAEMON, "--config", cfg])
        p = subprocess.Popen(args, cwd=cwd or self.d, env=CLEAN_ENV, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, start_new_session=True)
        out, err = [], []
        for stream, sink in ((p.stdout, out), (p.stderr, err)):
            threading.Thread(target=lambda s=stream, k=sink: [k.append(x.rstrip("\n")) for x in s],
                             daemon=True).start()
        self.addCleanup(self._stop, p)
        self.root = None
        self.wait_for(lambda: self._find_root(p), timeout=15)
        self.addCleanup(self._kill_scope, self.root)
        return p, out, err

    def _find_root(self, p):
        try:
            with open("/proc/%d/cgroup" % p.pid) as f:
                rel = [l[3:].strip() for l in f if l.startswith("0::")][0]
        except FileNotFoundError:
            return False
        if os.path.basename(rel) != "daemon":
            return False
        self.root = "/sys/fs/cgroup" + os.path.dirname(rel)
        return True

    @staticmethod
    def _kill_scope(root):
        try:
            with open(os.path.join(root, "cgroup.kill"), "w") as f:
                f.write("1")
        except FileNotFoundError:           # scope 已經沒了
            pass

    def frame(self, inst):
        return os.path.join(self.root, aos_daemon_cgroup.frame_name(inst))

    def bg(self):
        return [int(x) for x in self.read("bg").split()] if self.exists("bg") else []

    def texts(self, out):
        return [l.split(" ", 1)[1] for l in list(out)]
