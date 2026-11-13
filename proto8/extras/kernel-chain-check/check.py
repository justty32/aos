#!/usr/bin/env python3
# 在獨立暫存樹驗證兩站 kernel 的掛子、排隊、hook、重啟與 ping，並嚴格核對清理範圍。
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[2]

# 暫存 hook 只觀察，不改信；A 的 before_verdict 另擋 evil。
HOOK = '''#!/usr/bin/env python3
# 記錄暫存站的事件，並拒絕名為 evil 的掛子信。
import json, os, pathlib, sys
event = json.load(sys.stdin)
station = pathlib.Path(event["stack"])
event["kernel_env"] = os.environ.get("AOS_KERNEL")
with (station / "audit.jsonl").open("a") as stream:
    stream.write(json.dumps(event) + "\\n")
if event["event"] == "before_verdict" and "evil" in (event.get("body") or {}).get("procs_added", {}):
    print("evil is blocked")
    sys.exit(10)
'''

IDLE = '''#!/usr/bin/env python3
# 測試 proc 收到自己的退場標記後自然退非零，讓 daemon 保留 stopped 列。
import os, pathlib, sys
sys.exit(1 if (pathlib.Path(os.environ["AOS_STACK"]) / "finish").exists() else 0)
'''


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def read(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


class Check:
    def __init__(self, timeout):
        self.timeout = timeout
        # 不採用 TMPDIR，避免外來環境把 mktemp 指到既有的樹。
        self.clean = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        result = subprocess.run(["mktemp", "-d", "/tmp/aos-kernel-chain-XXXXXXXX"],
                                env=self.clean, check=True, capture_output=True, text=True)
        self.work = Path(result.stdout.strip()).resolve()
        self.root = self.work / "stacks/root"
        self.a = self.root / "procs/station_a"
        self.foreman = self.root / "procs/foreman"
        self.agent = self.foreman / "procs/agent"
        self.defs = self.work / "defs"
        self.processes = []
        self.logs = []
        self.sent = {}
        self.replies = {}
        self.stage = "setup"
        self.env = dict(self.clean, HOME=str(self.work / "home"),
                        XDG_CONFIG_HOME=str(self.work / "home/.config"),
                        XDG_CACHE_HOME=str(self.work / "home/.cache"),
                        PYTHONDONTWRITEBYTECODE="1",
                        PYTHONPATH=os.pathsep.join([str(PROTO / "py"), str(PROTO / "lib")]),
                        AOS_HOME=str(PROTO))
        self.agent_env = dict(self.env, AOS_DAEMON=str(self.foreman),
                              AOS_KERNEL=str(self.a / "requests"), AOS_AGENT="agent",
                              AOS_WS=str(self.work), AOS_STACK=str(self.agent / "tools/subagent"))
        (self.work / "home").mkdir()
        print("Temporary fixture: " + str(self.work), flush=True)

    def inside(self, path):
        path = Path(path).resolve()
        require(path != self.work and path.is_relative_to(self.work),
                "unsafe fixture path: " + str(path))
        return path

    def run(self, argv, *, env=None, payload=None, check=True, limit=None):
        # 所有短命指令也記下 Popen；逾時不得使用 subprocess.run 的隱含 kill。
        argv = list(map(str, argv))
        proc = subprocess.Popen(argv, cwd=self.work, env=env or self.env,
                                stdin=subprocess.PIPE if payload is not None else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.processes.append(proc)
        try:
            out, err = proc.communicate(payload, timeout=limit or self.timeout)
        except subprocess.TimeoutExpired:
            self.signal_owned(proc, signal.SIGTERM)
            try:
                out, err = proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                self.signal_owned(proc, signal.SIGKILL)
                out, err = proc.communicate(timeout=5)
            raise RuntimeError("command timed out: " + repr(argv) + "\n" + out + err)
        if check and proc.returncode:
            raise RuntimeError("command failed: " + repr(argv) + "\n" + out + err)
        return subprocess.CompletedProcess(argv, proc.returncode, out, err)

    def signal_owned(self, proc, sig):
        require(proc in self.processes, "refusing to signal an unrecorded process")
        if proc.poll() is not None:
            return
        try:
            cwd = os.readlink("/proc/%d/cwd" % proc.pid)
            require(Path(cwd).resolve().is_relative_to(self.work),
                    "refusing to signal pid %d outside the temporary fixture: %s" % (proc.pid, cwd))
            print("Signal %d to owned pid %d (cwd %s)" % (sig, proc.pid, cwd), flush=True)
            os.kill(proc.pid, sig)
        except FileNotFoundError:
            proc.poll()

    def ctl(self, stack, *args, check=True):
        stack = self.inside(stack)
        if args and args[0] == "shutdown":
            print("Shutdown verified temporary stack: " + str(stack), flush=True)
        return self.run(["aos-daemon-ctl", "-d", stack, *args], check=check)

    def table(self, stack):
        result = self.ctl(stack, "ls", "--json", check=False)
        return json.loads(result.stdout).get("procs", {}) if result.returncode == 0 else {}

    def wait(self, label, pred):
        end = time.monotonic() + self.timeout
        while time.monotonic() < end:
            value = pred()
            if value:
                return value
            if self.root_proc.poll() is not None:
                raise RuntimeError("root daemon exited while waiting for " + label)
            time.sleep(0.1)
        raise RuntimeError("timed out waiting for " + label)

    def kernel(self, folder, cfg):
        hooks = {name: {"event": name, "handler": str(self.defs / "audit"),
                        "timeout_ms": 5000}
                 for name in ("before_verdict", "after_verdict", "before_reply")}
        save(folder / "kernel.json", dict(cfg, hooks=hooks, reply_via_me=True))

    def make(self):
        for command in ("aos-exec", "aos-daemon", "aos-daemon-ctl", "aos-loop",
                        "aos-agent", "aos-post", "aos-directive", "aos-clock"):
            require(shutil.which(command), "command missing: " + command)
        self.defs.mkdir()
        audit = self.defs / "audit"
        audit.write_text(HOOK, encoding="utf-8")
        audit.chmod(0o755)
        idle = self.defs / "idle"
        idle.mkdir()
        (idle / "tick.py").write_text(IDLE, encoding="utf-8")
        save(idle / "interfaces.json", {"aos-agent": {"entry": "body.json"}})
        save(idle / "body.json", {"exec": {"argv": [sys.executable, str(idle / "tick.py")]},
                                  "interval_ms": 150})
        shutil.copytree(PROTO / "templates/agent-fsm", self.defs / "agent",
                        symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "tests"))
        save(self.defs / "agent/tools.json", {"tools": {"subagent": {"path": str(PROTO / "lib/agent/subagent")}}})
        save(self.defs / "agent/llm.json", {"model": "fake"})
        # 工具的頂層 Popen 留在暫存 cwd，逾時才能依硬規則核對後收它。
        for name, tool in (("fake_call", "base/llm_fake"), ("subagent_call", "agent/subagent")):
            save(self.defs / (name + ".json"),
                 {"argv": [str(PROTO / "lib" / tool / "_entry")], "cwd": str(self.work)})
        shutil.copytree(PROTO / "kernel/procs-kernel", self.defs / "station_a")
        shutil.copytree(PROTO / "kernel/daemon-kernel", self.defs / "foreman")
        # 兩站都不寫 next、都拿到指向領班信箱的 AOS_KERNEL：A 照它轉；領班發現指到自己就跳過、照 AOS_DAEMON 轉。
        for name, config in (("station_a", "loop.json"), ("foreman", "daemon.json")):
            save(self.defs / name / config,
                 {"exec": {"argv": ["aos-exec", str(PROTO / "lib/aos/kernel"),
                                    str(self.defs / name / "kernel.json")],
                           "envs": {"AOS_KERNEL": str(self.foreman / "requests")}}, "interval_ms": 150})
        self.kernel(self.defs / "station_a", {})
        self.kernel(self.defs / "foreman", {"max_running": 4, "queue": True})
        foreman_cfg = read(self.defs / "foreman/daemon.json")
        foreman_cfg["procs"] = {
            "agent": {"exec": {"argv": ["aos-exec", str(self.defs / "agent/body.json")],
                               "envs": {"AOS_KERNEL": str(self.a / "requests")}},
                      "def": str(self.defs / "agent"), "ws": str(self.work)},
            "other": self.spec("other")}
        save(self.defs / "foreman/daemon.json", foreman_cfg)
        save(self.defs / "_entry", ["aos-daemon", "--enable-logs", "daemon.json"])
        save(self.defs / "daemon.json", {"interval_ms": 150, "procs": {
            "_clock": {"exec": {"argv": ["aos-clock", str(self.root / "clock")]}, "interval_ms": 1000},
            "station_a": {"exec": str(self.defs / "station_a"), "stack": str(self.a)},
            "foreman": {"exec": str(self.defs / "foreman"), "stack": str(self.foreman)}}})

    def spec(self, name):
        return {"exec": {"argv": [sys.executable, str(self.defs / "idle/tick.py")]},
                "interval_ms": 150, "def": str(self.defs / "idle"),
                "ws": str(self.work), "stack": str(self.foreman / "procs" / name)}

    def start(self):
        log = (self.work / "root.log").open("a", encoding="utf-8")
        self.logs.append(log)
        self.root_proc = subprocess.Popen(["aos-exec", "--stack", str(self.root), str(self.defs)],
                                          cwd=self.work, env=self.env, stdout=log, stderr=log)
        self.processes.append(self.root_proc)
        for stack in (self.root, self.foreman):
            self.wait("daemon ping at " + str(stack), lambda stack=stack:
                      (stack / "state.json").exists() and
                      self.ctl(stack, "ping", "--timeout-s", "1", check=False).returncode == 0)
        self.wait("station A mailbox", lambda: (self.a / "requests/new").is_dir())
        self.wait("agent and other running", lambda: all(
            self.table(self.foreman).get(name, {}).get("phase") == "running" for name in ("agent", "other")))
        self.wait("station A running", lambda: self.table(self.root).get("station_a", {}).get("phase") == "running")

    def post(self, *args, body=None):
        result = self.run(["aos-post", *args], env=self.agent_env, check=False,
                          payload=json.dumps(body) if body is not None else None)
        require(result.returncode == 0 or (args[0] == "take-all" and result.returncode == 10),
                "aos-post failed: " + repr(args) + "\n" + result.stdout + result.stderr)
        return result.stdout.strip()

    def send(self, tag, body):
        box = self.agent / "tools/chain_check" / tag / "replies"
        self.post("init", box)
        letter = self.post("send", "--reply-to", box, self.a / "requests", body=body)
        self.sent[tag] = (letter, box)
        return letter

    def receive(self, tag, applied=True):
        letter, box = self.sent[tag]

        def take():
            self.post("take-all", box)
            names = list((box / "cur").glob("*/letter.json"))
            if not names:
                return None
            require(len(names) == 1, "duplicate replies for " + tag)
            envelope = json.loads(self.post("see", box, names[0].parent.name))
            require(envelope.get("in_reply_to") == letter, "reply correlation mismatch for " + tag)
            require(envelope.get("body", {}).get("applied") is applied, "unexpected reply: " + json.dumps(envelope))
            self.post("done", box, names[0].parent.name)
            return envelope

        self.replies[tag] = self.wait("correlated reply for " + tag, take)
        return self.replies[tag]

    def events(self, stack, event, letter=None):
        path = stack / "audit.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        return [row for row in rows if row["event"] == event and (letter is None or row["letter"] == letter)]

    def route(self, tag):
        letter, box = self.sent[tag]
        for stack in (self.a, self.foreman):
            for event in ("before_verdict", "before_reply"):
                require(len(self.events(stack, event, letter)) == 1,
                        "missing or repeated %s at %s for %s" % (event, stack.name, tag))
            require(sum(row["verdict"] == "pass" for row in self.events(stack, "after_verdict", letter)) == 1,
                    "request passed more or less than once at %s for %s" % (stack.name, tag))
        original = self.events(self.a, "before_verdict", letter)[0]
        relayed = self.events(self.foreman, "before_verdict", letter)[0]
        # 兩站的 kernel.json 都沒寫 next：信到得了領班與 daemon，靠的是 AOS_KERNEL 與「指到自己就跳過」。
        require(all(Path(row["kernel_env"] or "/").resolve() == self.foreman / "requests"
                    for row in (original, relayed)),
                "a station did not run with AOS_KERNEL set to the foreman mailbox")
        require((self.a / "requests" / original["reply_to"]).resolve() == box,
                "A did not receive the original reply mailbox")
        require((self.foreman / "requests" / relayed["reply_to"]).resolve() == self.a / "replies",
                "foreman reply bypassed A")
        require(self.events(self.a, "before_reply", letter)[0]["body"] == self.replies[tag]["body"],
                "A did not relay the received reply body")
        reply_event = self.events(self.a, "before_reply", letter)[0]
        require(reply_event["sender"] == original["sender"] and Path(reply_event["reply_to"]).resolve() == box,
                "A did not retain the original sender and reply mailbox")

    def queue(self):
        return read(self.foreman / "queue.json", {"queued": []})["queued"]

    def queued(self, tags):
        letters = [self.sent[tag][0] for tag in tags]
        return [row["letter"] for row in self.queue()] == letters

    def finish(self, name):
        # 不送訊號、不用按名稱收行程；這個測試 proc 自己看到標記後退場。
        self.inside(self.foreman / "procs" / name / "finish").touch()
        self.wait(name + " naturally stopped", lambda:
                  self.table(self.foreman).get(name, {}).get("phase") == "stopped")

    def shutdown(self):
        if self.root_proc.poll() is None:
            self.ctl(self.root, "shutdown", "--timeout-s", "30")
        self.root_proc.wait(timeout=self.timeout)

    def check(self):
        self.make()
        self.start()
        self.stage = "1"
        # 仿 llm_fake 的 script/tool_calls；手動驅動這一輪，不另外搭問腦總機。
        arguments = {"op": "add", "def": str(self.defs / "idle"), "name": "kid_tool",
                     "ws": str(self.work), "timeout_s": self.timeout}
        fake = {"endpoint": {"script": [{"tool_calls": [{"name": "subagent", "arguments": arguments}]}]},
                "request": {"messages": [{"role": "user", "content": "Create one subagent."}]}}
        result = self.run(["aos-exec", "--stack", str(self.agent / "think"), str(self.defs / "fake_call.json")],
                          env=self.agent_env, payload=json.dumps(fake))
        call = json.loads(result.stdout)["message"]["tool_calls"][0]["function"]
        require(call["name"] == "subagent", "fake brain did not call subagent")
        self.run(["aos-exec", "--stack", str(self.agent / "tools/subagent"),
                  str(self.defs / "subagent_call.json")], env=self.agent_env, payload=call["arguments"])
        self.wait("tool subagent running", lambda: self.table(self.foreman).get("kid_tool", {}).get("phase") == "running")
        # 另送一封同型掛子信，保留完整信封，直接核對最終 in_reply_to。
        self.send("kid1", {"procs_added": {"kid1": self.spec("kid1")}})
        self.receive("kid1")
        self.route("kid1")
        self.wait("four running procs", lambda: sum(row.get("phase") == "running"
                  for row in self.table(self.foreman).values()) == 4)
        print("ok 1 subagent crossed both stations and A relayed the correlated reply", flush=True)

        self.stage = "2"
        self.send("kid2", {"procs_added": {"kid2": self.spec("kid2")}})
        self.wait("kid2 queued", lambda: self.queued(["kid2"]))
        require("kid2" not in self.table(self.foreman), "queued proc already attached")
        self.finish("kid_tool")
        self.receive("kid2")
        self.route("kid2")
        self.wait("kid2 running and queue empty", lambda: self.queued([]) and
                  self.table(self.foreman).get("kid2", {}).get("phase") == "running")
        print("ok 2 max_running queued the excess request and a freed slot drained it", flush=True)

        # TODO：第 3 段等 aos-daemon 認 procs_state_path 後補；以查詢信驗證刪減表。
        self.stage = "4"
        self.send("evil", {"procs_added": {"evil": self.spec("evil")}})
        reply = self.receive("evil", applied=False)
        require(reply["body"].get("error", {}).get("code") == "HookRejected", "evil was not HookRejected")
        require(not self.events(self.foreman, "before_verdict", self.sent["evil"][0]), "evil reached foreman")
        require("evil" not in self.table(self.foreman), "evil was attached")
        print("ok 4 evil was immediately refused with applied=false and HookRejected", flush=True)

        self.stage = "5"
        for tag in ("kid3", "kid4"):
            self.send(tag, {"procs_added": {tag: self.spec(tag)}})
            self.wait(tag + " queued", lambda tag=tag: any(row["letter"] == self.sent[tag][0] for row in self.queue()))
        require(self.queued(["kid3", "kid4"]), "initial queue order mismatch")
        before = self.queue()
        forwarded = read(self.a / "forwarded.json")
        require(all(letter in forwarded for letter, _ in (self.sent[tag] for tag in ("kid3", "kid4"))),
                "A did not retain pending relay records")
        old_pids = {name: self.table(self.root)[name]["pid"] for name in ("station_a", "foreman")}
        self.shutdown()
        require(self.queue() == before, "shutdown changed queue entries or order")
        self.start()
        self.wait("same queue after restart", lambda: self.queue() == before)
        for name, pid in old_pids.items():
            require(self.table(self.root)[name]["pid"] != pid, name + " did not restart")
        require(read(self.a / "forwarded.json") == forwarded, "restart changed pending relay records")
        for victim, tag in (("kid1", "kid3"), ("kid2", "kid4")):
            self.finish(victim)
            self.receive(tag)
            self.route(tag)
            self.wait(tag + " running", lambda tag=tag: self.table(self.foreman).get(tag, {}).get("phase") == "running")
            if tag == "kid3":
                require(self.queued(["kid4"]), "second queued letter jumped ahead or disappeared")
        self.wait("queue and A relay records empty", lambda: self.queued([]) and not read(self.a / "forwarded.json", {}))
        print("ok 5 both stations restarted with FIFO, pending replies and single forwarding intact", flush=True)

        self.stage = "6"
        self.send("ping", {"ping": True})
        self.receive("ping")
        self.route("ping")
        # 再等數輪：不能留下晚到的第二封回信或第二次轉寄。
        time.sleep(1)
        for tag in ("kid1", "kid2", "kid3", "kid4", "ping"):
            self.route(tag)
        for tag, (_, box) in self.sent.items():
            require(not list((box / "new").glob("*/letter.json")) and not list((box / "cur").glob("*/letter.json")),
                    "unexpected late or duplicate reply for " + tag)
        print("ok 6 ping crossed both stations and the daemon reply returned through A", flush=True)

    def cleanup(self):
        # 起不來也先嘗試自有根樹的公開 shutdown；fallback 只准記錄的 Popen pid。
        if hasattr(self, "root_proc") and self.root_proc.poll() is None:
            try:
                self.shutdown()
            except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                print("Cleanup shutdown failed: " + str(error), flush=True)
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for proc in reversed(self.processes):
                self.signal_owned(proc, sig)
            for proc in self.processes:
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
        for log in self.logs:
            log.close()
        # pgrep 只做核對；絕不拿它的輸出去送訊號。
        survivors = self.run(["pgrep", "-af", str(self.work)], check=False)
        require(survivors.returncode in (0, 1), "temporary process audit failed: " + survivors.stderr)
        if survivors.returncode == 0:
            print(survivors.stdout, end="", flush=True)
            raise RuntimeError("temporary processes remain; fixture retained at " + str(self.work))
        print("Temporary process audit: empty", flush=True)
        shutil.rmtree(self.work)
        print("Temporary fixture removed: " + str(self.work), flush=True)

    def diagnostics(self):
        print("Failure fixture: " + str(self.work), flush=True)
        for path in [self.work / "root.log", *self.root.glob("procs/**/stderr.txt")]:
            if path.exists() and path.stat().st_size:
                print("--- " + str(path.relative_to(self.work)) + " ---", flush=True)
                print(path.read_text(errors="replace")[-4000:], end="\n", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Check five kernel-chain scenarios in an isolated disposable tree.")
    parser.add_argument("--timeout-s", type=float, default=30, help="positive timeout per wait (default: 30)")
    opts = parser.parse_args()
    require(0 < opts.timeout_s <= 300, "--timeout-s must be in (0, 300]")
    check = Check(opts.timeout_s)
    passed = False
    try:
        check.check()
        passed = True
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print("kernel-chain-check: error: StageFailed stage %s: %s" % (check.stage, error), flush=True)
        check.diagnostics()
    finally:
        try:
            check.cleanup()
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            passed = False
            print("kernel-chain-check: error: CleanupFailed " + str(error), flush=True)
    if passed:
        print("kernel-chain-check: 5/5 ok", flush=True)
        return 0
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print("kernel-chain-check: error: CheckFailed " + str(error), flush=True)
        sys.exit(1)
