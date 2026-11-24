"""Test subagent and agents_ctl on a real aos-daemon: tools/llm changes land on the subagent (not the parent), and a subagent removed with agents_ctl is forgotten and frees the quota."""
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

sys.dont_write_bytecode = True
TOOL = Path(__file__).resolve().parents[1] / "_entry"
AGENT = TOOL.parents[1]
CTL_TOOL = AGENT / "agents_ctl" / "_entry"
PROTO = AGENT.parents[2]
TEMPLATE = PROTO / "templates" / "agents" / "agent-fsm"
DAEMON_BIN = PROTO / "bin" / "aos-daemon"


@unittest.skipUnless(DAEMON_BIN.exists() and CTL_TOOL.exists(), "needs an installed aos-daemon (proto8/bin) and agents_ctl")
class RealDaemon(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="subagent-real-"))
        self.ws = self.tmp / "ws"
        self.dstack = self.ws / ".stack"
        self.dstack.mkdir(parents=True)
        (self.tmp / "daemon.json").write_text('{"interval_ms": 200}')
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        bins = [str(PROTO / "bin")]
        env.update(PATH=os.pathsep.join(bins + [env["PATH"]]), AOS_HOME=str(PROTO), PYTHONDONTWRITEBYTECODE="1")
        self.log = open(self.tmp / "d.log", "w")
        self.daemon = subprocess.Popen(["aos-daemon", "daemon.json"], cwd=self.tmp, env=dict(env, AOS_STACK=str(self.dstack)),
                                       stdout=self.log, stderr=self.log, start_new_session=True)
        self.addCleanup(self.stop_daemon)
        self.env = dict(env, AOS_DAEMON=str(self.dstack), AOS_WS=str(self.ws))
        deadline = time.monotonic() + 10
        while True:
            r = self.agent("ctl", "add", "--name", "mom", str(TEMPLATE), check=False)
            if r.returncode == 0 or time.monotonic() > deadline:
                break
            time.sleep(0.2)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.mom = r.stdout.strip().splitlines()[-1]
        self.env["AOS_STACK"] = os.path.join(self.mom, "tools", TOOL.parent.name)

    def stop_daemon(self):
        try:
            os.killpg(self.daemon.pid, signal.SIGTERM)
            self.daemon.wait(15)
        except (OSError, subprocess.TimeoutExpired):
            try:
                os.killpg(self.daemon.pid, signal.SIGKILL)
            except OSError:
                pass
            self.daemon.wait()
        self.log.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def agent(self, *argv, check=True):
        r = subprocess.run(["aos-agent"] + list(argv), cwd=self.ws, env=self.env, capture_output=True, text=True, timeout=60)
        if check:
            self.assertEqual(r.returncode, 0, (argv, r.stderr))
        return r

    def tool(self, path, args):
        return subprocess.run([str(path)], input=json.dumps(args), cwd=self.ws, env=self.env, capture_output=True, text=True, timeout=120)

    def ok(self, path, args):
        r = self.tool(path, args)
        self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
        return r.stdout

    def test_subagents_on_a_real_daemon(self):
        self.ok(TOOL, {"op": "add", "def": str(TEMPLATE), "name": "kid", "ws": "kid"})
        self.assertEqual([c["name"] for c in json.loads(self.ok(TOOL, {"op": "ls", "json": True}))["subagents"]], ["kid"])
        short = self.ok(TOOL, {"op": "ls"}).splitlines()
        self.assertEqual((len(short), short[0].split("\t")[0], short[-1]), (2, "kid", "subagents 1/4"))
        self.assertLess(len(short[0]), 200)
        long = self.ok(TOOL, {"op": "ls", "long": True}).splitlines()
        self.assertEqual((len(long[0].split("\t")), long[-1]), (9, "subagents 1/4"))
        out = self.ok(TOOL, {"op": "tools", "name": "kid", "args": {"op": "add", "name": "math2", "path": str(PROTO / "py" / "tools" / "base" / "math")}})
        self.assertIn("kid's next reply", out)
        kid_tools = [t["name"] for t in json.loads(self.agent("tools", "--target", "kid", "ls", "--json").stdout)]
        mom_tools = [t["name"] for t in json.loads(self.agent("tools", "--target", "mom", "ls", "--json").stdout)]
        self.assertIn("math2", kid_tools)                  # math itself is already in the gadgets pack (11-10 tool-packs)
        self.assertNotIn("math2", mom_tools)
        self.ok(TOOL, {"op": "llm", "name": "kid", "args": {"op": "set", "settings": {"model": "fake"}}})
        self.assertIn("model=fake", self.agent("llm", "--target", "kid", "ls").stdout)
        self.assertNotIn("model=fake", self.agent("llm", "--target", "mom", "ls", check=False).stdout)
        self.assertIn("messages", self.ok(TOOL, {"op": "history", "name": "kid", "args": {"op": "ls"}}))
        self.ok(TOOL, {"op": "hook", "name": "kid", "args": {"op": "ls"}})
        r = self.tool(TOOL, {"op": "tools", "name": "mom", "args": {"op": "ls"}})
        self.assertIn("error: SubagentUnknown mom", r.stdout)
        # someone removes kid with agents_ctl: subagent forgets it and the slot is free again
        self.ok(CTL_TOOL, {"op": "rm", "name": "kid"})
        self.assertNotIn('"kid"', self.ok(CTL_TOOL, {"op": "ls", "json": True}))
        self.assertNotIn("kid\t", self.ok(CTL_TOOL, {"op": "ls"}))
        self.assertEqual(self.ok(TOOL, {"op": "ls"}), "subagents 0/4\n")
        self.assertIn("error: SubagentUnknown kid", self.tool(TOOL, {"op": "state", "name": "kid"}).stdout)
        self.assertIn("subagents 1/4", self.ok(TOOL, {"op": "add", "def": str(TEMPLATE), "name": "kid2"}))
        self.ok(TOOL, {"op": "rm", "name": "kid2", "purge": True})

    def test_requests_go_to_aos_kernel_without_aos_daemon(self):
        """只靠會答查詢信的框架站掛子、存絕對 stack、對帳、移除；不需要 AOS_DAEMON。"""
        from kernel_fixture import KernelFixture
        fixture = KernelFixture()
        self.addCleanup(fixture.close)
        self.assertNotIn("AOS_DAEMON", fixture.env)
        result = fixture.tool(TOOL, {"op": "add", "def": str(fixture.definition), "name": "kid", "ws": "kid"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        book = json.loads((fixture.mom / "tools/subagent/subagents.json").read_text())
        self.assertEqual(Path(book[0]["stack"]), fixture.mom.parent / "kid")
        listed = fixture.tool(TOOL, {"op": "ls", "json": True})
        self.assertEqual(listed.returncode, 0, listed.stdout + listed.stderr)
        self.assertEqual(json.loads(listed.stdout)["subagents"][0]["stack"], book[0]["stack"])
        removed = fixture.tool(TOOL, {"op": "rm", "name": "kid"})
        self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
        self.assertEqual(json.loads((fixture.mom / "tools/subagent/subagents.json").read_text()), [])
        # 指示詞的 stack 由 daemon 算：ctl add 不印路徑時，工具再問 where，不把空字串記成 cwd。
        directed = fixture.tool(TOOL, {"op": "add", "def": str(fixture.definition), "name": "directed",
                                       "stack_json": {"$env": "AOS_WS", "$path": "directed-kid"}})
        self.assertEqual(directed.returncode, 0, directed.stdout + directed.stderr)
        book = json.loads((fixture.mom / "tools/subagent/subagents.json").read_text())
        self.assertEqual(book[0]["stack"], str(fixture.ws / "directed-kid"))
        listed = fixture.tool(TOOL, {"op": "ls", "json": True})
        self.assertEqual(json.loads(listed.stdout)["subagents"][0]["name"], "directed")


if __name__ == "__main__":
    unittest.main()
