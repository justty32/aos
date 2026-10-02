"""帳號模組系列測試共用：測試帳號、假 root 的 namespace 探測與 NsCase 基底。"""
import os
import pwd
import shutil
import subprocess
import tempfile
import threading
import unittest

from _util import PY
from _daemon_util import CLEAN_ENV, DaemonCase


HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
NS = ["unshare", "--user", "--map-root-user", "--map-auto"]


def _have(name):
    try:
        pwd.getpwnam(name)
        return True
    except KeyError:
        return False


# 預設帳號：Arch 有 http、Debian／Ubuntu 有 www-data；都沒有就退到 bin、sys（三個帳號要不同、都不是 root）
DEFAULT = next((n for n in ("http", "www-data", "bin", "sys") if _have(n)), "http")
OTHER, THIRD = "daemon", "nobody"


def _ns_ok():
    """namespace 裡是 root，而且切得到三個帳號（各 fork 一次試 setuid）。"""
    code = ("import os,pwd\n"
            "assert os.geteuid()==0\n"
            "for n in %r:\n"
            "    p=pwd.getpwnam(n); pid=os.fork()\n"
            "    if pid==0:\n"
            "        os.initgroups(n,p.pw_gid); os.setgid(p.pw_gid); os.setuid(p.pw_uid); os._exit(0)\n"
            "    assert os.waitstatus_to_exitcode(os.waitpid(pid,0)[1])==0\n" % ((DEFAULT, OTHER, THIRD),))
    try:
        return subprocess.run(NS + [PY, "-c", code], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


NS_OK = _ns_ok()


@unittest.skipUnless(NS_OK, "拿不到 unshare --map-auto 的假 root 或測試帳號；要等真 root 手動驗")
class NsCase(DaemonCase):
    """在 user namespace 裡開 daemon；src/py 複製到 /tmp。"""

    @classmethod
    def setUpClass(cls):
        cls.copy = tempfile.mkdtemp(prefix="aos-acct-src-")
        os.chmod(cls.copy, 0o755)
        shutil.copytree(SRC, os.path.join(cls.copy, "py"), ignore=shutil.ignore_patterns("__pycache__"))
        cls.daemon = os.path.join(cls.copy, "py", "bin", "aos-daemon")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.copy, ignore_errors=True)

    def setUp(self):
        super().setUp()
        os.chmod(self.d, 0o777)
        # 別的帳號建的檔、資料夾外面刪不掉：先在 namespace 裡（root）清掉
        self.addCleanup(subprocess.run, NS + ["rm", "-rf", self.d], capture_output=True)

    def write(self, rel, body, executable=False):
        p = super().write(rel, body, executable)
        os.chmod(p, 0o755 if executable else 0o644)
        return p

    def start_ns(self, cfg, env=None):
        p = subprocess.Popen(NS + [PY, self.daemon, "--config", cfg], cwd=self.d, env=env or CLEAN_ENV,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        out, err = [], []
        for stream, sink in ((p.stdout, out), (p.stderr, err)):
            threading.Thread(target=lambda s=stream, k=sink: [k.append(x.rstrip("\n")) for x in s],
                             daemon=True).start()
        self.addCleanup(self._stop, p)
        return p, out, err

    def run_ns(self, cfg, env=None):
        return subprocess.run(NS + [PY, self.daemon, "--config", cfg], cwd=self.d, env=env or CLEAN_ENV,
                              capture_output=True, text=True, timeout=10)

    def cfg(self, insts, account=None, interval_ms=100000, **mods):
        modules = dict({"account": {"user": DEFAULT, "allow": [OTHER, THIRD]} if account is None else account},
                       **mods)
        return self.config({"interval_ms": interval_ms, "modules": modules, "insts": insts})

    def who(self, name):
        """任務寫的 `id -un`、`id -G`、HOME、USER、LOGNAME。"""
        words = self.read("who." + name).split()
        return {"user": words[0], "groups": set(words[1:-3]), "home": words[-3], "USER": words[-2],
                "LOGNAME": words[-1]}

    def uid_line(self, pid):
        with open("/proc/%d/status" % pid) as f:
            return [l.split()[1:] for l in f if l.startswith("Uid:")][0]

    def children(self, pid):
        with open("/proc/%d/task/%d/children" % (pid, pid)) as f:
            return [int(x) for x in f.read().split()]
