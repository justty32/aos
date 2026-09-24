"""daemon 測試共用：遵守控制 pipe 的假孩子、輪詢、以及拉 daemon／建池目標的基底類別。

_kernel_util 從這裡 import read_json、wait_for，這兩個行為不變。
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

LIB = Path(__file__).resolve().parents[1]
CLI = LIB.parent / "cli"
PY = sys.executable

# 每個孩子確實等 go，收到後才往 ready 檔追加一行（pid、pgid、sid、fd 1 指向哪、時間）。
# 模式寫 "@檔案" 時每次開機重讀那個檔，測試可以中途改孩子的行為。
#   normal：讀到 stop 或 EOF 退 0     exitN：馬上退 N     afterMS:N：活 MS 毫秒再退 N
#   kill：不理 TERM、不讀 stdin        term：TERM 時寫 .term 再退、不理 stop     epipe：關 fd 0、不理 TERM
CHILD = r'''
import json, os, signal, sys, time
mode, ready = sys.argv[1:3]
if mode.startswith('@'):
    mode = open(mode[1:]).read().strip()
while True:
    line = sys.stdin.buffer.readline()
    if not line:
        sys.exit(0)
    if json.loads(line).get('method') == 'go':
        break
if mode in ('kill', 'epipe'):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
def terminated(sig, frame):
    with open(ready + '.term', 'a') as f: f.write(json.dumps(time.monotonic()) + '\n')
    sys.exit(0)
if mode == 'term':
    signal.signal(signal.SIGTERM, terminated)
if mode == 'epipe':
    os.close(0)
with open(ready, 'a') as f:
    f.write(json.dumps({'pid': os.getpid(), 'pgid': os.getpgrp(), 'sid': os.getsid(0),
                        'fd1': os.readlink('/proc/self/fd/1'), 'at': time.monotonic()}) + '\n')
if mode.startswith('exit'):
    sys.exit(int(mode[4:]))
if mode.startswith('after'):
    ms, code = mode[5:].split(':')
    time.sleep(int(ms) / 1000)
    sys.exit(int(code))
if mode in ('kill', 'epipe'):
    while True: time.sleep(.01)
while True:
    line = sys.stdin.buffer.readline()
    if not line:
        sys.exit(0)
    if json.loads(line).get('method') == 'stop' and mode != 'term':
        sys.exit(0)
'''


def wait_for(predicate, timeout=6):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.005)
    raise AssertionError("等不到行程或檔案狀態")


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, value):
    path = Path(path)
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(json.dumps(value))
    os.replace(tmp, path)
    return str(path)


INFO = {"_metainfo": {"_type": "daemon", "_version": 2}, "poll_ms": 5, "restart_delay_ms": 80,
        "restart_max_ms": 60000, "stable_ms": 10000, "spawn_per_sec": 1000, "max_children": 200,
        "stop_wait_ms": 80, "kill_wait_ms": 80}


class DaemonCase(unittest.TestCase):
    """一個暫存家 D、假孩子腳本、池的目標樣板；tearDown 只砍自己暫存目錄底下的行程。"""

    PREFIX = "aos-daemon-test-"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix=self.PREFIX)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "D"
        self.home.mkdir()
        self.info = dict(INFO)
        write_json(self.home / "info.json", self.info)
        self.child = self.root / "child.py"
        self.child.write_text(CHILD)
        self.addCleanup(self.kill_leftovers)

    def set_info(self, **changes):
        self.info.update(changes)
        write_json(self.home / "info.json", self.info)

    def kill_leftovers(self):
        """只砍命令列含這個暫存目錄的行程（別隊也在跑）。"""
        mine = str(self.root)
        for entry in os.listdir("/proc"):
            if not entry.isdigit() or int(entry) == os.getpid():
                continue
            try:
                cmd = Path("/proc/%s/cmdline" % entry).read_bytes()
            except OSError:
                continue
            if mine.encode() in cmd:
                try:
                    os.kill(int(entry), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass

    # ---- 目標 ----

    def targets(self, n, mode="normal", pool="p"):
        """第 i 號的 inst 在 t-<pool>/<i>.json；回樣板。mode 是 "@path" 就每次開機重讀。"""
        folder = self.root / ("t-" + pool)
        folder.mkdir(exist_ok=True)
        (self.root / ("ready-" + pool)).mkdir(exist_ok=True)
        for i in range(n):
            write_json(folder / ("%d.json" % i),
                       {"argv": [PY, str(self.child), mode, str(self.ready(pool, i))]})
        return str(folder / "{name}.json")

    def ready(self, pool, i):
        return self.root / ("ready-" + pool) / ("%d.jsonl" % i)

    def starts(self, pool, i):
        path = self.ready(pool, i)
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    # ---- daemon ----

    def start(self, wait=True):
        log = open(self.root / "daemon.log", "ab")
        self.addCleanup(log.close)
        proc = subprocess.Popen([PY, str(CLI / "aos-daemon"), "boot", "--target", str(self.home)],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log,
                                start_new_session=True)
        self.proc = proc
        def cleanup():
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=4)
        self.addCleanup(cleanup)
        if wait:
            wait_for(lambda: self.state().get("pid") == proc.pid)
        return proc

    def log(self):
        path = self.root / "daemon.log"
        return path.read_text() if path.exists() else ""

    def state(self):
        return read_json(self.home / "state.json", {})

    def call(self, method, params=None):
        import aos_client
        return aos_client.call(self.home, method, params, timeout_ms=6000, poll_ms=5)

    def scale(self, pool="p", count=1, owner="/k", **extra):
        params = dict({"pool": pool, "owner": owner, "count": count}, **extra)
        return self.call("scale", params)

    def ok(self, response):
        self.assertIn("result", response, response)
        return response["result"]

    def code(self, response):
        self.assertIn("error", response, response)
        return (response["error"].get("data") or {}).get("code", response["error"]["code"])

    def summary(self, pool="p"):
        return read_json(self.home / "pools" / pool / "summary.json")

    def kid(self, pool, i):
        return read_json(self.home / "pools" / pool / "kids" / ("%d.json" % i))

    def running(self, pool, n):
        """等到那池 running 恰好 n 顆（summary）。"""
        return wait_for(lambda: (self.summary(pool) or {}).get("running") == n and self.summary(pool))

    def halt(self):
        import aos_client, aos_home
        aos_home.post_request(self.home, aos_client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        self.assertEqual(self.proc.wait(timeout=6), 0, self.log())
        self.assertEqual(self.state()["pid"], 0)
