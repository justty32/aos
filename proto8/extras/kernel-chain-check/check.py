#!/usr/bin/env python3
# 在獨立暫存樹驗證 kernel 鏈的掛子、排隊、hook、重啟、ping、照規則分流與留著等表態，並嚴格核對清理範圍。
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

# A 的分流 hook：body 的 lane 是 side 的信改寄旁站，其餘不說話＝照站原本的下一站。
ROUTE = '''#!/usr/bin/env python3
# 照信裡的 lane 欄替這一封挑下一站。
import json, pathlib, sys
event = json.load(sys.stdin)
if (event.get("body") or {}).get("lane") == "side":
    print(json.dumps({"next": str(pathlib.Path(event["stack"]).parent / "station_b" / "requests")}))
'''

# A 的表態 hook：body 的 hold_me 是 true 的信先留著等表態，並記下每次被問；其餘不說話。
# 名字 ask 排在記錄事件的 after_verdict 之後、route 之前：記錄看到的是規則的 pass，route 只在表態 pass 重判那次生效。
ASK = '''#!/usr/bin/env python3
# 把帶 hold_me 的信留著等表態，每次被問都記一列。
import json, pathlib, sys
event = json.load(sys.stdin)
body = event["body"] if isinstance(event.get("body"), dict) else {}
if body.get("hold_me") is True:
    with (pathlib.Path(event["stack"]) / "ask.jsonl").open("a") as stream:
        stream.write(json.dumps({"letter": event["letter"], "verdict": event["verdict"],
                                 "decision": event.get("decision")}) + "\\n")
    print(json.dumps({"verdict": "hold"}))
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
        self.b = self.root / "procs/station_b"
        self.foreman = self.root / "procs/foreman"
        self.agent = self.foreman / "procs/agent"
        self.defs = self.work / "defs"
        self.processes = []
        self.logs = []
        self.sent = {}
        self.bodies = {}
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

    def kernel(self, folder, cfg, **extra):
        hooks = {name: {"event": name, "handler": str(self.defs / "audit"),
                        "timeout_ms": 5000}
                 for name in ("before_verdict", "after_verdict", "before_reply")}
        save(folder / "kernel.json", dict(cfg, hooks=dict(hooks, **extra), reply_via_me=True))

    def make(self):
        for command in ("aos-exec", "aos-daemon", "aos-daemon-ctl", "aos-loop",
                        "aos-agent", "aos-post", "aos-directive", "aos-clock"):
            require(shutil.which(command), "command missing: " + command)
        self.defs.mkdir()
        audit = self.defs / "audit"
        audit.write_text(HOOK, encoding="utf-8")
        audit.chmod(0o755)
        route = self.defs / "route"
        route.write_text(ROUTE, encoding="utf-8")
        route.chmod(0o755)
        ask = self.defs / "ask"
        ask.write_text(ASK, encoding="utf-8")
        ask.chmod(0o755)
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
        # 旁站 B：不給 AOS_KERNEL、不寫 next，放行的信進根 daemon 的 ctl 信箱。只有 A 的分流 hook 會把信指到它。
        shutil.copytree(PROTO / "kernel/procs-kernel", self.defs / "station_b")
        save(self.defs / "station_b/loop.json",
             {"exec": {"argv": ["aos-exec", str(PROTO / "lib/aos/kernel"),
                                str(self.defs / "station_b/kernel.json")]}, "interval_ms": 150})
        self.kernel(self.defs / "station_b", {})
        self.kernel(self.defs / "station_a", {}, route={
            "event": "after_verdict", "condition": "pass", "handler": str(route), "timeout_ms": 5000}, ask={
            "event": "after_verdict", "condition": "pass", "handler": str(ask), "timeout_ms": 5000})
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
            "station_b": {"exec": str(self.defs / "station_b"), "stack": str(self.b)},
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
        self.wait("station A and B mailboxes", lambda: all(
            (stack / "requests/new").is_dir() for stack in (self.a, self.b)))
        self.wait("agent and other running", lambda: all(
            self.table(self.foreman).get(name, {}).get("phase") == "running" for name in ("agent", "other")))
        self.wait("stations A and B running", lambda: all(
            self.table(self.root).get(name, {}).get("phase") == "running" for name in ("station_a", "station_b")))

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
        self.bodies[tag] = body
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

    def judged(self, stack, letter, tag, held):
        # 留著的信在 A 判兩次：規則先判一次（之後 ask 改成 hold），表態 pass 後重判一次；其餘每站一次。
        passes = [row.get("decision") for row in self.events(stack, "after_verdict", letter) if row["verdict"] == "pass"]
        require(passes == ([None, "pass"] if held and stack == self.a else [None]),
                "request passed more or less than expected at %s for %s: %s" % (stack.name, tag, passes))

    def route(self, tag, held=False):
        letter, box = self.sent[tag]
        for stack in (self.a, self.foreman):
            for event in ("before_verdict", "before_reply"):
                require(len(self.events(stack, event, letter)) == 1,
                        "missing or repeated %s at %s for %s" % (event, stack.name, tag))
            self.judged(stack, letter, tag, held)
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

    def side_route(self, tag, held=False):
        """分流到旁站的信：A 與 B 各進一次、領班沒看到，回信經 B、A 兩站代回。"""
        letter, box = self.sent[tag]
        for stack in (self.a, self.b):
            for event in ("before_verdict", "before_reply"):
                require(len(self.events(stack, event, letter)) == 1,
                        "missing or repeated %s at %s for %s" % (event, stack.name, tag))
            self.judged(stack, letter, tag, held)
        require(not any(self.events(self.foreman, event, letter)
                        for event in ("before_verdict", "after_verdict", "before_reply")),
                "side letter also reached the foreman for " + tag)
        require(self.events(self.a, "after_verdict", letter)[0].get("next", "absent") is None,
                "A's after_verdict event did not carry next: null")
        relayed = self.events(self.b, "before_verdict", letter)[0]
        require((self.b / "requests" / relayed["reply_to"]).resolve() == self.a / "replies",
                "station B reply bypassed A")
        reply_event = self.events(self.a, "before_reply", letter)[0]
        require(reply_event["body"] == self.replies[tag]["body"] and Path(reply_event["reply_to"]).resolve() == box,
                "A did not relay the side station's reply to the original mailbox")

    def no_late_replies(self):
        for tag, (_, box) in self.sent.items():
            require(not list((box / "new").glob("*/letter.json")) and not list((box / "cur").glob("*/letter.json")),
                    "unexpected late or duplicate reply for " + tag)

    def held(self):
        return sorted(row["letter"] for row in read(self.a / "hold.json", {"held": []})["held"])

    def asked(self, letter):
        path = self.a / "ask.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        return [row["decision"] for row in rows if row["letter"] == letter]

    def still_held(self, tags):
        """留著的信：在 A 的窗與 cur 裡、只進過 A 一次、ask 只問一次、領班與 B 沒看到、寄件人沒回信。"""
        letters = sorted(self.sent[tag][0] for tag in tags)
        require(self.held() == letters, "hold.json does not list exactly the held letters: %s" % self.held())
        in_cur = sorted(path.parent.name for path in (self.a / "requests/cur").glob("*/letter.json"))
        require(in_cur == letters, "A's requests/cur/ does not hold exactly the held letters: %s" % in_cur)
        for tag in tags:
            letter, box = self.sent[tag]
            require(len(self.events(self.a, "before_verdict", letter)) == 1, "before_verdict ran again for " + tag)
            require(self.asked(letter) == [None], "ask was not asked exactly once for %s: %s" % (tag, self.asked(letter)))
            require(not any(self.events(stack, event, letter) for stack in (self.foreman, self.b)
                            for event in ("before_verdict", "after_verdict", "before_reply")),
                    "held letter left A for " + tag)
            require(not list(box.glob("*/*/letter.json")), "held letter already got a reply for " + tag)

    def decide(self, tag, said):
        # 照框架說的：先寫暫存檔再改名進 decisions/<信名>.json。
        letter = self.sent[tag][0]
        folder = self.inside(self.a / "decisions")
        folder.mkdir(exist_ok=True)
        temp = self.inside(self.work / "decision.tmp")
        save(temp, said)
        os.rename(temp, folder / (letter + ".json"))

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
        self.no_late_replies()
        print("ok 6 ping crossed both stations and the daemon reply returned through A", flush=True)

        self.stage = "7"
        # 一個站、兩個下一站：A 的 after_verdict hook 照 lane 欄把信分到旁站 B 或照舊給領班，一封只去一處。
        self.send("side", {"ping": True, "lane": "side"})
        self.send("main", {"ping": True, "lane": "main"})
        for tag in ("side", "main"):
            self.receive(tag)
        time.sleep(1)
        self.side_route("side")
        self.route("main")
        require(not any(self.events(self.b, event, self.sent["main"][0])
                        for event in ("before_verdict", "after_verdict", "before_reply")),
                "main letter also reached station B")
        for tag in ("kid1", "kid2", "kid3", "kid4", "ping"):
            require(not self.events(self.b, "before_verdict", self.sent[tag][0]), tag + " reached station B")
        self.wait("A relay records empty", lambda: not read(self.a / "forwarded.json", {}))
        self.no_late_replies()
        print("ok 7 A's hook split two letters between two next stations and both replies returned", flush=True)

        self.stage = "8"
        # 先留著等表態：A 的 ask hook 把帶 hold_me 的信留在 A；有人寫了表態檔，站才照它放行或拒。
        probes = {"held_pass": {"ping": True, "hold_me": True, "desc": "forward after a yes"},
                  "held_refuse": {"ping": True, "hold_me": True, "why": {"asked_by": "chain-check", "n": 2}},
                  "held_side": {"ping": True, "hold_me": True, "lane": "side", "desc": {"note": "side after a yes"}}}
        for tag, body in probes.items():
            self.send(tag, body)
        self.wait("three letters held at A", lambda: self.held() == sorted(self.sent[tag][0] for tag in probes))
        self.still_held(probes)
        time.sleep(1)
        self.still_held(probes)
        # 表態 pass：重判一次後照平常的路 A → 領班 → 根 daemon，回信經兩站代回；body 原樣（額外鍵也在）。
        self.decide("held_pass", {"verdict": "pass"})
        reply = self.receive("held_pass")
        require(reply["body"] == {"applied": True}, "held_pass reply is not the daemon's ping reply")
        self.route("held_pass", held=True)
        require(self.events(self.foreman, "before_verdict", self.sent["held_pass"][0])[0]["body"] == probes["held_pass"],
                "A did not forward the held body unchanged")
        require(self.asked(self.sent["held_pass"][0]) == [None, "pass"], "ask was not asked once more on the re-judge")
        # 表態 refuse：寄件人拿到表態寫的 code 與 msg，信沒離開 A。
        self.decide("held_refuse", {"verdict": "refuse", "error": {"code": "NotNow", "msg": "say what it is for"}})
        reply = self.receive("held_refuse", applied=False)
        require(reply["body"] == {"applied": False, "error": {"code": "NotNow", "msg": "say what it is for"}},
                "held_refuse reply does not carry the decision's error: " + json.dumps(reply["body"]))
        letter = self.sent["held_refuse"][0]
        require(not any(self.events(stack, event, letter) for stack in (self.foreman, self.b)
                        for event in ("before_verdict", "after_verdict", "before_reply")),
                "refused held letter left A")
        require(self.asked(letter) == [None] and not self.events(self.a, "before_reply", letter),
                "refused held letter was asked or relayed again")
        # 帶 lane=side 的留著信：表態 pass 重判時 route 才給 next，分到 B，回信經 B、A 代回。
        self.decide("held_side", {"verdict": "pass"})
        reply = self.receive("held_side")
        require(reply["body"] == {"applied": True}, "held_side reply is not the daemon's ping reply")
        self.side_route("held_side", held=True)
        require(self.events(self.b, "before_verdict", self.sent["held_side"][0])[0]["body"] == probes["held_side"],
                "A did not forward the held side body unchanged")
        time.sleep(1)
        require(read(self.a / "hold.json") == {"held": []}, "hold.json is not empty: " + json.dumps(read(self.a / "hold.json")))
        require(not list((self.a / "decisions").iterdir()), "decision files left in A's decisions/")
        require(not list((self.a / "requests/cur").glob("*/letter.json")), "letters left in A's requests/cur/")
        self.wait("A relay records empty", lambda: not read(self.a / "forwarded.json", {}))
        self.no_late_replies()
        print("ok 8 three held letters waited at A until decided: pass, refuse and pass split to B", flush=True)

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
    parser = argparse.ArgumentParser(description="Check seven kernel-chain scenarios in an isolated disposable tree.")
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
        print("kernel-chain-check: 7/7 ok", flush=True)
        return 0
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print("kernel-chain-check: error: CheckFailed " + str(error), flush=True)
        sys.exit(1)
