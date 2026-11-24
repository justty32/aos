"""test_agent_spec_extern_live - cut 4 for real: an agent.py with system=defs.extern("../shared/system.txt") and fsm=defs.extern("fsm.hand.json") compiled with the installed aos, mounted in a copy of start-api with a fake brain that answers with the system text it got: editing the shared file shows up without recompiling, recompiling leaves the hand-written files alone, agent_def new copies the links as they are (a copy at another depth is a broken link that agent_def check reports)."""
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
FAKE = r'''#!/usr/bin/env python3
"""echo_system - fake brain endpoint of test_agent_spec_extern_live: answers with the system text it was given."""
import json, sys
msgs = json.load(sys.stdin)["request"]["messages"]
text = next((m.get("content") for m in msgs if m.get("role") == "system"), "")
print(json.dumps({"message": {"role": "assistant", "content": "SYSTEM WAS: %s" % str(text).strip()},
                  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, "model": "fake"}))
'''
BODY = '''
agent = defs.Agent(
    "Answer with the shared system text.",
    system=defs.extern("../../shared/system.txt"),     # a link to a file outside the folder
    tools=[],
    llm={"model": "echo-system"},
    fsm=defs.extern("fsm.hand.json"),                  # a file of this folder kept by hand
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
        cls.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="extern-live-")))
        cls.tree = cls.tmp / "tree"
        shutil.copytree(PROTO / "templates" / "starts" / "start-api", cls.tree, symlinks=True)
        cls.mounted = (cls.tree / "llm" / "kernel.json").is_file()      # the llm kernel as a row on the root (start-api 11-20) or llms/def
        kernel = cls.tree / ("llm" if cls.mounted else "llms/def") / "kernel.json"
        brain = cls.tree / "echo_system"
        brain.mkdir()
        (brain / "_entry").write_text(FAKE)
        os.chmod(brain / "_entry", 0o755)
        k = json.loads(kernel.read_text())
        k["endpoints"]["echo-system"] = {"exec": str(brain), "speed": "fast", "cost": "free", "summary": "answers with the system text"}
        kernel.write_text(json.dumps(k))
        (cls.tree / "shared").mkdir()
        (cls.tree / "shared" / "system.txt").write_text("first words\n")
        cls.defn = cls.tree / "agents" / "bob"
        cls.defn.mkdir()
        os.environ["AOS_HOME"] = str(PROTO)                              # std.fsm() reads the agent-fsm template there
        from aos.py.agent import defs
        (cls.defn / "fsm.hand.json").write_text(json.dumps(defs.std.fsm().dry_run()["fsm.json"], indent=2) + "\n")
        head = (PROTO / "templates" / "agents" / "agent-python" / "agent.py").read_text().split("# ---- your agent")[0]
        (cls.defn / "agent.py").write_text(head + BODY)
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
                cls.a = agent.attach("bob", daemon=cls.daemon)
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

    def agent_def(self, **args):
        r = subprocess.run(["aos-exec", str(PROTO / "lib" / "tools" / "agent" / "agent_def")], cwd=self.tree,
                           env=dict(ENV, AOS_WS=str(self.tree)), input=json.dumps(args), text=True, capture_output=True, timeout=60)
        first = r.stdout.splitlines()[0] if r.stdout.strip() else ""     # check with problems: the JSON, then its error line
        return json.loads(first) if first.startswith("{") else r.stdout + r.stderr

    def ask(self, text):
        letter = self.a.say(text)
        return self.a.listen(timeout_s=60, letter=letter)

    def test_1_links_run_and_edits_show_without_recompiling(self):
        self.assertEqual(self.compiled.returncode, 0, self.compiled.stderr)
        self.assertEqual(os.readlink(self.defn / "system.txt"), "../../shared/system.txt")
        self.assertEqual(os.readlink(self.defn / "fsm.json"), "fsm.hand.json")
        self.assertEqual(self.agent_def(op="check", path=str(self.defn))["problems"], [])
        self.assertIn("SYSTEM WAS: first words", self.ask("hello"))
        (self.tree / "shared" / "system.txt").write_text("second words\n")       # edited by hand, not recompiled
        self.assertIn("SYSTEM WAS: second words", self.ask("again"))

    def test_2_recompile_leaves_the_hand_files_alone(self):
        hand = (self.defn / "fsm.hand.json").read_bytes()
        shared = (self.tree / "shared" / "system.txt").read_bytes()
        r = subprocess.run([sys.executable, str(self.defn / "agent.py"), "--compile"], env=ENV, text=True, capture_output=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("system.txt -> ../../shared/system.txt", r.stdout)
        self.assertEqual((self.defn / "fsm.hand.json").read_bytes(), hand)
        self.assertEqual((self.tree / "shared" / "system.txt").read_bytes(), shared)
        self.assertEqual(os.readlink(self.defn / "system.txt"), "../../shared/system.txt")

    def test_3_agent_def_new_copies_links_as_they_are(self):
        self.assertIn("wrote definition", self.agent_def(op="new", **{"from": "agents/bob", "path": "agents/bob2"}))
        same = self.tree / "agents" / "bob2"
        self.assertEqual(os.readlink(same / "system.txt"), "../../shared/system.txt")    # the same depth: still works
        self.assertEqual(os.readlink(same / "fsm.json"), "fsm.hand.json")               # its own hand-written copy
        self.assertEqual(self.agent_def(op="check", path=str(same))["problems"], [])
        self.assertIn("wrote definition", self.agent_def(op="new", **{"from": "agents/bob", "path": "agents/deep/bob3"}))
        deep = self.tree / "agents" / "deep" / "bob3"
        self.assertEqual(os.readlink(deep / "system.txt"), "../../shared/system.txt")    # the same text: broken one level deeper
        self.assertFalse((deep / "system.txt").exists())
        problems = self.agent_def(op="check", path=str(deep))["problems"]
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("system.txt is a link to ../../shared/system.txt, which is not there", problems[0]["reason"])


if __name__ == "__main__":
    unittest.main()
