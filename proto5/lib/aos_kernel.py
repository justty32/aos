"""一格接一格的排程者：kernel.md 的帳本、出貨箱、syscall 與 boot。

持久決定只寫 state.json；工作與四類出貨先記後放，只有接 tick 鏈先放後記。
目標只記路徑、不讀 inst；交給執行它的 cpu 與 aos-exec 讀驗。
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import aos_client
import aos_daemon
import aos_home
from aos_directives import Context, DirectiveError, Document, parse_options, resolve_located

CLI = Path(__file__).resolve().parents[1] / "cli" / "aos-kernel"
CPU_CLI = CLI.with_name("aos-cpu")
DEFAULTS = {"tick_ms": 1000, "interval_ms": 1000, "timeout_ms": 0, "done_exit": 100, "bad_after": 10}


class KernelError(aos_home.HomeError):
    def __init__(self, code, msg, rpc_code=-32000, position=None):
        super().__init__(code, msg)
        self.rpc_code, self.position = rpc_code, position


class CLIUsage(KernelError):
    def __init__(self, msg):
        super().__init__("Usage", msg)


def _name(value):
    return isinstance(value, str) and value not in ("", ".", "..") and "/" not in value and "\0" not in value


def _bad(msg, position):
    raise KernelError("FieldTypeMismatch", msg, -32602, position)


def load_info(home):
    home = Path(home).absolute()
    path = home / "info.json"
    raw = aos_home.read_json(path)
    if not isinstance(raw, dict) or any(k.startswith("$") for k in raw):
        _bad("info 頂層必須是字面物件", [])
    def expand(value, ctx, position, field=()):
        if len(field) == 3 and field[0] == "cpus" and field[2] == "envs":
            return copy.deepcopy(value)
        loc = resolve_located(value, ctx, position)
        value = parse_options(loc.value, loc.position, {})[1]
        if isinstance(value, dict):
            return {k: expand(v, loc.ctx, loc.position + [k], field + (k,)) for k, v in value.items()}
        if isinstance(value, list):
            return [expand(v, loc.ctx, loc.position + [str(i)], field + (str(i),)) for i, v in enumerate(value)]
        return value
    try:
        info = expand(raw, Context(Document(str(path), raw), base_dir=str(home)), [])
    except DirectiveError as exc:
        raise KernelError(exc.code, exc.msg) from exc
    mi = info.get("_metainfo")
    if (not isinstance(mi, dict) or mi.get("_type") != "kernel" or
            type(mi.get("_version")) is not int or mi["_version"] != 1):
        raise KernelError("NotAHome", "不是 kernel 第 1 版的家")
    cpus = info.get("cpus")
    if not isinstance(cpus, dict):
        _bad("cpus 必須是物件", ["cpus"])
    for name, config in cpus.items():
        if not _name(name) or not isinstance(config, dict):
            _bad("cpu 名稱或設定不合法", ["cpus", name])
        if not isinstance(config.setdefault("pool", "default"), str):
            _bad("pool 必須是字串", ["cpus", name, "pool"])
        if "envs" in config and not isinstance(config["envs"], dict):
            _bad("envs 必須是物件", ["cpus", name, "envs"])
    if sum(c["pool"] == "kernel" for c in cpus.values()) != 1:
        _bad("恰好一顆 cpu 的 pool 必須是 kernel", ["cpus"])
    for key, default in DEFAULTS.items():
        value = info.setdefault(key, default)
        if type(value) is not int or value < 0 or (key == "done_exit" and value > 255):
            _bad("%s 必須是合法非負整數" % key, [key])
    if "daemon" in info and (not isinstance(info["daemon"], str) or
                              not os.path.isabs(info["daemon"]) or "\0" in info["daemon"]):
        _bad("daemon 必須是絕對路徑", ["daemon"])
    return info


def init(home):
    home = Path(home).absolute()
    if home.exists():
        raise KernelError("AlreadyExists", "拒絕覆蓋既有的家：%s" % home)
    home.mkdir(parents=True)
    aos_home.ensure_queue(home)
    (home / "cpus").mkdir()
    info = {"_metainfo": {"_type": "kernel", "_version": 1},
            "cpus": {"k": {"pool": "kernel"}, "0": {}, "1": {}, "2": {}}, **DEFAULTS}
    aos_home.write_json(home / "info.json", info)
    return str(home)


def _idle():
    return {"req": None, "proc": None, "discard": False}


def new_state(info, chain, kcpu, cli):
    return {"chain": chain, "kcpu": kcpu, "cli": str(cli), "last_seq": 0, "phase": "running",
            "cpus": {c: _idle() for c, config in info["cpus"].items()
                     if c != kcpu and config.get("pool", "default") != "kernel"},
            "queue": [], "procs": {}, "acks": [], "replies": [], "stops": [], "deletes": []}


def classify(proc, response, info, now=None):
    """§4 反覆行程判定表；不動輸入，回新的行程紀錄。"""
    proc = copy.deepcopy(proc)
    result = response.get("result", {})
    if result.get("stopped") is True:
        proc["status"] = "queued"
        return proc
    if "error" in response:
        proc["fails"] += 1
    else:
        proc["runs"] += 1
        if result.get("kind") == "aos":
            proc["fails"] += 1
        elif info["done_exit"] != 0 and result.get("code") == info["done_exit"]:
            proc.update(fails=0, status="done")
            return proc
        elif result.get("code") in (0, 101):
            proc["fails"] = 0
        else:
            proc["fails"] += 1
    if info["bad_after"] != 0 and proc["fails"] >= info["bad_after"]:
        proc["status"] = "bad"
    else:
        proc.update(status="queued", not_before=(time.time() if now is None else now) + proc["interval_ms"] / 1000)
    return proc


def _put(home, name, obj):
    try:
        aos_home.post_request(home, name, obj)
    except aos_home.RequestExists:
        pass


def _body_error(code, msg):
    return {"error": {"code": -32000, "message": msg, "data": {"code": code}}}


class Kernel:
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
            "target": self.state["cli"], "args": ["tick", str(self.home), "--chain", self.state["chain"], "--seq", str(seq)],
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

    def collect(self):
        for c, slot in list(self.state["cpus"].items()):
            req = slot["req"]
            if req is None or (self.cpu_home(c) / "requests" / req).exists():
                continue
            response_path = self.cpu_home(c) / "responses" / req
            if not response_path.exists():
                if not slot["discard"]:
                    self._post_work(c, req, self.state["procs"][slot["proc"]])
                continue
            response = aos_home.read_json(response_path)
            name, proc = slot["proc"], self.state["procs"][slot["proc"]]
            self.events.append({"event": "response", "proc": name, "cpu": c,
                                "response": {k: response[k] for k in ("result", "error") if k in response}})
            if slot["discard"]:
                del self.state["procs"][name]
            elif proc["once"]:
                self._reply(proc["pending"], {k: response[k] for k in ("result", "error") if k in response})
                del self.state["procs"][name]
            else:
                proc = classify(proc, response, self.info)
                self.state["procs"][name] = proc
                if proc["status"] == "queued":
                    self.state["queue"].append(name)
                elif proc["status"] == "bad":
                    self.events.append({"event": "bad", "proc": name, "fails": proc["fails"], "bad_after": self.info["bad_after"]})
            self.state["acks"].append({"home": str(self.cpu_home(c)), "name": req})
            slot.update(_idle())
            self.save()

    def _create_cpu(self, c, config):
        home = self.cpu_home(c)
        if home.exists():
            return
        home.mkdir(parents=True)
        aos_home.ensure_queue(home)
        aos_home.write_json(home / "info.json", {"_metainfo": {"_type": "exec_cpu", "_version": 1}, "poll_ms": 20, "timeout_ms": 0})
        inst = {"argv": [str(CPU_CLI.resolve()), str(home)], "cwd": str(home),
                "stderr": {"$opt": "append", "$val": str(home / "cpu.log")}}
        if "envs" in config:
            inst["envs"] = copy.deepcopy(config["envs"])
        aos_home.write_json(home / "inst.json", inst)

    def _daemon_call(self, method, params, name, allow_not_found=False):
        daemon = self.info["daemon"]
        # 崩在回音到達後可重讀；原單若還在仍必須等它先消失。
        if not (Path(daemon) / "responses" / name).exists():
            _put(daemon, name, {"jsonrpc": "2.0", "id": name[:-5], "method": method, "params": params})
        response = aos_client.wait_response(daemon, name, timeout_ms=5000, poll_ms=5)
        self.state["acks"].append({"home": daemon, "name": name})
        self.save()
        if "error" in response:
            error = response["error"]
            code = error.get("data", {}).get("code", str(error["code"]))
            if not (allow_not_found and code == "NotFound"):
                raise KernelError(code, error["message"])
        return response

    def ensure_cpus(self):
        effective = self.effective_cpus()
        children = aos_daemon.read_state(self.info["daemon"])["children"]
        for c, config in effective.items():
            target = str(self.cpu_home(c) / "inst.json")
            child = children.get(c)
            if child is not None and child["target"] != target:
                raise KernelError("NameTaken", "daemon 的名字 %s 已由另一個目標使用" % c)
            if child is None or (not child["alive"] and child["state"] != "dead"):
                self._create_cpu(c, config)
                self._daemon_call("spawn", {"name": c, "target": target, "restart": True},
                                  "k-%s-%d-spawn-%s.json" % (self.state["chain"], self.seq, c))
        for c in list(self.state["cpus"]):
            if (c not in effective or c == self.state["kcpu"]) and self.state["cpus"][c]["req"] is None:
                del self.state["cpus"][c]
        for c in effective:
            if c != self.state["kcpu"]:
                self.state["cpus"].setdefault(c, _idle())
        self.save()

    def _post_work(self, c, name, proc):
        params = {k: proc[k] for k in ("target", "dir_target", "args", "timeout_ms") if k in proc}
        _put(self.cpu_home(c), name, {"jsonrpc": "2.0", "id": name[:-5], "method": "aos-exec", "params": params})

    def dispatch(self):
        if self.state["phase"] != "running":
            return
        for c, slot in self.state["cpus"].items():
            if slot["req"] is not None or c not in self.info["cpus"] or c == self.state["kcpu"]:
                continue
            pool = self.info["cpus"][c]["pool"]
            if pool == "kernel":
                continue
            name = next((n for n in self.state["queue"] if self.state["procs"][n]["pool"] == pool and
                         self.state["procs"][n]["not_before"] <= time.time()), None)
            if name is None:
                continue
            proc = self.state["procs"][name]
            req = "k-%s-%d-%s.json" % (self.state["chain"], self.seq, c)
            self.state["queue"].remove(name)
            proc["status"] = "running"
            slot.update(req=req, proc=name, discard=False)
            self.save()
            self._post_work(c, req, proc)
            self.events.append({"event": "dispatch", "proc": name, "cpu": c, "request": req})

    def stopping(self):
        if self.state["phase"] != "stopping":
            return
        for name in list(self.state["queue"]):
            proc = self.state["procs"][name]
            if proc["once"]:
                self._cancel_pending(proc, "Stopping")
                self.state["queue"].remove(name)
                del self.state["procs"][name]
        self.save()
        if (all(slot["req"] is None for slot in self.state["cpus"].values()) and
                not any(self.state[k] for k in ("acks", "replies", "stops", "deletes")) and
                not any(p["pending"] is not None for p in self.state["procs"].values())):
            self.state["stops"] = list(dict.fromkeys([*self.state["cpus"], *self.effective_cpus()]))
            self.state["phase"] = "stopped"
            self.save()

    def _stop(self):
        self.state["phase"] = "stopping"
        self.save()

    def step(self):
        if self.state["phase"] == "stopped":
            self.flush_outboxes()
            return 0
        name, request = self.tick_request(self.seq + 1)
        _put(self.cpu_home(self.state["kcpu"]), name, request)
        self.state["last_seq"] = self.seq
        self.save()
        time.sleep(self.info["tick_ms"] / 1000)
        self.flush_outboxes()
        self.ack_ticks()
        aos_home.scan_controls(self.home, self._stop)
        for name in aos_home.list_requests(self.home):
            self.apply_syscall(aos_home.read_request(self.home / "requests" / name))
        self.collect()
        self.ensure_cpus()
        self.dispatch()
        self.stopping()
        self.flush_outboxes()
        self.save()
        with (self.home / "kernel.log").open("a", encoding="utf-8") as out:
            out.write(json.dumps({"chain": self.state["chain"], "seq": self.seq, "events": self.events}, ensure_ascii=False) + "\n")
        return 0


def tick(home, chain, seq):
    info = load_info(home)
    state = aos_home.read_state(home)
    if chain != state.get("chain"):
        return 0
    return Kernel(home, info, state, seq).step()


def boot(home, daemon=None, wait_ms=30000):
    home = Path(home).absolute()
    info = load_info(home)
    cli = CLI.resolve()
    if not cli.is_file() or not os.access(cli, os.X_OK):
        raise KernelError("ReadFailed", "kernel CLI 必須有執行位：%s" % cli)
    daemon = aos_daemon.daemon_home(daemon)
    aos_home.load_info(daemon, "daemon")
    if not aos_daemon.is_alive(daemon):
        raise KernelError("NotRunning", "daemon 沒在跑：%s" % daemon)
    c = next(c for c, config in info["cpus"].items() if config["pool"] == "kernel")
    old_state = aos_home.read_state(home)
    old_c = old_state.get("kcpu", c)
    handoff = list(dict.fromkeys([old_c, c]))
    children = aos_daemon.read_state(daemon)["children"]
    # 換 kernel 池時仍先收帳本釘死的舊主人；兩個名字都驗完才送任何 kill。
    for name in handoff:
        child = children.get(name)
        if child is not None and child["target"] != str(home / "cpus" / name / "inst.json"):
            raise KernelError("NameTaken", "kernel cpu 名字已由另一個目標使用：%s" % name)
    chain = "%d-%d" % (time.time_ns(), os.getpid())
    # 交接完成前不碰舊帳本；kill 的 ack 暫存，取得帳本後一併記入出貨箱。
    kill_acks = []
    for name in handoff:
        if name not in children:
            continue
        request = ("k-%s-boot-kill.json" % chain if len(handoff) == 1 else
                   "k-%s-boot-kill-%s.json" % (chain, name))
        response = aos_client.call(daemon, "kill", {"name": name}, name=request,
                                   timeout_ms=5000, poll_ms=5, acknowledge=False)
        error = response.get("error")
        if error and error.get("data", {}).get("code") != "NotFound":
            raise KernelError(error.get("data", {}).get("code", str(error["code"])), error["message"])
        kill_acks.append({"home": daemon, "name": request})
        deadline = time.monotonic() + wait_ms / 1000
        while name in aos_daemon.read_state(daemon)["children"]:
            if time.monotonic() >= deadline:
                raise KernelError("AlreadyRunning", "舊 kernel cpu 尚未退出；kill 已送出")
            time.sleep(.005)
    raw = aos_home.read_json(home / "info.json")
    raw["daemon"] = daemon
    aos_home.write_json(home / "info.json", raw)
    info["daemon"] = daemon
    state = aos_home.read_state(home, new_state(info, chain, c, cli))
    state.update(chain=chain, kcpu=c, cli=str(cli), last_seq=0, phase="running", stops=[])
    state["acks"].extend(kill_acks)
    kernel = Kernel(home, info, state, 0)
    kernel.save()
    for name, config in info["cpus"].items():
        kernel._create_cpu(name, config)
        kernel._daemon_call("spawn", {"name": name, "target": str(kernel.cpu_home(name) / "inst.json"), "restart": True},
                            "k-%s-0-spawn-%s.json" % (chain, name))
    name, request = kernel.tick_request(1)
    _put(kernel.cpu_home(c), name, request)
    return 0


def status(home):
    info, state = load_info(home), aos_home.read_state(home)
    daemon = info.get("daemon", aos_daemon.daemon_home())
    child_state = aos_daemon.read_state(daemon)
    c = state.get("kcpu")
    cpu_home = Path(home) / "cpus" / c if c else None
    cpu_state = aos_home.read_state(cpu_home) if cpu_home and cpu_home.exists() else {}
    return {k: state.get(k) for k in ("chain", "phase", "last_seq", "cpus", "queue", "procs")} | {
        "daemon": {"alive": aos_daemon.is_alive(daemon), "children": child_state["children"]},
        "kernel_cpu": {"name": c, "current": cpu_state.get("current"),
                       "requests": len(list((cpu_home / "requests").glob("*.json"))) if cpu_home else 0}}


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CLIUsage(message)


def _parser():
    parser = _Parser(prog="aos-kernel", add_help=False)
    subs = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    for command in ("init", "boot", "tick", "add", "rm", "ls", "stop"):
        p = subs.add_parser(command, add_help=False)
        p.add_argument("home")
        if command == "boot":
            p.add_argument("--daemon")
            p.add_argument("--wait-ms", type=int, default=30000)
        elif command == "tick":
            p.add_argument("--chain", required=True)
            p.add_argument("--seq", required=True, type=int)
        elif command == "add":
            p.add_argument("target")
            for key in ("name", "pool", "dir-target"):
                p.add_argument("--" + key)
            for key in ("interval-ms", "timeout-ms", "wait-ms"):
                p.add_argument("--" + key, type=int)
            p.add_argument("--once", action="store_true")
        elif command == "rm":
            p.add_argument("name")
    return parser


def _cli_request(args, trailing):
    home = Path(args.home).absolute()
    name = aos_client.new_name("cli")
    if args.command == "stop":
        _put(home, "stop-" + name, {"jsonrpc": "2.0", "method": "stop"})
        return 0
    params = {"name": args.name} if args.command == "rm" else {"target": os.path.abspath(args.target), "once": args.once}
    if args.command == "add":
        for key in ("name", "pool", "dir_target", "interval_ms", "timeout_ms"):
            value = getattr(args, key)
            if value is not None:
                params[key] = value
        if args.once and "name" not in params:
            params["name"] = name
        if trailing is not None:
            params["args"] = trailing
    aos_client.submit(home, args.command, params, name=name)
    path = home / "responses" / name
    if args.command == "add" and args.once and args.wait_ms is None:
        print("%s %s" % (name, path))
        return 0
    wait_ms = args.wait_ms if args.command == "add" and args.wait_ms is not None else 10000
    try:
        response = aos_client.wait_response(home, name, timeout_ms=wait_ms, poll_ms=5)
    except aos_client.ClientError:
        print(path)
        raise
    aos_client.ack(home, name)
    if "error" in response:
        error = response["error"]
        raise KernelError(error.get("data", {}).get("code", str(error["code"])), error["message"])
    if args.command == "add" and args.once:
        print(json.dumps(response["result"], ensure_ascii=False))
    else:
        print(response["result"]["name"])
    return 0


def main(argv=None):
    values = list(sys.argv[1:] if argv is None else argv)
    trailing = None
    if "--" in values:
        pos = values.index("--")
        values, trailing = values[:pos], values[pos + 1:]
    try:
        args = _parser().parse_args(values)
        if trailing is not None and args.command != "add":
            raise CLIUsage("只有 add 能帶 -- ARG...")
        for key in ("wait_ms", "interval_ms", "timeout_ms", "seq"):
            value = getattr(args, key, None)
            if value is not None and value < (1 if key == "seq" else 0):
                raise CLIUsage("%s 不在合法範圍" % key)
        if args.command == "init":
            init(args.home)
            return 0
        if args.command == "boot":
            return boot(args.home, args.daemon, args.wait_ms)
        if args.command == "tick":
            return tick(args.home, args.chain, args.seq)
        if args.command == "ls":
            print(json.dumps(status(args.home), ensure_ascii=False))
            return 0
        return _cli_request(args, trailing)
    except aos_home.HomeError as exc:
        sys.stderr.write("aos-kernel: %s: %s\n" % (exc.code, exc.msg.replace("\n", " ")))
        return 2 if isinstance(exc, CLIUsage) else 1
    except (OSError, ValueError, TypeError, KeyError) as exc:
        sys.stderr.write("aos-kernel: IOFailed: %s\n" % str(exc).replace("\n", " "))
        return 1


if __name__ == "__main__":
    sys.exit(main())
