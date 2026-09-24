"""kernel 的帳本第 2 版（kernel-ledger.md）：排隊（ready／delayed 堆積、懶刪）、syscall、出貨箱。

帳本仍是一份 state.json、一次原子寫；一格最多寫四次（提交點 1～4），寫入由 engine 決定，這裡的函式只改記憶體。
"""
import collections
import hashlib
import heapq
import os
from pathlib import Path
import time

import aos_home
from aos_kernel_info import (
    FEATURES, KCPU, KERNEL_POOL, PARK_MS, KernelError, _bad, _body_error, _name, _put, is_member, split_key,
)


class KernelLedger:
    def __init__(self, home, info, state, seq, now=None):
        self.home, self.info, self.seq = Path(home).absolute(), info, seq
        self.now = time.time() if now is None else now
        self.state = state
        for key, default in (("busy", {}), ("on", {}), ("recent", []), ("ready", {}), ("delayed", []),
                             ("stale", {}), ("pools", {}), ("sends", []), ("acks", []), ("replies", []),
                             ("deletes", []), ("procs", {})):
            state.setdefault(key, default)
        state.setdefault("halting", False)
        # 09-24 停車：舊帳本升上來時補能力標記（下一次存檔就寫進去；aos-agent start 看它）。
        features = state.setdefault("features", [])
        features.extend(f for f in FEATURES if f not in features)
        # ready 在記憶體裡當 deque 用（從頭拿不搬整條）；存檔時轉回陣列。
        state["ready"] = {p: collections.deque(q) for p, q in state["ready"].items()}
        self.events = []

    # ---- 存檔 ----
    def snapshot(self):
        out = dict(self.state)
        out["ready"] = {p: [list(x) for x in q] for p, q in self.state["ready"].items()}
        return out

    def save(self):
        aos_home.write_state(self.home, self.snapshot())

    # ---- 路徑 ----
    def pool_dir(self, pool):
        return self.home / "pools" / pool

    def cpu_home(self, key):
        """key 是 'P/<i>'（kcpu 就是 kernel/0）。"""
        pool, i = split_key(key)
        return self.pool_dir(pool) / "cpus" / str(i)

    # ---- 排隊（kernel-ledger §2：排隊的格帶 request，懶刪） ----
    def _valid(self, name, request, not_before=None):
        proc = self.state["procs"].get(name)
        if proc is None or proc["status"] != "queued" or proc["request"] != request:
            return False
        return not_before is None or proc["not_before"] == not_before

    def enqueue(self, name):
        proc = self.state["procs"][name]
        if proc["not_before"] <= self.now:
            self.state["ready"].setdefault(proc["pool"], collections.deque()).append([name, proc["request"]])
        else:
            heapq.heappush(self.state["delayed"], [proc["not_before"], name, proc["request"]])

    def _stale_dropped(self, pool):
        stale = self.state["stale"]
        if stale.get(pool, 0) > 0:
            stale[pool] -= 1
            if stale[pool] == 0:
                del stale[pool]

    def mark_stale(self, pool):
        """一個排隊中的行程被拿掉（懶刪）：記舊格數；超過活格數就整條壓縮（攤還 O(1)）。"""
        stale = self.state["stale"]
        stale[pool] = stale.get(pool, 0) + 1
        length = len(self.state["ready"].get(pool, ())) + len(self.state["delayed"])
        if stale[pool] * 2 > length:
            self.compact(pool)

    def compact(self, pool):
        queue = self.state["ready"].get(pool)
        if queue is not None:
            self.state["ready"][pool] = collections.deque(e for e in queue if self._valid(e[0], e[1]))
        self.state["delayed"] = [e for e in self.state["delayed"] if self._valid(e[1], e[2], e[0])]
        heapq.heapify(self.state["delayed"])
        self.state["stale"].pop(pool, None)

    def promote_delayed(self):
        """第 8 步之 1：堆頂到期就彈出、接到它池的 ready 尾巴。"""
        delayed = self.state["delayed"]
        while delayed and delayed[0][0] <= self.now:
            not_before, name, request = heapq.heappop(delayed)
            if not self._valid(name, request, not_before):
                proc = self.state["procs"].get(name)
                self._stale_dropped(proc["pool"] if proc else None)
                continue
            pool = self.state["procs"][name]["pool"]
            self.state["ready"].setdefault(pool, collections.deque()).append([name, request])

    def pop_ready(self, pool):
        """從池的 ready 頭拿下一個有效格；舊格丟掉。沒有回 None。"""
        queue = self.state["ready"].get(pool)
        while queue:
            name, request = queue.popleft()
            if self._valid(name, request):
                return name
            self._stale_dropped(pool)
        return None

    # ---- 忙的 cpu ----
    def release(self, key):
        """那顆 cpu 結清：busy、on 拿掉；可派就放回 free 尾巴，縮小中就 draining 減 1（kernel-tick 第 6 步）。"""
        slot = self.state["busy"].pop(key, None)
        if slot is not None and self.state["on"].get(slot["proc"]) == key:
            del self.state["on"][slot["proc"]]
        pool, i = split_key(key)
        entry = self.state["pools"].get(pool)
        if entry is None or pool == KERNEL_POOL:
            return
        want = entry["want"] or {"count": 0, "skip": []}
        pending = entry["pending"] or entry["sent"]
        sent = entry["sent"]
        in_w = is_member(i, want["count"], want["skip"])
        if (in_w and is_member(i, sent["count"], sent["skip"]) and is_member(i, pending["count"], pending["skip"])
                and not entry["dirty"]):
            entry["free"].append(i)
        elif not in_w:
            if entry["draining"] > 0:
                entry["draining"] -= 1
                if entry["draining"] == 0:
                    entry["dirty"] = True

    def work_exists(self, key, req):
        home = self.cpu_home(key)
        return (home / "requests" / req).exists(), (home / "responses" / req).exists()

    # ---- syscall（proto5 §2，判定不變；寫帳本改由提交點 3 一起寫） ----
    def _reply(self, pending, body):
        if pending is not None:
            item = {"name": pending["name"], "id": pending["id"], "body": body}
            if pending.get("wake") is not None:  # 09-24 停車：這張 add 的最後一則回音帶著要叫醒誰
                item["wake"] = pending["wake"]
            self.state["replies"].append(item)

    def _wake_of(self, params):
        """add 的 wake（合法名稱才記）。不比代數：stop／start 後的新一代會接手舊批（aos-agent register.md），叫它才對（astra 必修 1）。"""
        name = params.get("wake") if isinstance(params, dict) else None
        return {"wake": name} if _name(name) else {}

    def wake(self, name):
        """叫醒一個行程（kernel/syscall.md「叫醒一個行程」）；回做了什麼（None＝什麼都沒做）。只改記憶體。"""
        proc = self.state["procs"].get(name)
        if proc is None or proc["once"] or proc["status"] not in ("running", "queued"):
            return None
        if proc["status"] == "running":
            slot = self.state["busy"].get(self.state["on"].get(name))
            if slot is not None and slot["discard"]:
                return None
            proc["woken"] = True
            how = "woken"
        elif proc["not_before"] > self.now:
            proc["not_before"] = self.now
            proc.pop("parked", None)
            self.state["ready"].setdefault(proc["pool"], collections.deque()).append([name, proc["request"]])
            self.mark_stale(proc["pool"])  # delayed 裡那格時間對不上了，變舊格
            how = "ready"
        else:
            return None
        self.events.append({"event": "wake", "proc": name, "how": how})
        return how

    def _cancel_pending(self, proc, code):
        self._reply(proc.get("pending"), _body_error(code, "行程已移除" if code == "Removed" else "kernel 正在停機"))
        proc["pending"] = None

    def _add(self, env, wake=None):
        p = env.params
        if not isinstance(p, dict):
            _bad("params 必須是物件", ["params"])
        checks = {"target": lambda v: isinstance(v, str) and "\0" not in v and os.path.isabs(v),
                  "dir_target": lambda v: isinstance(v, str) and "\0" not in v,
                  "name": _name, "once": lambda v: type(v) is bool,
                  "pool": lambda v: isinstance(v, str),
                  "interval_ms": lambda v: type(v) is int and v >= 0,
                  "timeout_ms": lambda v: type(v) is int and v >= 0,
                  "park_ms": lambda v: type(v) is int and v >= 0, "wake": _name,
                  "args": lambda v: isinstance(v, list) and all(isinstance(x, str) and "\0" not in x for x in v)}
        if "target" not in p:
            _bad("target 必填", ["params", "target"])
        for key, check in checks.items():
            if key in p and not check(p[key]):
                _bad("%s 型別不合" % key, ["params", key])
        pool = p.get("pool", "default")
        if pool == KERNEL_POOL or pool not in self.info["pools"]:
            _bad("pool 必須是現有的工作池", ["params", "pool"])
        numeric = [int(n) for n in self.state["procs"] if n.isascii() and n.isdecimal()]
        name = p.get("name", str(max(numeric, default=-1) + 1))
        if name in self.state["procs"]:
            raise KernelError("AlreadyExists", "行程已存在：%s" % name)
        once = p.get("once", False)
        if once and self.state["phase"] != "running":
            # kernel-tick 第 9 步：stopping 之後新 add 的 once 當場回 Stopping。
            raise KernelError("Stopping", "kernel 正在停機")
        proc = {"request": env.name, "target": p["target"], "dir_target": p.get("dir_target", ".aos/inst.json"),
                "once": once, "pool": pool,
                "interval_ms": p.get("interval_ms", self.info["interval_ms"]),
                "timeout_ms": p.get("timeout_ms", self.info["timeout_ms"]),
                "park_ms": p.get("park_ms", self.info.get("park_ms", PARK_MS)), "status": "queued",
                "runs": 0, "fails": 0, "not_before": 0, "pending": None}
        if "args" in p:
            proc["args"] = p["args"]
        if proc["once"] and not env.notify:
            proc["pending"] = {"name": env.name, "id": env.id, **(wake or {})}
        self.state["procs"][name] = proc
        self.enqueue(name)
        return None if proc["once"] else {"result": {"name": name}}

    def remove(self, name):
        proc = self.state["procs"].get(name)
        if proc is None:
            raise KernelError("NotFound", "沒有這個行程：%s" % name)
        if proc["once"]:
            self._cancel_pending(proc, "Removed")
        keep = False
        key = self.state["on"].get(name)
        slot = self.state["busy"].get(key) if key else None
        if proc["status"] == "running" and slot is not None and slot["proc"] == name:
            if any(self.work_exists(key, slot["req"])):
                slot["discard"], keep = True, True
            else:
                self.release(key)
        if not keep:
            del self.state["procs"][name]
            if proc["status"] == "queued":
                self.mark_stale(proc["pool"])
        return {"result": {"name": name}}

    def apply_syscall(self, env):
        if env.name in self.state["deletes"]:
            return
        body, wake = None, {}
        if env.error is not None:
            body = {"error": env.error["error"]}
        else:
            try:
                if env.method == "add":
                    wake = self._wake_of(env.params)
                    body = self._add(env, wake)
                elif env.method == "rm":
                    if not isinstance(env.params, dict) or not _name(env.params.get("name")):
                        _bad("rm.name 必須是合法名稱", ["params", "name"])
                    body = self.remove(env.params["name"])
                elif env.method == "wake":
                    if not isinstance(env.params, dict) or not _name(env.params.get("name")):
                        _bad("wake.name 必須是合法名稱", ["params", "name"])
                    if env.params["name"] not in self.state["procs"]:
                        raise KernelError("NotFound", "沒有這個行程：%s" % env.params["name"])
                    self.wake(env.params["name"])
                    body = {"result": {"name": env.params["name"]}}
                else:
                    raise KernelError("MethodNotFound", "不認得 method：%s" % env.method, -32601)
            except KernelError as exc:
                error = {"code": exc.rpc_code, "message": exc.msg}
                if exc.rpc_code != -32601:
                    error["data"] = {"code": exc.code}
                    if exc.position is not None:
                        error["data"]["position"] = exc.position
                body = {"error": error}
        if body is not None and not env.notify:
            self._reply({"name": env.name, "id": env.id, **wake}, body)
        self.state["deletes"].append(env.name)

    def start_stopping(self):
        """stop：phase 改 stopping，當場掃一次 ready／delayed 把 once 拿掉、各回 Stopping（O(排隊數)，只這一次）。"""
        if self.state["phase"] != "running":
            return
        self.state["phase"] = "stopping"
        procs = self.state["procs"]
        def drop(name, request, not_before=None):
            if not self._valid(name, request, not_before):
                return True
            proc = procs[name]
            if proc["once"]:
                self._cancel_pending(proc, "Stopping")
                del procs[name]
                return True
            return False
        for pool, queue in self.state["ready"].items():
            self.state["ready"][pool] = collections.deque(e for e in queue if not drop(e[0], e[1]))
        self.state["delayed"] = [e for e in self.state["delayed"] if not drop(e[1], e[2], e[0])]
        heapq.heapify(self.state["delayed"])
        self.state["stale"] = {}

    # ---- 出貨（kernel-ledger §3：全部做完才一次寫帳本） ----
    def flush_outboxes(self):
        """四箱全做一遍；回「有沒有做事」讓呼叫者決定要不要寫帳本。"""
        did = False
        for item in self.state["acks"]:
            digest = hashlib.sha256(item["name"].encode()).hexdigest()[:16]
            name = "ack-%s-%s-%s-%s.json" % (self.state["chain"], self.seq, Path(item["home"]).name, digest)
            _put(item["home"], name, {"jsonrpc": "2.0", "method": "ack", "params": {"name": item["name"]}})
        for item in self.state["replies"]:
            response = {"jsonrpc": "2.0", "id": item["id"], **item["body"]}
            try:
                aos_home.link_json(self.home / "responses" / item["name"], response)
            except aos_home.RequestExists:
                pass
            if item.get("wake") is not None:
                # 09-24 停車：回音檔放好之後才叫醒；叫醒的結果跟「拿掉這筆」同一次存帳本（呼叫者存）。
                self.wake(item["wake"])
        for item in self.state["deletes"]:
            (self.home / "requests" / item).unlink(missing_ok=True)
        for item in self.state["sends"]:
            # 回音已在＝對方處理過了（崩在放完、清帳前），不再放同名單。
            if not (Path(item["home"]) / "responses" / item["name"]).exists():
                _put(item["home"], item["name"], item["body"])
        for box in ("acks", "replies", "deletes", "sends"):
            if self.state[box]:
                did = True
                self.state[box] = []
        return did

    def tick_request(self, seq):
        name = "k-%s-%d.json" % (self.state["chain"], seq)
        return name, {"jsonrpc": "2.0", "id": name[:-5], "method": "aos-exec", "params": {
            "target": self.state["cli"], "args": ["tick", "--target", str(self.home), "--chain", self.state["chain"], "--seq", str(seq)],
            "timeout_ms": 0}}

    def ack_ticks(self):
        home = self.cpu_home(KCPU)
        for path in sorted((home / "responses").glob("*.json")):
            if (home / "requests" / path.name).exists():
                continue
            response = aos_home.read_json(path)
            if "error" in response or response.get("result", {}).get("code", 0) != 0:
                self.events.append({"event": "tick_error", "request": path.name, "response": response})
            digest = hashlib.sha256(path.name.encode()).hexdigest()[:16]
            name = "ack-%s-%d-%s-%s.json" % (self.state["chain"], self.seq, "0", digest)
            _put(home, name, {"jsonrpc": "2.0", "method": "ack", "params": {"name": path.name}})
