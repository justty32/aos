"""kernel 隊測試用的假 daemon：只處理 D/requests/ 的 scale 與 ack，不拉任何 cpu。

照 proto5-2 spec/protocol.md §1 回音；寫 D/pools/<dpool>/pool.json 與 summary.json；count 0 時刪 summary（池拿掉）。
可設定：某池下一張回指定錯誤、整個暫停不回、把某張單「吃掉」（刪單不回音，模擬兩個檔都不在）、
count 0 時先留著 summary（照真 daemon 的形狀：count 0、running 0、draining 1）模擬還在收孩子；
count 0 時把 summary 寫壞（garble）模擬摘要在但讀不到。
可一步一步呼叫 process()，也可 start() 在背景執行緒自己跑（boot 要等回音時用）。
"""
import fcntl
import json
import os
from pathlib import Path
import shutil
import threading
import time

import aos_daemon
import aos_home


def _pool_summary(home, dpool):
    """daemon 隊還沒交 aos_daemon.pool_summary 前的替身（同約定：不在或壞了回 None）。"""
    try:
        return json.loads((Path(home) / "pools" / dpool / "summary.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def install():
    if not hasattr(aos_daemon, "pool_summary"):
        aos_daemon.pool_summary = _pool_summary


class FakeDaemon:
    def __init__(self, home, alive=True):
        install()
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        aos_home.ensure_queue(self.home)
        (self.home / "pools").mkdir(exist_ok=True)
        aos_home.write_json(self.home / "info.json", {"_metainfo": {"_type": "daemon", "_version": 2}})
        self.errors = {}        # dpool -> [code, ...]：下一張依序回這些錯
        self.swallow = set()    # 單名：刪掉不回音
        self.linger = set()     # dpool：count 0 時先留著 summary（count 0、running 0、draining 1）
        self.garble = set()     # dpool：count 0 時 summary 寫成壞 JSON（摘要在但讀不到）
        self.paused = False
        self.stopping = False
        self.seen = []          # 處理過的 (單名, params)
        self.lock_fd = None
        self._thread, self._halt = None, threading.Event()
        self._mutex = threading.Lock()
        if alive:
            self.set_alive(True)

    # ---- 活不活（aos_daemon.is_alive 用 flock 探測） ----
    def set_alive(self, alive):
        if alive and self.lock_fd is None:
            self.lock_fd = os.open(self.home / ".daemon.lock", os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o644)
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX)
        elif not alive and self.lock_fd is not None:
            os.close(self.lock_fd)
            self.lock_fd = None

    # ---- 讀 ----
    def pool(self, dpool):
        try:
            return aos_home.read_json(self.home / "pools" / dpool / "pool.json")
        except aos_home.HomeError:
            return None

    def summary(self, dpool):
        return _pool_summary(self.home, dpool)

    def gone(self, dpool):
        """池完全拿掉：模擬 daemon 收完孩子（刪 summary、pool.json、資料夾）。"""
        shutil.rmtree(self.home / "pools" / dpool, ignore_errors=True)

    # ---- 處理 ----
    def process(self):
        with self._mutex:
            if self.paused:
                return []
            done = []
            for path in sorted((self.home / "requests").glob("*.json")):
                name = path.name
                try:
                    obj = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if name.startswith("ack-"):
                    (self.home / "responses" / obj["params"]["name"]).unlink(missing_ok=True)
                    path.unlink(missing_ok=True)
                    continue
                if name in self.swallow:
                    path.unlink(missing_ok=True)
                    done.append(name)
                    continue
                response = self._scale(obj)
                aos_home.write_json(self.home / "responses" / name, response)
                path.unlink(missing_ok=True)
                self.seen.append((name, obj.get("params")))
                done.append(name)
            return done

    def _error(self, rid, code, msg=""):
        if code == "-32602":
            return aos_home.params_error(rid, msg or "形狀不合", ["params"])
        return aos_home.error_response(rid, -32000, msg or code, {"code": code})

    def _scale(self, obj):
        rid, p = obj.get("id"), obj.get("params") or {}
        if obj.get("method") != "scale":
            return aos_home.error_response(rid, -32601, "不認得 method")
        dpool = p.get("pool")
        queued = self.errors.get(dpool)
        if queued:
            return self._error(rid, queued.pop(0))
        count, skip = p.get("count"), p.get("skip", [])
        if type(count) is not int or count < 0 or not isinstance(dpool, str):
            return self._error(rid, "-32602")
        if self.stopping:
            return self._error(rid, "Stopping")
        current = self.pool(dpool)
        if current is not None and current["owner"] != p.get("owner"):
            return self._error(rid, "NameTaken", "池 %s 的 owner 是 %s" % (dpool, current["owner"]))
        if current is not None and "decl" in p and current.get("decl") is not None and p["decl"] < current["decl"]:
            return self._error(rid, "Stale", "過期的宣告")
        if current is None and count == 0:
            return aos_home.result_response(rid, {"pool": dpool, "count": 0, "ver": 0})
        ver = (current or {}).get("ver", 0)
        if current is None or (current["count"], current["skip"]) != (count, skip):
            ver += 1
        decl = {"pool": dpool, "owner": p.get("owner"), "count": count, "skip": list(skip), "ver": ver,
                "target": p.get("target", (current or {}).get("target")),
                "home": p.get("home", (current or {}).get("home")), "decl": p.get("decl")}
        d = self.home / "pools" / dpool
        d.mkdir(parents=True, exist_ok=True)
        aos_home.write_json(d / "pool.json", decl)
        if count == 0 and dpool in self.garble:
            (d / "summary.json").write_text("{壞")
        elif count == 0 and dpool not in self.linger:
            self.gone(dpool)
        else:
            aos_home.write_json(d / "summary.json", {
                "pool": dpool, "owner": p.get("owner"), "count": count, "ver": ver,
                "running": count, "restarting": 0, "pending": 0, "dead": 0, "failed": 0,
                "killing": 0, "draining": 0 if count else 1, "updated": time.time()})
        return aos_home.result_response(rid, {"pool": dpool, "count": count, "ver": ver})

    # ---- 背景跑 ----
    def start(self, poll=.002):
        self._halt.clear()
        def loop():
            while not self._halt.is_set():
                self.process()
                time.sleep(poll)
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        if self._thread is not None:
            self._halt.set()
            self._thread.join(5)
            self._thread = None

    def close(self):
        self.stop()
        self.set_alive(False)


# ---- 測試基底：假 daemon＋直接呼叫 tick，一格一格跑 ----
import hashlib
import tempfile
import unittest

import aos_kernel_boot
import aos_kernel_engine
import aos_kernel_info


class Crash(BaseException):
    """模擬 kernel 在某一步被 KILL：不被任何 except 接住，記憶體裡的狀態全丟。"""


class FakeCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aos-kfake-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.K = self.root / "K"
        self.fake = FakeDaemon(self.root / "D")
        self.addCleanup(self.fake.close)
        self.D = str(self.fake.home)
        self.seq = 0
        self.n = 0

    # ---- 家 ----
    def init(self, pools=None, **settings):
        config = {"pools": pools if pools is not None else {"default": {"count": 2}},
                  "tick_ms": 0, "interval_ms": 0, "bad_after": 3, **settings}
        config.setdefault("daemon", self.D)
        aos_kernel_info.init(self.K, config)

    def info(self):
        return aos_home.read_json(self.K / "info.json")

    def edit_info(self, **pools):
        """edit_info(default={"count": 3})：整格換掉；值 None＝把池刪掉。"""
        info = self.info()
        for name, config in pools.items():
            if config is None:
                info["pools"].pop(name, None)
            else:
                info["pools"][name] = config
        aos_home.write_json(self.K / "info.json", info)

    def state(self):
        return aos_home.read_state(self.K)

    def boot(self, wait_ms=5000):
        self.fake.start()
        try:
            aos_kernel_boot.boot(self.K, wait_ms)
        finally:
            self.fake.stop()
        self.seq = 0

    def tick(self, process=True):
        """跑一格（直接呼叫 tick），然後讓假 daemon 處理一輪。"""
        self.seq += 1
        state = self.state()
        code = aos_kernel_engine.tick(self.K, state["chain"], self.seq)
        self.assertEqual(code, 0)
        if process:
            self.fake.process()
        return self.state()

    def ticks(self, n):
        for _ in range(n):
            state = self.tick()
        return state

    def settle(self, n=3):
        """boot 後跑幾格讓池宣告完（scale 送、回音、收）。"""
        return self.ticks(n)

    # ---- 交件與 cpu 模擬 ----
    def add(self, name=None, pool="default", once=False, **params):
        self.n += 1
        req = "cli-%d-%d.json" % (self.n, os.getpid())
        p = {"target": str(self.root / "work.json"), "pool": pool, "once": once, **params}
        if name is not None:
            p["name"] = name
        aos_home.post_request(self.K, req, {"jsonrpc": "2.0", "id": req[:-5], "method": "add", "params": p})
        return req

    def rm(self, name):
        self.n += 1
        req = "cli-%d-%d.json" % (self.n, os.getpid())
        aos_home.post_request(self.K, req, {"jsonrpc": "2.0", "id": req[:-5], "method": "rm", "params": {"name": name}})
        return req

    def stop_kernel(self):
        aos_home.post_request(self.K, "stop-cli-%d.json" % os.getpid(), {"jsonrpc": "2.0", "method": "stop"})

    def reply(self, req):
        return aos_home.read_json(self.K / "responses" / req)

    def cpu(self, key):
        pool, i = key.split("/")
        return self.K / "pools" / pool / "cpus" / i

    def respond(self, key, code=0, notify=True, result=None, req=None):
        """模擬 cpu：寫回音 → 刪原單 → 丟 resp- 通知（cpu-notify §2）。"""
        home = self.cpu(key)
        req = req or self.state()["busy"][key]["req"]
        body = {"jsonrpc": "2.0", "id": req[:-5], "result": result or {"kind": "exit", "code": code}}
        aos_home.write_json(home / "responses" / req, body)
        (home / "requests" / req).unlink(missing_ok=True)
        if notify:
            self.notify(home, req)
        return req

    def notify(self, home, req, raw=None):
        digest = hashlib.sha256(("%s\n%s" % (home, req)).encode()).hexdigest()[:16]
        name = "resp-%s.json" % digest
        obj = raw if raw is not None else {"jsonrpc": "2.0", "method": "responded", "params": {"home": str(home), "name": req}}
        if isinstance(obj, str):
            (self.K / "requests" / name).write_text(obj)
        else:
            aos_home.write_json(self.K / "requests" / name, obj)
        return name

    def log_events(self):
        path = self.K / "kernel.log"
        if not path.exists():
            return []
        return [e for line in path.read_text().splitlines() for e in json.loads(line)["events"]]
