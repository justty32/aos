"""kernel 與端到端測試共用的真 daemon／cpu 家及有上限輪詢（proto5-2 版）。

跟 proto5 版的差別（照 proto5-2 spec/kernel-info、kernel-cli init、handoff、daemon-home）：
- K 家用 `aos-kernel init --config` 建，info 是第 2 版的**池表**：
  `initialize(pools=None, **settings)`；`pools` 省略＝`POOLS`（`default` 1 顆＋`llm` 1 顆，
  等於 proto5 的 `{"k": kernel, "0": {}, "llm": {"pool": "llm"}}`）。kernel 池 init 自己補。
  `settings` 蓋在頂層（`tick_ms`、`bad_after`、`done_exit`、`daemon`、`cpu`…）；預設
  `tick_ms 5`、`interval_ms 5`、`bad_after 3`、`cpu.poll_ms 5`、`daemon`＝這個測試的 D。
  池寫法例：`{"default": {"count": 2}, "llm": {"count": 1, "envs": {"AOS_LLM_CONFIG": "/abs/llm.json"}}}`。
- `boot()` 只跑 `aos-kernel boot --target K`（daemon 從 info 拿，`--daemon-target` 拿掉），等 daemon 開的第 1 格。
- （09-24 one-boot）沒有 kernel 池了：`init` 不再補 kernel 池；帳本是 `K/ledger.sqlite`，`state()` 讀它（同第 2 版的 dict 形狀，
  `on` 從 busy 反推）；`put_state(dict)` 整份換掉帳本。
- daemon 的 info 是第 2 版鍵：`DAEMON_INFO`（重拉起點 50 ms、上限 400 ms、poll 5 ms、每秒可拉 1000 顆）。
- daemon 的孩子不再在 `D/state.json`：改用下面幾個 helper（底下只呼叫 `aos_daemon.pool_summary`／`pool_kid`）。

新 helper（pool 一律是 **kernel 的池名**，會自己換成 dpool）：
  set_info(**top)／set_pool(pool, **fields)／set_count(pool, n)   改 K/info.json（tick 下一格照做）
  dpool(pool)                    這池在 daemon 那邊叫什麼（info 的 dpool，沒寫＝池名）
  summary(pool)                  aos_daemon.pool_summary；池不在回 None
  kid(pool, i)                   aos_daemon.pool_kid；沒拉過回 None
  kid_pid(pool, i)               那顆 running 時的 pid，否則 None
  wait_running(pool, n)          等到摘要 count＝n 且 running＝n（n＝0 也可以：摘要消失也算）
  wait_gone(pool)                等 daemon 那池整個拿掉（summary 不在）
  cpu_home(pool, i)              K/pools/<pool>/cpus/<i>
  kernel_stop()                  aos-kernel halt，等 phase＝stopped 且每池在 daemon 那邊都消失
  daemon_stop()                  放 stop、等 daemon 退 0
  dstate()                       D/state.json（只剩 pid／stopping／current）
舊 helper 照留：write、cli、raw_cli、good_cli、state、call、add、job、start_daemon、setup_running(pools=…, **settings)。
收尾：daemon 先 TERM（走停機階梯），不行就 KILL＋把 kids 檔記的 pid 整組 KILL；最後砍命令列含暫存目錄的殘留行程。
"""
import copy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

import aos_client
import aos_daemon
import aos_home
import aos_kernel_store
from _daemon_util import read_json, wait_for

CLI = Path(__file__).resolve().parents[2] / "cli"
PY = sys.executable

POOLS = {"default": {"count": 1}, "llm": {"count": 1}}
DAEMON_INFO = {"_metainfo": {"_type": "daemon", "_version": 2}, "poll_ms": 5,
               "restart_delay_ms": 50, "restart_max_ms": 400, "stable_ms": 10000,
               "spawn_per_sec": 1000, "max_children": 200, "stop_wait_ms": 150, "kill_wait_ms": 150}


class KernelCase(unittest.TestCase):
    PREFIX = "aos-kernel-test-"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix=self.PREFIX)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "K"
        self.daemon = self.root / "D"
        self.daemon.mkdir()
        self.write(self.daemon / "info.json", dict(DAEMON_INFO))
        self.groups = set()
        self.daemon_process = None
        self.info = None
        self.addCleanup(self.cleanup)

    def write(self, path, obj):
        aos_home.write_json(path, obj)
        return str(path)

    # ---- aos-kernel 命令列 ----

    def cli(self, *args, timeout=10):
        """cli(子命令, K, 其他…)：第二個參數是 K 家時換成 --target K（09-24 fix-r4 起 K 不是位置參數）。"""
        args = [str(a) for a in args]
        if len(args) >= 2 and not args[1].startswith("-"):
            args = [args[0], "--target", args[1], *args[2:]]
        return self.raw_cli(*args, timeout=timeout)

    def raw_cli(self, *args, timeout=10, cwd=None, env=None):
        """原樣把參數交給 aos-kernel，不替你補 --target。"""
        return subprocess.run([PY, str(CLI / "aos-kernel"), *map(str, args)], cwd=cwd, env=env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)

    def good_cli(self, *args, timeout=10):
        result = self.cli(*args, timeout=timeout)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    # ---- K 家 ----

    def initialize(self, pools=None, **settings):
        """aos-kernel init --config：池表＋測試用的快設定；回（讀回來的）info。"""
        if "cpus" in settings:
            raise TypeError("proto5 的 cpus= 已拿掉：改傳 pools（例 {'default': {'count': 1}}），kernel 池不用寫")
        config ={"pools": copy.deepcopy(POOLS if pools is None else pools), "daemon": str(self.daemon),
                  "tick_ms": 5, "interval_ms": 5, "bad_after": 3, "cpu": {"poll_ms": 5}}
        config.update(settings)
        path = self.write(self.root / "kernel-config.json", config)
        self.good_cli("init", self.home, "--config", path)
        self.info = read_json(self.home / "info.json")
        return self.info

    def set_info(self, **top):
        self.info = read_json(self.home / "info.json")
        self.info.update(top)
        self.write(self.home / "info.json", self.info)

    def set_pool(self, pool, **fields):
        """改一池的欄位（池不在就新增）；值 None＝拿掉那個鍵。整池拿掉用 drop_pool。"""
        self.info = read_json(self.home / "info.json")
        config = self.info["pools"].setdefault(pool, {"count": 0})
        for key, value in fields.items():
            if value is None:
                config.pop(key, None)
            else:
                config[key] = value
        self.write(self.home / "info.json", self.info)

    def set_count(self, pool, n):
        self.set_pool(pool, count=n)

    def drop_pool(self, pool):
        self.info = read_json(self.home / "info.json")
        self.info["pools"].pop(pool, None)
        self.write(self.home / "info.json", self.info)

    def cpu_home(self, pool, i):
        return self.home / "pools" / pool / "cpus" / str(i)

    # ---- daemon ----

    def start_daemon(self):
        log = open(self.root / "daemon.log", "ab")
        self.addCleanup(log.close)
        self.daemon_process = subprocess.Popen(
            [PY, str(CLI / "aos-daemon"), "boot", "--target", str(self.daemon)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log, start_new_session=True)
        wait_for(lambda: self.dstate().get("pid") == self.daemon_process.pid)
        return self.daemon_process

    def dpool(self, pool):
        info = self.info or read_json(self.home / "info.json")
        return (info["pools"].get(pool) or {}).get("dpool", pool)

    def summary(self, pool):
        return aos_daemon.pool_summary(str(self.daemon), self.dpool(pool))

    def kid(self, pool, i):
        return aos_daemon.pool_kid(str(self.daemon), self.dpool(pool), i)

    def kid_pid(self, pool, i):
        kid = self.kid(pool, i)
        return kid["pid"] if kid and kid.get("state") == "running" else None

    def wait_running(self, pool, n, timeout=8):
        def ok():
            s = self.summary(pool)
            if n == 0 and s is None:
                return True
            return s is not None and s.get("count") == n and s.get("running") == n and s.get("killing") == 0 \
                and s.get("draining") == 0 and s
        return wait_for(ok, timeout=timeout)

    def wait_gone(self, pool, timeout=8):
        return wait_for(lambda: self.summary(pool) is None, timeout=timeout)

    def daemon_pids(self):
        """kids 檔記著的、running／killing 的 pid（收尾兜底用）。"""
        pids = set()
        for leaf in (self.daemon / "pools").glob("*/kids/*.json"):
            record = read_json(leaf, {})
            if record.get("state") in ("running", "killing") and type(record.get("pid")) is int:
                pids.add(record["pid"])
        return pids

    # ---- kernel ----

    def boot(self):
        chain = self.state().get("chain")
        result = self.good_cli("boot", self.home, timeout=20)
        self.info = read_json(self.home / "info.json")
        wait_for(lambda: self.state().get("chain") != chain and self.state().get("last_seq", 0) >= 1)
        return result

    def setup_running(self, pools=None, **settings):
        self.initialize(pools, **settings)
        self.start_daemon()
        return self.boot()

    def state(self):
        try:
            return aos_kernel_store.read(self.home, {})
        except aos_home.HomeError:
            return {}

    def put_state(self, state):
        aos_kernel_store.write(self.home, state)

    def dstate(self):
        return read_json(self.daemon / "state.json", {})

    def call(self, method, params=None, **kwargs):
        return aos_client.call(self.home, method, params, timeout_ms=kwargs.pop("timeout_ms", 5000), poll_ms=5, **kwargs)

    def add(self, target, name="job", **options):
        response = self.call("add", dict(target=str(target), name=name, **options))
        self.assertEqual(response.get("result", {}).get("name"), name, response)
        return response

    def job(self, source="pass", name="job", **extra):
        return self.write(self.root / (name + ".json"), dict(argv=[PY, "-c", source], **extra))

    def kernel_stop(self, timeout=10):
        self.good_cli("halt", self.home, timeout=timeout + 5)
        wait_for(lambda: self.state().get("phase") == "stopped", timeout=timeout)
        where = {(e["daemon"], e["dpool"]) for e in (self.state().get("pools") or {}).values()}
        wait_for(lambda: all(aos_daemon.pool_summary(d, p) is None for d, p in where), timeout=timeout)

    def daemon_stop(self):
        aos_home.post_request(self.daemon, aos_client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        self.assertEqual(self.daemon_process.wait(timeout=8), 0)

    # ---- 收尾 ----

    def cleanup(self):
        daemon = self.daemon_process
        pids = self.daemon_pids() | self.groups
        if daemon is not None and daemon.poll() is None:
            try:
                daemon.terminate()
                daemon.wait(timeout=5)
            except subprocess.TimeoutExpired:
                daemon.kill()
                daemon.wait(timeout=4)
                for pid in pids:
                    try:
                        os.killpg(pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        pass
        for pid in self.groups:
            try:
                os.killpg(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        self.kill_leftovers()

    def kill_leftovers(self):
        """只砍命令列含這個暫存目錄的行程（tick、工作；別隊也在跑）。"""
        mine = str(self.root).encode()
        for entry in os.listdir("/proc"):
            if not entry.isdigit() or int(entry) == os.getpid():
                continue
            try:
                cmd = Path("/proc/%s/cmdline" % entry).read_bytes()
            except OSError:
                continue
            if mine in cmd:
                try:
                    os.kill(int(entry), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass


def isolated_test(module, classname, method):
    """把會製造孤兒的單條測試放進自己當 init 的 driver，連 zombie 都收乾淨。"""
    script = r'''
import ctypes, os, signal, sys, time, unittest
if ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0):
    raise OSError(ctypes.get_errno(),'prctl')
os.environ['AOS_TEST_SUBREAPER']='1'
suite=unittest.defaultTestLoader.loadTestsFromName(sys.argv[1])
result=unittest.TextTestRunner().run(suite)
until=time.monotonic()+3
while time.monotonic()<until:
    try: pid,_=os.waitpid(-1,os.WNOHANG)
    except ChildProcessError: break
    if not pid: time.sleep(.005)
sys.exit(not result.wasSuccessful())
'''
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(CLI.parent / "lib"), str(Path(__file__).parent)]))
    return subprocess.run([PY, "-c", script, "%s.%s.%s" % (module, classname, method)],
                          capture_output=True, text=True, env=env, timeout=30)
