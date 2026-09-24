"""kernel 一格十步（kernel-tick.md）：只碰有事的 cpu——有通知的、上一格剛派的、輪到巡檢的。

提交點（kernel-ledger §3）：1＝第 2 步 last_seq；2＝第 4 步出貨完；3＝第 5～9 步全部決定完；4＝第 10 步出貨完。
"""
import itertools
import json
import os
from pathlib import Path
import time

import aos_home
from aos_kernel_info import (
    KCPU, KERNEL_POOL, _put, chain_epoch, classify, cpu_key, load_info, split_key,
)
from aos_kernel_ledger import KernelLedger
from aos_kernel_pools import PoolsMixin, scale_request


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
            self.apply_syscall(aos_home.read_request(req_dir / name))
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
                self.state["busy"][key] = {"req": req, "proc": name, "discard": False}
                self.state["on"][name] = key
                self.state["recent"].append(key)
                self.events.append({"event": "dispatch", "proc": name, "cpu": key, "request": req})

    def post_dispatched(self):
        for key in self.state["recent"]:
            slot = self.state["busy"].get(key)
            if slot is not None:
                self._post_work(key, slot["req"], self.state["procs"][slot["proc"]])

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
        entry = st["pools"].get(KERNEL_POOL)
        if entry is not None:
            name = "k-%s-%d-scale-%s.json" % (st["chain"], self.seq, KERNEL_POOL)
            body = scale_request(name, self.home, KERNEL_POOL, entry, 0, [], [chain_epoch(st["chain"]), self.seq])
            st["sends"].append({"home": entry["daemon"], "name": name, "body": body})
            entry["pending"] = {"name": name, "count": 0, "skip": []}
        self.events.append({"event": "stopped"})

    # ---- 一格 ----
    def step(self):
        if self.state["phase"] == "stopped":
            if self.flush_outboxes():
                self.save()
            return 0
        name, request = self.tick_request(self.seq + 1)
        _put(self.cpu_home(KCPU), name, request)
        self.state["last_seq"] = self.seq
        self.save()                                   # 提交點 1
        time.sleep(self.info["tick_ms"] / 1000)
        if self.flush_outboxes():
            self.save()                               # 提交點 2
        self.ack_ticks()
        self.now = time.time()
        notified = self.read_requests()               # 第 5 步
        self.collect(notified)                        # 第 6 步
        self.pools_step()                             # 第 7 步
        self.dispatch()                               # 第 8 步
        self.stopping()                               # 第 9 步
        self.save()                                   # 提交點 3
        self.post_dispatched()                        # 先記後放
        if self.flush_outboxes():
            self.save()                               # 提交點 4
        if self.events:
            with (self.home / "kernel.log").open("a", encoding="utf-8") as out:
                out.write(json.dumps({"chain": self.state["chain"], "seq": self.seq, "events": self.events}, ensure_ascii=False) + "\n")
        return 0


def tick(home, chain, seq):
    info = load_info(home)
    state = aos_home.read_state(home)
    if chain != state.get("chain"):
        return 0
    return Kernel(home, info, state, seq).step()
