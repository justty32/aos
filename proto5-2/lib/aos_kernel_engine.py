"""kernel 的結果收集、cpu 管理與每格排程。"""
import copy
import json
from pathlib import Path
import time

import aos_client
import aos_daemon
import aos_home
from aos_kernel_info import CPU_CLI, KernelError, _idle, _put, classify, load_info
from aos_kernel_ledger import KernelLedger

class Kernel(KernelLedger):
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
        home.mkdir(parents=True, exist_ok=True)
        aos_home.ensure_queue(home)
        if not (home / "info.json").exists():
            aos_home.write_json(home / "info.json", {"_metainfo": {"_type": "exec_cpu", "_version": 1}, "poll_ms": 20, "timeout_ms": 0})
        inst = {"argv": [str(CPU_CLI.resolve()), str(home)], "cwd": str(home),
                "stderr": {"$opt": "append", "$val": str(home / "cpu.log")}}
        if "envs" in config:
            inst["envs"] = copy.deepcopy(config["envs"])
        if not (home / "inst.json").exists():
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
