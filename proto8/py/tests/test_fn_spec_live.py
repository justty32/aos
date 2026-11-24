"""test_fn_spec_live - cut 3 for real: an agent.py with @fn.tool add and @fn.hook no_secrets compiled with the installed aos, checked by agent_def check, mounted in a copy of start-api with a scripted fake brain: the brain calls add and gets 5, a ws_write that mentions a secret is blocked and the reason is in history."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

PROTO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROTO / "lib"))          # the installed copy (the same as the commands in bin/)
from aos.py import agent, daemon_ctl, Failed  # noqa: E402

ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
ENV.update(AOS_HOME=str(PROTO), PATH=str(PROTO / "bin") + os.pathsep + ENV["PATH"], PYTHONDONTWRITEBYTECODE="1")
SCRIPT = [{"tool_calls": [{"name": "add", "arguments": {"a": 2, "b": 3}}]},
          {"tool_calls": [{"name": "ws_write", "arguments": {"path": "note.txt", "content": "my secret"}}]},
          {"content": "done with add and ws_write"}]
BODY = '''
from aos.py import fn
std = defs.std


@fn.tool
def add(a: float, b: float) -> float:
    """Add two numbers and return the sum. Example: {"a": 2, "b": 3} -> 5

    Args:
      a: the first number
      b: the second number
    """
    return a + b


@fn.hook("before_tool", condition="ws_write")
def no_secrets(event):
    """Stop a ws_write that mentions a secret."""
    if "secret" in json.dumps(event.get("arguments", {})):
        return fn.block("the arguments mention a secret")


agent = defs.Agent(
    "Add numbers and write notes, but never a secret.",
    system="You add numbers and write notes.\\n",
    tools=[std.pack("ws-write"), add],
    llm={"model": "fake-fn"},
    fsm=std.fsm(),
    hooks=[no_secrets],
)
defs.main(agent)
'''


def until(cond, timeout=30, every=0.1):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = cond()
        if v:
            return v
        time.sleep(every)
    raise AssertionError("timed out")


@unittest.skipUnless((PROTO / "bin" / "aos-exec").exists(), "needs an installed tree (bin/aos-exec)")
class Live(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="fn-spec-live-")))
        cls.tree = cls.tmp / "tree"
        shutil.copytree(PROTO / "templates" / "starts" / "start-api", cls.tree, symlinks=True)
        cls.mounted = (cls.tree / "llm" / "kernel.json").is_file()      # the llm kernel as a row on the root (start-api 11-20) or llms/def
        kernel = cls.tree / ("llm" if cls.mounted else "llms/def") / "kernel.json"
        k = json.loads(kernel.read_text())
        k["endpoints"]["fake-fn"] = {"exec": {"$env": "AOS_HOME", "$path": "/lib/tools/base/llm_fake"}, "speed": "fast", "cost": "free",
                                     "script": SCRIPT, "summary": "scripted fake brain: calls add, then ws_write with a secret"}
        kernel.write_text(json.dumps(k))
        cls.defn = cls.tree / "agents" / "fnbot"
        cls.defn.mkdir()
        head = (PROTO / "templates" / "agents" / "agent-python" / "agent.py").read_text().split("# ---- your agent")[0]
        (cls.defn / "agent.py").write_text(head + "import json\n" + BODY)
        cls.compiled = subprocess.run([sys.executable, str(cls.defn / "agent.py"), "--compile"], env=ENV, text=True,
                                      capture_output=True, timeout=60)
        cls.procs, cls.logs = [], [open(cls.tmp / n, "w") for n in ("root.log", "llm.log")]
        cls.daemon = str(cls.tree / ".stack")
        try:
            cls.procs.append(subprocess.Popen(["aos-exec", "root"], cwd=cls.tree, env=ENV, stdin=subprocess.DEVNULL,
                                              stdout=cls.logs[0], stderr=subprocess.STDOUT, start_new_session=True))
            until(lambda: (cls.tree / ".stack" / "state.json").exists())
            if cls.mounted:
                subprocess.run(["aos-daemon-ctl", "-d", ".stack", "add", "--auto-restart", "llm"], cwd=cls.tree, env=ENV,
                               check=True, capture_output=True, timeout=60)
                until(lambda: (cls.tree / ".stack" / "procs" / "llm" / "state.json").exists())
            else:
                cls.procs.append(subprocess.Popen(["aos-exec", "--stack", "stacks/llm", "def"], cwd=cls.tree / "llms", env=ENV,
                                                  stdin=subprocess.DEVNULL, stdout=cls.logs[1], stderr=subprocess.STDOUT,
                                                  start_new_session=True))
                until(lambda: (cls.tree / "llms" / "stacks" / "llm" / "state.json").exists())
            os.environ.update(AOS_HOME=str(PROTO), PATH=ENV["PATH"])
            for k in [k for k in os.environ if k.startswith("AOS_") and k != "AOS_HOME"]:
                del os.environ[k]
            if cls.compiled.returncode == 0:
                agent.ctl.add(str(cls.defn), daemon=cls.daemon, w=str(cls.tree), auto_restart=True)
                cls.a = agent.attach("fnbot", daemon=cls.daemon)
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            for d in [cls.daemon] + ([] if cls.mounted else [str(cls.tree / "llms" / "stacks" / "llm")]):
                try:
                    daemon_ctl.shutdown(daemon=d)
                except Failed:
                    pass
            for p in cls.procs:
                try:
                    p.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)          # only the group this test started
                    p.wait()
        finally:
            for f in cls.logs:
                f.close()
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_compiled_and_checked(self):
        self.assertEqual(self.compiled.returncode, 0, self.compiled.stderr)
        self.assertEqual(json.loads((self.defn / "tools.json").read_text())["tools"]["add"], {"path": "fn/add.py"})
        self.assertEqual(json.loads((self.defn / "hookeds.json").read_text())["no_secrets"],
                         {"event": "before_tool", "handler": "fn/no_secrets.py", "condition": "ws_write"})
        r = subprocess.run(["aos-exec", str(PROTO / "lib" / "tools" / "agent" / "agent_def")], cwd=self.tree, env=dict(ENV, AOS_WS=str(self.tree)),
                           input=json.dumps({"op": "check", "path": str(self.defn)}), text=True, capture_output=True, timeout=60)
        self.assertEqual(json.loads(r.stdout)["problems"], [], r.stdout + r.stderr)

    def test_brain_calls_the_tool_and_the_hook_blocks(self):
        self.assertEqual(self.compiled.returncode, 0, self.compiled.stderr)
        letter = self.a.say("add 2 and 3, then write a note")
        self.assertIn("done with add and ws_write", self.a.listen(timeout_s=60, letter=letter))
        history = [json.loads(x) for x in (Path(self.a.stack) / "history.jsonl").read_text().splitlines() if x.strip()]
        tools = [m for m in history if m.get("role") == "tool"]
        self.assertEqual(len(tools), 2, history)
        self.assertEqual(tools[0]["content"].strip(), "5")
        self.assertIn("the arguments mention a secret", tools[1]["content"])
        self.assertFalse((self.tree / "note.txt").exists())


if __name__ == "__main__":
    unittest.main()
