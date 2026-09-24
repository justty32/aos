"""kernel 的帳本、syscall 與出貨箱。"""
import hashlib
import os
from pathlib import Path

import aos_home
from aos_kernel_info import KernelError, _bad, _body_error, _idle, _name, _put

class KernelLedger:
    def __init__(self, home, info, state, seq):
        self.home, self.info, self.state, self.seq = Path(home).absolute(), info, state, seq
        self.events = []

    def save(self):
        aos_home.write_state(self.home, self.state)

    def cpu_home(self, name):
        return self.home / "cpus" / name

    def effective_cpus(self):
        cpus = {c: v for c, v in self.info["cpus"].items() if v["pool"] != "kernel" and c != self.state["kcpu"]}
        cpus[self.state["kcpu"]] = self.info["cpus"].get(self.state["kcpu"], {"pool": "kernel"})
        return cpus

    def _reply(self, pending, body):
        if pending is not None:
            self.state["replies"].append({"name": pending["name"], "id": pending["id"], "body": body})

    def _cancel_pending(self, proc, code):
        self._reply(proc.get("pending"), _body_error(code, "行程已移除" if code == "Removed" else "kernel 正在停機"))
        proc["pending"] = None

    def _add(self, env):
        p = env.params
        if not isinstance(p, dict):
            _bad("params 必須是物件", ["params"])
        checks = {"target": lambda v: isinstance(v, str) and "\0" not in v and os.path.isabs(v),
                  "dir_target": lambda v: isinstance(v, str) and "\0" not in v,
                  "name": _name, "once": lambda v: type(v) is bool,
                  "pool": lambda v: isinstance(v, str),
                  "interval_ms": lambda v: type(v) is int and v >= 0,
                  "timeout_ms": lambda v: type(v) is int and v >= 0,
                  "args": lambda v: isinstance(v, list) and all(isinstance(x, str) and "\0" not in x for x in v)}
        if "target" not in p:
            _bad("target 必填", ["params", "target"])
        for key, check in checks.items():
            if key in p and not check(p[key]):
                _bad("%s 型別不合" % key, ["params", key])
        pool = p.get("pool", "default")
        if pool == "kernel" or pool not in {c["pool"] for c in self.info["cpus"].values()}:
            _bad("pool 必須是現有的工作池", ["params", "pool"])
        numeric = [int(n) for n in self.state["procs"] if n.isascii() and n.isdecimal()]
        name = p.get("name", str(max(numeric, default=-1) + 1))
        if name in self.state["procs"]:
            raise KernelError("AlreadyExists", "行程已存在：%s" % name)
        proc = {"request": env.name, "target": p["target"], "dir_target": p.get("dir_target", ".aos/inst.json"),
                "once": p.get("once", False), "pool": pool,
                "interval_ms": p.get("interval_ms", self.info["interval_ms"]),
                "timeout_ms": p.get("timeout_ms", self.info["timeout_ms"]), "status": "queued",
                "runs": 0, "fails": 0, "not_before": 0, "pending": None}
        if "args" in p:
            proc["args"] = p["args"]
        if proc["once"] and not env.notify:
            proc["pending"] = {"name": env.name, "id": env.id}
        self.state["procs"][name] = proc
        self.state["queue"].append(name)
        return None if proc["once"] else {"result": {"name": name}}

    def remove(self, name):
        proc = self.state["procs"].get(name)
        if proc is None:
            raise KernelError("NotFound", "沒有這個行程：%s" % name)
        if proc["once"]:
            self._cancel_pending(proc, "Removed")
        keep = False
        for c, slot in self.state["cpus"].items():
            if slot["proc"] != name or slot["req"] is None:
                continue
            req = slot["req"]
            if ((self.cpu_home(c) / "requests" / req).exists() or
                    (self.cpu_home(c) / "responses" / req).exists()):
                slot["discard"], keep = True, True
            else:
                slot.update(_idle())
        self.state["queue"] = [n for n in self.state["queue"] if n != name]
        if not keep:
            del self.state["procs"][name]
        return {"result": {"name": name}}

    def apply_syscall(self, env):
        if env.name in self.state["deletes"]:
            return
        body = None
        if env.error is not None:
            body = {"error": env.error["error"]}
        else:
            try:
                if env.method == "add":
                    body = self._add(env)
                elif env.method == "rm":
                    if not isinstance(env.params, dict) or not _name(env.params.get("name")):
                        _bad("rm.name 必須是合法名稱", ["params", "name"])
                    body = self.remove(env.params["name"])
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
            self._reply({"name": env.name, "id": env.id}, body)
        self.state["deletes"].append(env.name)
        self.save()

    def flush_outboxes(self):
        for box in ("acks", "replies", "stops", "deletes"):
            while self.state[box]:
                item = self.state[box][0]
                if box == "acks":
                    digest = hashlib.sha256(item["name"].encode()).hexdigest()[:16]
                    name = "ack-%s-%s-%s-%s.json" % (self.state["chain"], self.seq, Path(item["home"]).name, digest)
                    _put(item["home"], name, {"jsonrpc": "2.0", "method": "ack", "params": {"name": item["name"]}})
                elif box == "replies":
                    response = {"jsonrpc": "2.0", "id": item["id"], **item["body"]}
                    try:
                        aos_home.link_json(self.home / "responses" / item["name"], response)
                    except aos_home.RequestExists:
                        pass
                elif box == "stops":
                    _put(self.cpu_home(item), "stop-%s.json" % self.state["chain"], {"jsonrpc": "2.0", "method": "stop"})
                else:
                    (self.home / "requests" / item).unlink(missing_ok=True)
                self.state[box].pop(0)
                self.save()

    def tick_request(self, seq):
        name = "k-%s-%d.json" % (self.state["chain"], seq)
        return name, {"jsonrpc": "2.0", "id": name[:-5], "method": "aos-exec", "params": {
            "target": self.state["cli"], "args": ["tick", "--target", str(self.home), "--chain", self.state["chain"], "--seq", str(seq)],
            "timeout_ms": 0}}

    def ack_ticks(self):
        home = self.cpu_home(self.state["kcpu"])
        retained = self.state["cpus"].get(self.state["kcpu"], {}).get("req")
        for path in sorted((home / "responses").glob("*.json")):
            if path.name == retained or (home / "requests" / path.name).exists():
                continue
            response = aos_home.read_json(path)
            if "error" in response or response.get("result", {}).get("code", 0) != 0:
                self.events.append({"event": "tick_error", "request": path.name, "response": response})
            digest = hashlib.sha256(path.name.encode()).hexdigest()[:16]
            name = "ack-%s-%d-%s-%s.json" % (self.state["chain"], self.seq, self.state["kcpu"], digest)
            _put(home, name, {"jsonrpc": "2.0", "method": "ack", "params": {"name": path.name}})
