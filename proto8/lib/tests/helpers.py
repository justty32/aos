"""proto8/lib 測試共用的部分：路徑、暫存資料夾的基底類別 `Tmp`、`alive()`、`leftovers()`。不是測試檔（discover 只收 test*.py）。

每個測試在 mktemp 建的暫存資料夾裡跑，跑完刪掉。刪之前查一次：cwd 在暫存資料夾裡的 aos_loop／aos_daemon 行程
還活著＝漏了（例：daemon 被 SIGKILL，自成 session 的子 loop 變孤兒），整群砍掉、這個測試算失敗。
"""
import json
import os
import shutil
import signal
import sys
import tempfile
import time
import unittest

LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INST = os.path.join(LIB, "aos_inst.py")
LOOP = os.path.join(LIB, "aos_loop.py")
DAEMON = os.path.join(LIB, "aos_daemon.py")
FSM = os.path.join(LIB, "aos_fsm.py")
sys.path.insert(0, LIB)


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aos-test-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.addCleanup(self.no_leftovers)          # 比 rmtree 先跑（cleanup 後進先出）

    def no_leftovers(self):
        """暫存資料夾裡還有活著的 aos_loop／daemon／fsm／gate／kernel 行程（cwd 或命令列路徑在內）＝漏了：等一下下（可能正在收），還在就整群 SIGKILL、算失敗。"""
        end = time.monotonic() + 2
        while leftovers(self.tmp) and time.monotonic() < end:
            time.sleep(0.05)
        left = leftovers(self.tmp)
        for pid, _ in left:
            for kill, who in ((os.killpg, pid), (os.kill, pid)):
                try:
                    kill(who, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        self.assertEqual(left, [], "測試漏了行程")

    def p(self, *parts):
        return os.path.join(self.tmp, *parts)

    def write(self, name, doc):
        path = self.p(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(doc if isinstance(doc, str) else json.dumps(doc))
        return path

    def read(self, name):
        with open(self.p(name)) as f:
            return f.read()

    def inst(self, name, sh, **keys):
        """寫 NAME/inst.json：在暫存資料夾裡用 sh 跑 SH。回資料夾的絕對路徑。"""
        self.write(name + "/inst.json", dict({"argv": ["sh", "-c", sh], "cwd": self.tmp}, **keys))
        return self.p(name)

    def until(self, cond, timeout=5):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            v = cond()
            if v:
                return v
            time.sleep(0.02)
        self.fail("等不到")


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def leftovers(root, names=("aos_loop.py", "aos_daemon.py", "aos_gate.py", "aos_fsm.py", "aos_kernel.py", "aos_gate_kernel.py", "aos_kernel_judge.py")):
    """cwd 或命令列路徑在 root 底下、命令列有 names 之一的行程：[(pid, 命令列), ...]（讀 /proc；不收殭屍）。"""
    root = os.path.realpath(root)

    def inside(p):
        return p == root or p.startswith(root + os.sep)

    found = []
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            cwd = os.readlink("/proc/%s/cwd" % d)
            with open("/proc/%s/cmdline" % d, "rb") as f:
                argv = f.read().decode(errors="replace").split("\0")
            with open("/proc/%s/stat" % d) as f:
                zombie = f.read().rsplit(")", 1)[1].split()[0] == "Z"
        except OSError:
            continue
        cmd = " ".join(argv).strip()
        if zombie or not any(os.path.basename(a) in names for a in argv):
            continue
        if inside(cwd) or any(inside(os.path.realpath(x)) for x in argv if x.startswith("/")):
            found.append((int(d), cmd))
    return found


def tree_hash(root):
    """資料夾裡所有檔（含相對路徑）的 sha256；拿來確定「沒被寫過」。"""
    import hashlib
    h = hashlib.sha256()
    for d, dirs, files in sorted(os.walk(root)):
        dirs.sort()
        for n in sorted(files):
            p = os.path.join(d, n)
            h.update(os.path.relpath(p, root).encode())
            with open(p, "rb") as f:
                h.update(f.read())
    return h.hexdigest()
