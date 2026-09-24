"""kernel 一格（kernel/tick.md）：只碰有事的 cpu——有通知的、上一格剛派的、輪到巡檢的。

2026-09-24 one-boot：一格由 daemon 開（定時、或 K/requests/ 有新檔），不再放下一格、不再睡 tick_ms；
一開始拿 K/.tick.lock（同時只准一格；拿不到退 75），序號＝帳本 last_seq＋1。
提交點（kernel/ledger.md）：A＝第 4 步出貨完；B＝第 5～9 步全部決定完；C＝第 10 步出貨完。每個提交點一筆 sqlite 交易。
"""
import fcntl
import itertools
import json
import os
from pathlib import Path
import signal
import time

import aos_home
import aos_hops
import aos_kernel_store
from aos_kernel_info import (
    KERNEL_POOL, KernelError, _put, classify, cpu_key, load_info, split_key,
)
from aos_kernel_ledger import KernelLedger
from aos_kernel_pools import PoolsMixin

LOCK = ".tick.lock"
BUSY_EXIT = 75   # 鎖被佔（別的 tick 正在跑）：daemon 不算失敗


class Kernel(PoolsMixin, KernelLedger):
    # ---- 第 5 步：讀 K/requests/，列一次目錄照前綴分 ----
    def read_requests(self):
        req_dir = self.home / "requests"
        acks, stops, resps, calls = [], [], [], []
        for name in sorted(os.listdir(req_dir)):
            if name.startswith(".") or name.endswith(".tmp") or not name.endswith(".json"):
                continue
            bucket = (acks if name.startswith("ack-") else stops if name.startswith("stop-")
                      else resps if name.startswith("resp-") else calls)
            bucket.append(name)
        for name in acks:
            self._ack_control(req_dir / name)
        for name in stops:
            self._stop_control(req_dir / name)
        for name in calls:
            env = aos_home.read_request(req_dir / name)
            if aos_hops.on():
                params = env.params if isinstance(env.params, dict) else {}
                aos_hops.mark("kernel", "req", name=name, method=env.method, proc=params.get("name"), wake=params.get("wake"))
            self.apply_syscall(env)
        notified = []
        for name in resps:
            key = self._notification(req_dir / name)
            if key is not None:
                notified.append(key)
        return notified

    def _ack_control(self, path):
        """範式 §3.3（同 aos_home.scan_controls 的 ack 那半）：先刪回音再刪 ack 檔。"""
        env = aos_home.read_request(path)
        response = env.error
        if response is None:
            if env.method != "ack" or not env.notify:
                response = aos_home.error_response(env.id, -32600, "控制前綴必須對應同名 notification")
            else:
                try:
                    if not isinstance(env.params, dict):
                        raise aos_home.HomeError("FieldTypeMismatch", "ack.params 必須是物件")
                    name = aos_home.validate_name(env.params.get("name"))
                except aos_home.HomeError as exc:
                    response = aos_home.params_error(env.id, exc.msg, ["params", "name"])
                else:
                    (self.home / "responses" / name).unlink(missing_ok=True)
        if response is not None and not env.notify:
            aos_home.write_json(self.home / "responses" / path.name, response)
        path.unlink(missing_ok=True)

    def _stop_control(self, path):
        """stop：改 phase（提交點 3 才落帳）；原檔進 deletes，崩在提交前下一格會再看到它。"""
        if path.name in self.state["deletes"]:
            return
        env = aos_home.read_request(path)
        if env.error is None and env.method == "stop" and env.notify:
            self.start_stopping()
        elif not env.notify:
            response = env.error or aos_home.error_response(env.id, -32600, "控制前綴必須對應同名 notification")
            self.state["replies"].append({"name": path.name, "id": env.id, "body": {"error": response["error"]}})
        self.state["deletes"].append(path.name)

    def _notification(self, path):
        """resp- 通知 → 'P/<i>'；舊的、壞的只刪（壞的記 log），絕不讓這格退 1（kernel-tick 第 6 步）。"""
        if path.name in self.state["deletes"]:
            return None
        self.state["deletes"].append(path.name)
        try:
            env = aos_home.read_request(path)
        except aos_home.HomeError as exc:
            self.events.append({"event": "bad_notify", "file": path.name, "why": exc.msg})
            return None
        why, key = None, None
        params = env.params if isinstance(env.params, dict) else {}
        if env.error is not None or not env.notify or env.method != "responded":
            why = "不是 responded notification"
        elif not isinstance(params.get("home"), str) or not isinstance(params.get("name"), str):
            why = "params.home／name 必須是字串"
        else:
            try:
                parsed = self._notified_cpu(params["home"])
            except (ValueError, OSError) as exc:  # astra P7：\0、怪路徑…解析本身出錯也只是壞通知
                parsed, why = None, "home 解析失敗：%s" % type(exc).__name__
            if why is None and parsed is None:
                why = "home 不在 K/pools/*/cpus/ 底下"
            elif why is None:
                key = cpu_key(*parsed)
                slot = self.state["busy"].get(key)
                if slot is None:
                    why = "busy 沒有 %s" % key
                elif slot["req"] != params["name"]:
                    return None  # 舊通知：只刪不查
        if why is not None:
            self.events.append({"event": "bad_notify", "file": path.name, "why": why})
            return None
        return key

    def _notified_cpu(self, raw):
        """通知的 home → (P, i)；不在 K/pools/*/cpus/ 底下回 None。
        cpu 報的是它 getcwd() 的實際路徑，K 若經過 symlink 給的就跟 self.home 字面不同：字面比不上再用 realpath 比（D-80）。"""
        for home, pools in ((Path(os.path.normpath(raw)), self.home / "pools"),
                            (Path(os.path.realpath(raw)), Path(os.path.realpath(self.home / "pools")))):
            if home.parent.name == "cpus" and home.parent.parent.parent == pools:
                parsed = split_key("%s/%s" % (home.parent.parent.name, home.name))
                if parsed is not None:
                    return parsed
        return None

    # ---- 第 6 步：收回音 ----
    def collect(self, notified):
        busy = self.state["busy"]
        recent, self.state["recent"] = self.state["recent"], []
        sweep = list(itertools.islice(busy, self.info["sweep"]))
        for key in sweep:  # 查完的搬到尾巴，下一格輪別人
            busy[key] = busy.pop(key)
        for key in dict.fromkeys([*notified, *recent, *sweep]):
            slot = busy.get(key)
            if slot is None:
                continue
            req_exists, resp_exists = self.work_exists(key, slot["req"])
            if req_exists:
                continue
            name = slot["proc"]
            if not resp_exists:
                if slot["discard"]:
                    # D-27：rm 過、兩個檔都不在＝從沒放出去；直接取消，不卡住那顆。
                    self.state["procs"].pop(name, None)
                    self.release(key)
                else:
                    self._post_work(key, slot["req"], self.state["procs"][name])
                continue
            response = aos_home.read_json(self.cpu_home(key) / "responses" / slot["req"])
            proc = self.state["procs"][name]
            self.events.append({"event": "response", "proc": name, "cpu": key,
                                "response": {k: response[k] for k in ("result", "error") if k in response}})
            if aos_hops.on():
                result = response.get("result")
                aos_hops.mark("kernel", "resp", proc=name, cpu=key, code=result.get("code") if isinstance(result, dict) else None)
            if slot["discard"]:
                del self.state["procs"][name]
            elif proc["once"]:
                self._reply(proc["pending"], {k: response[k] for k in ("result", "error") if k in response})
                del self.state["procs"][name]
            else:
                proc = classify(proc, response, self.info, self.now)
                self.state["procs"][name] = proc
                if proc["status"] == "queued":
                    self.enqueue(name)
                elif proc["status"] == "bad":
                    self.events.append({"event": "bad", "proc": name, "fails": proc["fails"], "bad_after": self.info["bad_after"]})
            self.state["acks"].append({"home": str(self.cpu_home(key)), "name": slot["req"]})
            self.release(key)

    def _post_work(self, key, req, proc):
        params = {k: proc[k] for k in ("target", "dir_target", "args", "timeout_ms") if k in proc}
        _put(self.cpu_home(key), req, {"jsonrpc": "2.0", "id": req[:-5], "method": "aos-exec", "params": params})

    # ---- 第 8 步：派工（只改記憶體；提交點 3 之後才放檔） ----
    def dispatch(self):
        if self.state["phase"] != "running":
            return
        self.promote_delayed()
        for pool, queue in self.state["ready"].items():
            entry = self.state["pools"].get(pool)
            if entry is None or pool == KERNEL_POOL:
                continue
            free = entry["free"]
            while queue and free:
                name = self.pop_ready(pool)
                if name is None:
                    break
                i = free.pop()
                key = cpu_key(pool, i)
                req = "k-%s-%d-%s-%d.json" % (self.state["chain"], self.seq, pool, i)
                self.state["procs"][name]["status"] = "running"
                self.state["procs"][name].pop("parked", None)  # 09-24 停車：派出去就不算停著（park_ms 到了自己醒的）
                self.state["busy"][key] = {"req": req, "proc": name, "discard": False}
                self.state["on"][name] = key
                self.state["recent"].append(key)
                self.events.append({"event": "dispatch", "proc": name, "cpu": key, "request": req})

    def post_dispatched(self):
        for key in self.state["recent"]:
            slot = self.state["busy"].get(key)
            if slot is not None:
                self._post_work(key, slot["req"], self.state["procs"][slot["proc"]])
                aos_hops.mark("kernel", "dispatch", proc=slot["proc"], cpu=key, request=slot["req"])

    # ---- 第 9 步：停機 ----
    def stopping(self):
        st = self.state
        if st["phase"] != "stopping":
            return
        if not st["halting"]:
            if (st["busy"] or any(st[k] for k in ("acks", "replies", "deletes", "sends")) or
                    any(p["pending"] is not None for p in st["procs"].values()) or
                    any(e["pending"] is not None for p, e in st["pools"].items() if p != KERNEL_POOL)):
                return
            st["halting"] = True
            self.events.append({"event": "halting"})
        if not self.pools_quiet():
            return
        st["phase"] = "stopped"
        ticker = st.get("ticker")
        if ticker:
            # one-boot：停好了，請 daemon 別再開 tick（notification，不回音）；下次 boot 重新登記。
            name = "k-%s-%d-untick.json" % (st["chain"], self.seq)
            st["sends"].append({"home": ticker, "name": name, "body": untick_request(self.home)})
        self.events.append({"event": "stopped"})

    def resend_untick(self):
        """停好了卻還被開格＝daemon 那邊還登記著（撤登記單在 daemon 崩潰對帳時被丟掉之類）：再送一張（astra 必修 3）。
        偷看 D/kernels/<id>.json 在不在（跟偷看 summary.json 一樣，不改 daemon 的家）；出貨箱裡已經有一張就不重複排。"""
        import aos_daemon_ticks
        ticker = self.state.get("ticker")
        if not ticker or aos_daemon_ticks.peek(ticker, self.home) is None:
            return
        if any((s.get("body") or {}).get("method") == "tick" for s in self.state["sends"]):
            return
        name = "k-%s-%d-untick.json" % (self.state["chain"], self.seq)
        self.state["sends"].append({"home": ticker, "name": name, "body": untick_request(self.home)})

    # ---- 一格 ----
    def step(self):
        if self.state["phase"] == "stopped":
            self.resend_untick()
            if self.flush_outboxes():
                self.save()
            return 0
        self.state["last_seq"] = self.seq
        if self.flush_outboxes():
            self.save()                               # 提交點 A：出貨完
        self.now = time.time()
        notified = self.read_requests()               # 第 5 步
        self.collect(notified)                        # 第 6 步
        self.pools_step()                             # 第 7 步
        self.dispatch()                               # 第 8 步
        self.stopping()                               # 第 9 步
        self.state["last_tick_at"] = self.now
        self.save()                                   # 提交點 B：決定完（連同 last_seq、last_tick_at）
        self.post_dispatched()                        # 先記後放
        if self.flush_outboxes():
            self.save()                               # 提交點 C：出貨完
        if self.events:
            with (self.home / "kernel.log").open("a", encoding="utf-8") as out:
                out.write(json.dumps({"chain": self.state["chain"], "seq": self.seq, "events": self.events}, ensure_ascii=False) + "\n")
        return 0


def untick_request(home):
    return {"jsonrpc": "2.0", "method": "tick", "params": {"home": str(home), "off": True}}


def take_lock(home, wait_ms=0):
    """K/.tick.lock 的獨占 flock；wait_ms 0＝不等。拿到回 fd，拿不到回 None。行程死了（含 kill -9）鎖自己消失。"""
    fd = os.open(Path(home) / LOCK, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    deadline = time.monotonic() + wait_ms / 1000
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.monotonic() >= deadline:
                os.close(fd)
                return None
            time.sleep(.005)


def tick(home, chain=None, seq=None):
    """一格。chain／seq 只為了舊 kernel cpu 裡還排著的舊格：帶了就是舊鏈殘格，退 0、什麼都不做。"""
    if chain is not None or seq is not None:
        return 0
    home = Path(home).absolute()
    info = load_info(home)
    if aos_kernel_store.legacy(home):
        raise KernelError("LedgerVersion", "帳本還是舊的 K/state.json；先 aos up（或 aos-kernel boot）換成 sqlite")
    if not aos_kernel_store.exists(home):
        raise KernelError("NotBooted", "K 還沒 boot 過（aos up 或 aos-kernel boot）")
    lock = take_lock(home)
    if lock is None:
        return BUSY_EXIT
    try:
        if info["tick_timeout_ms"]:
            # daemon 逾時會先 KILL 這格；鬧鐘設兩倍，只給 daemon 被殺後留下的孤兒 tick 用（SIGALRM 預設就是結束行程）。
            signal.setitimer(signal.ITIMER_REAL, 2 * info["tick_timeout_ms"] / 1000)
        aos_hops.mark("kernel", "begin", boot=True)
        store = aos_kernel_store.Store(home)
        try:
            state = store.load()
            return Kernel(home, info, state, int(state.get("last_seq") or 0) + 1, store=store).step()
        finally:
            store.close()
            aos_hops.mark("kernel", "end")
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)   # 同一個行程裡直接呼叫 tick（測試）時別留著鬧鐘
        os.close(lock)
