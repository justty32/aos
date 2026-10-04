"""測試共用：暫存空間根、node、跑 tick／tock（子程序或同程序）、起 daemon；結束時**先**收程序、**再**刪空間（N-55）。

cleanup 後進先出：setUp 先登記刪空間、再登記收程序；之後每個 Popen 用 `_proc.track` 登記的 reap 最先跑。
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
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)
LIB = os.path.join(TOP, "lib")
BIN = os.path.join(TOP, "bin")
MODULES = os.path.join(TOP, "modules")
TOOLS = os.path.join(MODULES, "tools")   # 工具包（aos7_ctl、任務端函式 aos7_taskside）
sys.path.insert(0, TOOLS)
sys.path.insert(0, LIB)
sys.path.insert(0, HERE)
# 測試鉤子（故障注入、SIGKILL／卡住點）：核心 aos7_fs 只在這個環境變數指到 _hooks.py 時才載入；所有子程序都繼承
os.environ["AOS7_TEST_HOOKS"] = os.path.join(HERE, "_hooks.py")

import _proc  # noqa: E402
import aos7_task  # noqa: E402
import aos7_tick  # noqa: E402
import aos7_tock  # noqa: E402
from aos7_fs import read_json, read_jsonl, write_json  # noqa: E402

# 同程序跑 tick（itick）時起的 aos7-run 不等它（tick 本來就不等任務），Popen 物件被回收時的 ResourceWarning 不看
warnings.simplefilter("ignore", ResourceWarning)

PREFIX = "aos72-test-"
SLEEP = ["sleep", "60"]

# 收到 n 次 tock 就自己結束的任務（S-11）；每收到一次記一行到槽裡的 seen.jsonl（任務自己的檔，換 run 不清）
WAITER = """import os, sys
sys.path[:0] = [%r, %r]
from aos7_fs import append_jsonl
from aos7_taskside import wait_tock
n, last = int(sys.argv[1]), 0
for _ in range(n):
    last = wait_tock(os.environ["AOS7_TASK"], last)
    append_jsonl(os.path.join(os.environ["AOS7_TASK"], "seen.jsonl"), {"round": last, "run": int(os.environ["AOS7_RUN"])})
""" % (LIB, TOOLS)


def kill_space_procs(root):
    """收掉環境變數 AOS7_ROOT 是 root（或在 root 底下）的所有程序（含 aos7-run）：測試收尾的保底。"""
    want = ("AOS7_ROOT=" + root).encode()
    groups = set()
    for p in os.listdir("/proc"):
        if not p.isdigit() or int(p) == os.getpid():
            continue
        try:
            with open("/proc/%s/environ" % p, "rb") as f:
                env = f.read().split(b"\0")
        except OSError:
            continue
        if any(e == want or e.startswith(want + b"/") for e in env):
            try:
                groups.add(os.getpgid(int(p)))
            except OSError:
                pass
    groups.discard(os.getpgid(0))
    for g in groups:
        try:
            os.killpg(g, signal.SIGKILL)
        except OSError:
            pass
    return groups


def _leads_group(p):
    try:
        return os.getpgid(p.pid) == p.pid
    except OSError:
        return False


class CoreCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix=PREFIX)
        self.root = os.path.realpath(self._tmp.name)
        self.procs = []
        self.addCleanup(self._remove_space)
        self.addCleanup(self._reap_all)

    def _reap_all(self):
        for p in self.procs:
            _proc.reap(p, group=_leads_group(p))
        for _ in range(3):
            if not kill_space_procs(self.root):
                break
            time.sleep(0.05)

    def _remove_space(self):
        for _ in range(5):
            shutil.rmtree(self.root, ignore_errors=True)
            if not os.path.exists(self.root):
                break
            time.sleep(0.1)
        self._tmp.cleanup()

    # ---------- 空間 ----------

    def mknode(self, nid="a", tasks=(), interval_ms=100, early=None, root=None, timeline=True, **extra):
        root = root or self.root
        node = root if nid == "." else os.path.join(root, nid)
        os.makedirs(os.path.join(node, ".aos"), exist_ok=True)
        if timeline:
            t = {"interval_ms": interval_ms}
            if early is not None:
                t["early_tock"] = early
            t.update(extra)
            write_json(os.path.join(node, ".aos", "timeline.json"), t)
        write_json(os.path.join(node, ".aos", "tasks.json"), {"tasks": list(tasks)})
        with open(os.path.join(node, "waiter.py"), "w") as f:
            f.write(WAITER)
        return node

    def set_tasks(self, node, tasks, **top):
        write_json(os.path.join(node, ".aos", "tasks.json"), dict(top, tasks=list(tasks)))

    def tasks(self, node):
        return (read_json(os.path.join(node, ".aos", "tasks.json"), {}) or {}).get("tasks")

    def slot(self, node, s):
        return aos7_task.slot_dir(node, s)

    def birth(self, node, s):
        return read_json(os.path.join(self.slot(node, s), "birth.json"), {}) or {}

    def exit_of(self, node, s):
        return read_json(os.path.join(self.slot(node, s), "exit.json"))

    def last_round(self, node):
        return read_json(os.path.join(node, ".aos", "last-round.json"), {}) or {}

    def round_json(self, node):
        return read_json(os.path.join(node, ".aos", "round.json"), {}) or {}

    def view(self, node, s, rnd=None):
        return aos7_task.judge(self.slot(node, s), node, s, rnd)

    # ---------- 程式 ----------

    def prog(self, name, *args, env=None, rc=0):
        p = subprocess.run([sys.executable, os.path.join(BIN, name), *args], capture_output=True, text=True,
                           timeout=30, env=dict(os.environ, **(env or {})))
        if rc is not None:
            self.assertEqual(p.returncode, rc, p.stderr)
        out = p.stdout.strip().splitlines()
        return json.loads(out[-1]) if out else None

    def tick(self, nid="a", **kw):
        return self.prog("aos7-tick", self.root, nid, **kw)

    def tock(self, nid="a", **kw):
        return self.prog("aos7-tock", self.root, nid, **kw)

    def itick(self, nid="a"):
        """同程序跑 tick（可以 mock 底下的函式）。"""
        return aos7_tick.tick(self.root, nid)

    def itock(self, nid="a", early=None):
        return aos7_tock.tock(self.root, nid, early)

    def round_trip(self, nid="a"):
        self.tick(nid)
        return self.tock(nid)

    def wait_for(self, pred, timeout=10, msg="timeout"):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            v = pred()
            if v:
                return v
            time.sleep(0.02)
        self.fail(msg)

    def wait_ended(self, node, s, run=None, timeout=10):
        def ok():
            ex = self.exit_of(node, s)
            return isinstance(ex, dict) and (run is None or ex.get("run") == run)
        self.wait_for(ok, timeout, "槽 %s 一直沒結束" % s)
        return self.exit_of(node, s)

    def wait_pid(self, node, s, timeout=10):
        return self.wait_for(lambda: read_json(os.path.join(self.slot(node, s), "pid.json")), timeout,
                             "槽 %s 一直沒有 pid.json" % s)


class DaemonCase(CoreCase):
    def start_daemon(self, root=None, env=None, register=()):
        root = root or self.root
        for nid in register:
            self.ctl("register", nid, root=root)
        p = subprocess.Popen([sys.executable, os.path.join(BIN, "aos7-daemon"), root],
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True,
                             env=dict(os.environ, **(env or {})))
        self.procs.append(p)
        _proc.track(self, p, grace=6, group=True)   # 先 SIGTERM（daemon 收自己的任務），逾時才 SIGKILL 整個群組
        return p

    def status(self, root=None):
        return read_json(os.path.join(root or self.root, ".aosd", "status.json"), {}) or {}

    def nstat(self, nid="a", root=None):
        return (self.status(root).get("nodes") or {}).get(nid) or {}

    def node_round(self, nid="a", root=None):
        return self.nstat(nid, root).get("round") or 0

    def ctl(self, op, *args, root=None, by=None):
        a = ["daemon", root or self.root, op, *args]
        if by:
            a += ["--by", by]
        return self.prog("aos7-ctl", *a)["wrote"]

    def receipt(self, path):
        """控制檔 path 的回條（ctl-done/ 同名）。"""
        return read_json(os.path.join(os.path.dirname(os.path.dirname(path)), "ctl-done", os.path.basename(path)))

    def wait_receipt(self, path, timeout=10):
        return self.wait_for(lambda: self.receipt(path) if not os.path.exists(path) else None, timeout,
                             "控制檔 %s 一直沒處理" % os.path.basename(path))

    def wait_round(self, n, nid="a", root=None, timeout=15):
        self.wait_for(lambda: self.node_round(nid, root) >= n, timeout, "%s 沒跑到第 %d 回合" % (nid, n))

    def stop_daemon(self, p, kill=True):
        self.ctl("stop", *(["--kill"] if kill else []))
        self.assertEqual(p.wait(15), 0)
