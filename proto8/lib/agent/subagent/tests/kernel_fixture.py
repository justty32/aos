# 起一台以框架站為身體的暫存 daemon，讓測試只靠 AOS_KERNEL 查表與掛子，並以 shutdown 收尾。
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

PROTO = Path(__file__).resolve().parents[4]

RESPONDER = '''# 測試用的假腦：收到 queue 信後接進 history 並回答固定結論。
import json, os, pathlib, subprocess
stack = pathlib.Path(os.environ["AOS_STACK"])
box = stack / "queue"
subprocess.run(["aos-post", "init", str(box)], check=True, stdout=subprocess.DEVNULL)
subprocess.run(["aos-post", "take-all", str(box)], stdout=subprocess.DEVNULL)
for letter in sorted((box / "cur").iterdir()):
    if not letter.is_dir():
        continue
    body = json.loads((letter / "letter.json").read_text())["body"]
    with (stack / "history.jsonl").open("a") as stream:
        stream.write(json.dumps(body) + "\\n")
        stream.write(json.dumps({"role": "assistant", "content": "kernel-only answer"}) + "\\n")
    subprocess.run(["aos-post", "done", str(box), letter.name], check=True, stdout=subprocess.DEVNULL)
'''


class KernelFixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="agent-kernel-only-")
        self.root = Path(self.tmp.name).resolve()
        self.ws = self.root / "ws"
        self.ws.mkdir()
        self.daemon_stack = self.root / "daemon"
        self.daemon_stack.mkdir()
        self.definition = self.root / "definition"
        self.definition.mkdir()
        self.save(self.definition / "interfaces.json", {"aos-agent": {"entry": "body.json", "history": "history.jsonl"}})
        (self.definition / "reply.py").write_text(RESPONDER)
        self.save(self.definition / "loop.json", {"exec": {"argv": [sys.executable, str(self.definition / "reply.py")]}, "interval_ms": 100})
        self.save(self.definition / "body.json", ["aos-loop", str(self.definition / "loop.json")])
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        bins = [str(p) for layer in ("impls", "cmd") for p in sorted((PROTO / layer).glob("*/bin"))]
        self.env.update(PATH=os.pathsep.join(bins + [self.env["PATH"]]), PYTHONDONTWRITEBYTECODE="1",
                        AOS_HOME=str(PROTO), AOS_WS=str(self.ws))
        self.save(self.root / "kernel.json", {"next": str(self.daemon_stack / "procs_requests")})
        self.save(self.root / "daemon.json", {"exec": {"argv": [str(PROTO / "lib/aos/kernel/_entry"), str(self.root / "kernel.json")]},
                                               "interval_ms": 50})
        self.log = (self.root / "daemon.log").open("w")
        self.proc = subprocess.Popen(["aos-daemon", str(self.root / "daemon.json")], cwd=self.root,
                                     env=dict(self.env, AOS_STACK=str(self.daemon_stack)), stdout=self.log, stderr=self.log)
        try:
            end = time.monotonic() + 10
            while not (self.daemon_stack / "requests/new").is_dir():
                if self.proc.poll() is not None or time.monotonic() >= end:
                    raise RuntimeError("kernel station did not start: " + (self.root / "daemon.log").read_text())
                time.sleep(0.05)
            self.env["AOS_KERNEL"] = str(self.daemon_stack / "requests")
            self.mom = self.root / "agents/mom"
            self.agent("ctl", "add", "--name", "mom", "--stack", str(self.mom), str(self.definition))
            self.agent("ctl", "stop", "mom")
            self.env["AOS_STACK"] = str(self.mom / "tools/subagent")
        except BaseException:
            self.close()
            raise

    @staticmethod
    def save(path, value):
        path.write_text(json.dumps(value) + "\n")

    def agent(self, *args):
        result = subprocess.run(["aos-agent", *args], cwd=self.ws, env=self.env, capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return result.stdout

    def tool(self, path, args, **env):
        return subprocess.run([str(path)], input=json.dumps(args), cwd=self.ws, env=dict(self.env, **env),
                              capture_output=True, text=True, timeout=40)

    def close(self):
        if self.proc.poll() is None:
            print("Shutdown verified temporary stack: " + str(self.daemon_stack), flush=True)
            result = subprocess.run(["aos-daemon-ctl", "-d", str(self.daemon_stack), "shutdown"],
                                    cwd=self.root, env=self.env, capture_output=True, text=True, timeout=15)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            self.proc.wait(15)
        self.log.close()
        self.tmp.cleanup()
